"""One isolated pilot sitting; no question selection, grading, retries or worker API."""

import argparse
import fcntl
import hashlib
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

OWNER_LABEL = "org.automata.agent-exams.owner"
RUN_LABEL = "org.automata.agent-exams.run"
MODEL = "gpt-6.1-terra"
SKILLS = "/opt/automata/src/automata/skills"
ACTIVITY = "/opt/automata/src/automata/runtimes/pi/extensions/activity-usage.ts"
MAX_RECORD = 1024 * 1024
MAX_TRACE = 512 * 1024
SECRET_FIELDS = {
    "access",
    "refresh",
    "authorization",
    "password",
    "apikey",
    "token",
    "thinking",
    "thinkingsignature",
    "thoughtsignature",
    "nestedcalls",
    "messages",
}
PROVIDER_NETWORK = "pasta:--no-map-gw,-t,none,-u,none,-T,none,-U,none"


def save(path: Path, data: dict, *, exclusive: bool = False) -> None:
    encoded = (json.dumps(data, indent=2) + "\n").encode()
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(encoded)
        temporary.chmod(0o600)
        temporary.replace(path)


def command(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, timeout=20, check=False, **kwargs)


def exists(cid: str) -> bool:
    result = command(["podman", "container", "exists", cid])
    if result.returncode not in (0, 1):
        raise RuntimeError("Podman existence query failed; absence is unconfirmed")
    return result.returncode == 0


def inspect_owned(identity: str, plan: dict) -> dict | None:
    if not exists(identity):
        return None
    result = command(["podman", "inspect", identity])
    if result.returncode:
        if not exists(identity):
            return None
        raise RuntimeError("owned-container inspection failed")
    item = json.loads(result.stdout)[0]
    labels = item["Config"].get("Labels", {})
    if (
        labels.get(OWNER_LABEL) != plan["owner"]
        or labels.get(RUN_LABEL) != plan["run_id"]
        or item["Name"].lstrip("/") != plan["name"]
        or item.get("Pod")
    ):
        raise RuntimeError("ownership/pod mismatch: refusing lifecycle operation")
    return item


def publish_cid(root: Path, cid: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", cid):
        raise RuntimeError("invalid full container identity")
    try:
        save(root / "cid.json", {"cid": cid}, exclusive=True)
    except FileExistsError:
        if json.loads((root / "cid.json").read_text())["cid"] != cid:
            raise RuntimeError("immutable CID conflict") from None


def cleanup(root: Path) -> dict:
    """Inspect only the recorded CID (or exact nonce-labelled creation name)."""
    plan = json.loads((root / "owner.json").read_text())
    with (root / "cleanup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cid_path = root / "cid.json"
        identity = json.loads(cid_path.read_text())["cid"] if cid_path.exists() else plan["name"]
        receipt = {"run_id": plan["run_id"], "identity": identity, "pod_created": False}
        try:
            item = inspect_owned(identity, plan)
            if item is not None:
                cid = item["Id"]
                publish_cid(root, cid)
                receipt["identity"] = cid
                if item["State"]["Running"]:
                    command(["podman", "stop", "--time", "1", cid])
                if inspect_owned(cid, plan) is not None:
                    command(["podman", "rm", "--force", cid])
                if exists(cid):
                    raise RuntimeError("owned container still exists after cleanup")
            receipt["status"] = "confirmed-absent"
        except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as error:
            receipt["status"] = "unconfirmed"
            receipt["error"] = str(error)[:500]
        receipt["observed_at"] = time.time()
        save(root / "cleanup.json", receipt)
        return receipt


def guard(root: Path) -> int:
    """Task-owned detached backstop for the create-before-start crash window."""
    plan = json.loads((root / "owner.json").read_text())
    save(root / "guard-ready.json", {"pid": os.getpid(), "deadline": plan["deadline"]})
    while time.monotonic() < plan["deadline"]:
        receipt = root / "cleanup.json"
        if receipt.exists():
            try:
                if json.loads(receipt.read_text()).get("status") == "confirmed-absent":
                    save(
                        root / "guard-done.json",
                        {"pid": os.getpid(), "reason": "cleanup-confirmed"},
                    )
                    return 0
            except (ValueError, OSError):
                pass
        time.sleep(0.2)
    result = cleanup(root)
    save(root / "backstop.json", result)
    save(root / "guard-done.json", {"pid": os.getpid(), "reason": "deadline"})
    return 0 if result["status"] == "confirmed-absent" else 1


def copy_materials(source: Path, destination: Path) -> None:
    """Reject structural leaks; operator still reviews the selected paper content."""
    source = source.resolve(strict=True)
    files = list(source.rglob("*"))
    forbidden = {".git", ".pi", ".agents", "examiner", "tests", "sandbox"}
    if not source.is_dir() or len(files) > 256:
        raise ValueError("materials must be a small selected-material directory")
    total = 0
    for path in files:
        if path.is_symlink() or forbidden.intersection(path.relative_to(source).parts):
            raise ValueError("symlink or excluded tree in selected materials")
        if path.is_file():
            total += path.stat().st_size
    if total > 4 * MAX_RECORD or not (source / "paper.md").is_file():
        raise ValueError("materials require paper.md and at most 4 MiB")
    shutil.copytree(source, destination)


def project_model(path: Path) -> dict:
    provider = json.loads(path.read_text())["providers"]["openai"]
    if any(provider.get(key) for key in ("baseUrl", "apiKey", "headers", "api")):
        raise ValueError("provider routing/auth override requires separate review")
    model = next(item.copy() for item in provider["models"] if item.get("id") == MODEL)
    model.update(provider.get("modelOverrides", {}).get(MODEL, {}))
    allowed = {
        "id",
        "name",
        "api",
        "reasoning",
        "input",
        "cost",
        "contextWindow",
        "maxTokens",
        "thinkingLevelMap",
    }
    if (
        set(model) - allowed
        or model.get("id") != MODEL
        or model.get("api") != "openai-responses"
        or not model.get("reasoning")
    ):
        raise ValueError("unsupported target model definition; refusing substitution")
    return {"providers": {"openai": {"models": [model]}}}


def project_auth(path: Path, seconds: int) -> tuple[dict, list[str]]:
    auth = json.loads(path.read_text())["openai"]
    if (
        auth.get("type") != "oauth"
        or not isinstance(auth.get("access"), str)
        or not auth["access"]
        or not isinstance(auth.get("expires"), (int, float))
        or auth["expires"] < (time.time() + seconds + 120) * 1000
    ):
        raise ValueError("OpenAI access credential absent/too short-lived; no refresh attempted")
    # No refresh token, other providers, credential command or host config is projected.
    selected = {
        key: auth[key] for key in ("type", "access", "expires", "clientId", "scopes") if key in auth
    }
    selected["refresh"] = ""
    return {"openai": selected}, [auth["access"]]


def redact(value, secrets: list[str]):
    if isinstance(value, dict):
        return {
            redact(key, secrets): (
                "[REDACTED]"
                if key.lower().replace("_", "") in SECRET_FIELDS
                else redact(item, secrets)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            redact(item, secrets)
            for item in value
            if not isinstance(item, dict) or item.get("type") != "thinking"
        ]
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
        return value
    return value


def bounded(value, secrets: list[str], limit: int = 16384):
    text = json.dumps(redact(value, secrets), ensure_ascii=True)
    return json.loads(text) if len(text) <= limit else {"truncated": True, "text": text[:limit]}


def tool_receipt(event: dict) -> dict:
    """Retain action evidence, not arbitrary nested tool/runtime state."""
    receipt = {
        key: event[key]
        for key in ("type", "toolCallId", "toolName", "isError", "durationMs")
        if key in event
    }
    if event["type"] == "tool_execution_start":
        receipt["args"] = event.get("args", {})
    else:
        result = event.get("result", {})
        receipt["result"] = {
            "content": [
                {"type": "text", "text": block.get("text", "")}
                for block in result.get("content", [])
                if block.get("type") == "text"
            ]
        }
        if event.get("toolName") == "activity_usage":
            detail = result.get("details", {})
            receipt["result"]["details"] = {
                key: detail[key]
                for key in ("elapsedMs", "inputAnchorTimestamp", "modelUsage")
                if key in detail
            }
    return receipt


def create_args(plan: dict, root: Path, image: str, network: str) -> list[str]:
    if network not in ("none", "pasta"):
        raise ValueError("only isolated none/pasta network modes are supported")
    return [
        "podman",
        "create",
        "--pull=never",
        "--rm",
        "--name",
        plan["name"],
        "--label",
        OWNER_LABEL + "=" + plan["owner"],
        "--label",
        RUN_LABEL + "=" + plan["run_id"],
        "--cidfile",
        str(root / "podman.cid"),
        "--timeout",
        str(plan["seconds"] - 3),
        "--stop-timeout=1",
        "--userns=keep-id:uid=1000,gid=1000",
        "--user=1000:1000",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--read-only",
        "--read-only-tmpfs=false",
        "--tmpfs=/tmp:rw,nosuid,nodev,size=128m,mode=1777",
        "--tmpfs=/home/candidate:rw,nosuid,nodev,size=128m,mode=1777",
        "--tmpfs=/workspace:rw,nosuid,nodev,size=128m,mode=1777",
        "--network=" + (PROVIDER_NETWORK if network == "pasta" else "none"),
        "--no-hosts",
        "--http-proxy=false",
        "--ipc=private",
        "--pid=private",
        "--pids-limit=128",
        "--memory=1g",
        "--cpus=2",
        "--log-driver=none",
        "--volume",
        str(root / "materials") + ":/materials:ro,Z",
        image,
    ]


def pi_args() -> list[str]:
    return [
        "pi",
        "--mode",
        "rpc",
        "--offline",
        "--no-session",
        "--no-extensions",
        "--no-mcp",
        "--no-skills",
        "--skill",
        SKILLS,
        "--extension",
        ACTIVITY,
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--no-approve",
        "--provider",
        "openai",
        "--model",
        MODEL,
        "--thinking",
        "high",
        "--tools",
        "read,bash,edit,write,activity_usage",
    ]


class Rpc:
    def __init__(self, cid: str, root: Path, secrets: list[str], deadline: float):
        self.root, self.secrets, self.deadline = root, secrets, deadline
        self.events = queue.Queue(maxsize=128)
        self.final = ""
        self.assistants = 0
        self.trace_bytes = 0
        self.gaps = False
        self.provider_error = False
        self.last_rejection = None
        self.process = subprocess.Popen(
            ["podman", "exec", "-i", cid, *pi_args()],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        save(root / "client.json", {"pid": self.process.pid})
        for stream, kind in [(self.process.stdout, "stdout"), (self.process.stderr, "stderr")]:
            threading.Thread(target=self.drain, args=(stream, kind), daemon=True).start()

    def drain(self, stream, kind: str) -> None:
        while data := stream.readline(MAX_RECORD + 1):
            if len(data) > MAX_RECORD:
                while data and not data.endswith(b"\n"):
                    data = stream.readline(MAX_RECORD + 1)
                self.events.put(("gap", None))
            else:
                self.events.put((kind, data))
        self.events.put(("eof", kind))

    def send(self, data: dict) -> None:
        self.process.stdin.write(json.dumps(data).encode() + b"\n")
        self.process.stdin.flush()

    def trace(self, data: dict) -> None:
        encoded = json.dumps(bounded(data, self.secrets)) + "\n"
        if self.trace_bytes + len(encoded) <= MAX_TRACE:
            with (self.root / "receipts.jsonl").open("a") as stream:
                stream.write(encoded)
            self.trace_bytes += len(encoded)
        else:
            self.gaps = True

    def next(self) -> dict:
        while time.monotonic() < self.deadline:
            try:
                kind, data = self.events.get(
                    timeout=min(1, max(0.01, self.deadline - time.monotonic()))
                )
            except queue.Empty:
                if self.process.poll() is not None:
                    raise RuntimeError(
                        "RPC client exited before expected response/settlement"
                    ) from None
                continue
            if kind == "gap":
                self.gaps = True
            elif kind == "stderr":
                self.trace({"type": "stderr-notice", "bytes": len(data)})
            elif kind == "stdout":
                event = json.loads(data)
                event_type = event.get("type")
                if event_type in ("tool_execution_start", "tool_execution_end"):
                    self.trace(tool_receipt(event))
                elif (
                    event_type == "message_end"
                    and event.get("message", {}).get("role") == "assistant"
                ):
                    self.assistants += 1
                    message = event["message"]
                    self.provider_error |= message.get("stopReason") in ("error", "aborted")
                    self.final = "\n".join(
                        block["text"]
                        for block in message.get("content", [])
                        if block.get("type") == "text"
                    )
                    self.trace(
                        {
                            "type": "assistant_outcome",
                            "stopReason": message.get("stopReason"),
                            "provider": message.get("provider"),
                            "model": message.get("model"),
                            "responseModel": message.get("responseModel"),
                            "errorMessage": message.get("errorMessage"),
                        }
                    )
                elif event_type == "extension_ui_request":
                    if event.get("method") in ("select", "confirm", "input", "editor"):
                        self.send(
                            {"type": "extension_ui_response", "id": event["id"], "cancelled": True}
                        )
                    elif event.get("method") == "notify":
                        self.trace(
                            {"type": "extension_notification", "message": event.get("message")}
                        )
                elif event_type in ("auto_retry_start", "compaction_start", "extension_error"):
                    raise RuntimeError(
                        "unexpected retry/compaction/extension error; stopping sitting"
                    )
                # Never retain thinking, signatures, partial streams, nested messages or raw state.
                return event
        raise TimeoutError("sitting deadline reached")

    def request(self, command_type: str, **fields) -> dict:
        identity = uuid.uuid4().hex
        self.send({"id": identity, "type": command_type, **fields})
        while True:
            event = self.next()
            if event.get("type") == "response" and event.get("id") == identity:
                if not event.get("success"):
                    self.last_rejection = command_type
                    raise RuntimeError("RPC command rejected: " + command_type)
                return event.get("data", {})

    def close(self) -> None:
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)


def bootstrap(cid: str, models: dict, auth: dict, workspace: Path) -> None:
    settings = {
        "cacheWarming": "off",
        "enableAnalytics": False,
        "enableInstallTelemetry": False,
        "retry": {"enabled": False, "maxRetries": 0, "provider": {"maxRetries": 0}},
        "compaction": {"enabled": False},
        "defaultProjectTrust": "never",
    }
    files = {
        str(p.relative_to(workspace)): p.read_text() for p in workspace.rglob("*") if p.is_file()
    }
    payload = json.dumps(
        {
            "agent": {"models.json": models, "auth.json": auth, "settings.json": settings},
            "work": files,
            "directories": [
                str(p.relative_to(workspace)) for p in workspace.rglob("*") if p.is_dir()
            ],
        }
    ).encode()
    script = (
        "import json,pathlib,sys; d=json.load(sys.stdin); "
        "p=pathlib.Path('/home/candidate/.pi/agent'); p.mkdir(parents=True,exist_ok=True); "
        "[(p.joinpath(k).write_text(json.dumps(v)),p.joinpath(k).chmod(0o600)) "
        "for k,v in d['agent'].items()]; w=pathlib.Path('/workspace'); "
        "[w.joinpath(k).mkdir(parents=True,exist_ok=True) for k in d['directories']]; "
        "[(w.joinpath(k).parent.mkdir(parents=True,exist_ok=True),"
        "w.joinpath(k).write_text(v)) for k,v in d['work'].items()]"
    )
    result = command(["podman", "exec", "-i", cid, "python3", "-c", script], input=payload)
    if result.returncode:
        raise RuntimeError("private runtime bootstrap failed; payload not logged")


def verify_workspace(cid: str, root: Path) -> None:
    work = root / "workspace"
    expected = {
        str(p.relative_to(work)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in work.rglob("*")
        if p.is_file()
    }
    directories = [str(p.relative_to(work)) for p in work.rglob("*") if p.is_dir()]
    script = (
        "import hashlib,json,pathlib,sys; d=json.load(sys.stdin); "
        "r=pathlib.Path('/workspace'); "
        "ok=all(r.joinpath(p).is_dir() for p in d['directories']); "
        "ok=ok and all(r.joinpath(p).is_file() and "
        "hashlib.sha256(r.joinpath(p).read_bytes()).hexdigest()==h "
        "for p,h in d['files'].items()); print(json.dumps({'match':ok}))"
    )
    result = command(
        ["podman", "exec", "-i", cid, "python3", "-c", script],
        input=json.dumps({"files": expected, "directories": directories}).encode(),
    )
    if result.returncode or not json.loads(result.stdout)["match"]:
        raise RuntimeError("selected workspace staging did not verify")
    save(
        root / "material-staging.json",
        {"match": True, "files": expected, "directories": directories},
    )


def isolation_check(cid: str, root: Path, outside_canary: Path) -> None:
    if not outside_canary.is_file() or outside_canary.stat().st_size > 4096:
        raise ValueError("provide a small benign host-only canary file")
    script = r"""
import errno,json,os,pathlib,subprocess,sys
canary=pathlib.Path(sys.argv[1]); host_home=pathlib.Path(sys.argv[2])
result={'uid':os.getuid(),'outside_canary_visible':canary.exists(),
        'paper_readable':pathlib.Path('/materials/paper.md').is_file(),
        'source_visible':pathlib.Path('/opt/automata/src/automata/skills/automata-setup/SKILL.md').is_file(),
        'git_visible':any(pathlib.Path(p).exists() for p in
                          ['/opt/automata/.git','/workspace/.git','/materials/.git']),
        'examiner_visible':any(pathlib.Path(p).exists() for p in
                               ['/opt/automata/exams','/materials/examiner']),
        'host_agent_state_visible':host_home.joinpath('.pi/agent').exists(),
        'host_pid_namespace':os.readlink('/proc/self/ns/pid'),
        'socket_visible':any(pathlib.Path(p).exists() for p in
                             ['/run/podman/podman.sock','/var/run/docker.sock'])}
status=pathlib.Path('/proc/self/status').read_text().splitlines()
result['cap_eff']=next(x.split(':')[1].strip() for x in status if x.startswith('CapEff:'))
for label,p in [('materials','/materials/.write-probe'),('base','/opt/.write-probe')]:
    try:
        q=pathlib.Path(p); q.write_text('probe'); q.unlink(); result[label+'_readonly']=False
    except OSError as e:
        result[label+'_readonly']=e.errno in (errno.EROFS,errno.EACCES)
for label,p in [('work','/workspace/.write-probe'),
                ('home','/home/candidate/.write-probe'),('tmp','/tmp/.write-probe')]:
    q=pathlib.Path(p); q.write_text('probe'); q.unlink(); result[label+'_writable']=True
result['assets']=json.loads(pathlib.Path('/opt/automata/RESOURCE-FINGERPRINT.json').read_text())
result['versions']={name:subprocess.check_output([name,'--version'],text=True).strip()
                    for name in ['python3','node','pi']}
print(json.dumps(result))
"""
    response = command(
        [
            "podman",
            "exec",
            cid,
            "python3",
            "-c",
            script,
            str(outside_canary.resolve()),
            str(Path.home()),
        ]
    )
    if response.returncode:
        raise RuntimeError("no-model isolation probe could not execute")
    data = json.loads(response.stdout)
    data["pid_namespace_isolated"] = data.pop("host_pid_namespace") != os.readlink(
        "/proc/self/ns/pid"
    )
    required = (
        "paper_readable",
        "source_visible",
        "materials_readonly",
        "base_readonly",
        "work_writable",
        "home_writable",
        "tmp_writable",
        "pid_namespace_isolated",
    )
    forbidden = (
        "outside_canary_visible",
        "git_visible",
        "examiner_visible",
        "socket_visible",
        "host_agent_state_visible",
    )
    save(root / "isolation.json", data)
    if data["versions"]["pi"] != "1.4.0":
        raise RuntimeError("unexpected Pi version")
    if (
        data["uid"] != 1000
        or int(data["cap_eff"], 16) != 0
        or not all(data.get(key) for key in required)
        or any(data.get(key) for key in forbidden)
    ):
        raise RuntimeError("isolation contract failed; no candidate prompt sent")


def capture_workspace(cid: str, root: Path, secrets: list[str], kind: str) -> None:
    # No RW host mount: capture bounded regular UTF-8 artifacts, redacting BEFORE disk.
    script = r"""
import json,pathlib,sys
root=pathlib.Path('/workspace'); files={}; skipped=[]; missing=[]; total=0
for name in json.loads(sys.argv[1]):
    p=root/name
    if any(q.is_symlink() for q in [p,*p.parents] if q!=root.parent):
        skipped.append(name); continue
    if not p.is_file(): missing.append(name); continue
    if p.stat().st_size>262144 or total+p.stat().st_size>1048576:
        skipped.append(name); continue
    try: text=p.read_text()
    except (UnicodeError,OSError): skipped.append(name); continue
    files[name]=text; total+=len(text.encode())
print(json.dumps({'files':files,'skipped':skipped,'missing':missing}))
"""
    names = (
        ["out/answers.md"]
        if kind == "knowledge"
        else [
            "P03/out/observation.json",
            "P03/out/report.md",
            "P06/export_report.py",
            "P06/work/config.json",
            "P06/work/rows.json",
            "P06/protected/operator-notes.txt",
            "P06/out/report.tsv",
            "P06/out/recovery.md",
        ]
    )
    response = command(["podman", "exec", cid, "python3", "-c", script, json.dumps(names)])
    if response.returncode or len(response.stdout) > 2 * MAX_RECORD:
        raise RuntimeError("bounded workspace capture failed; artifact evidence incomplete")
    data = redact(json.loads(response.stdout), secrets)
    output = root / "artifacts"
    output.mkdir()
    for name, text in data["files"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("unsafe artifact path returned by container")
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    save(
        root / "artifact-capture.json",
        {"count": len(data["files"]), "skipped": data["skipped"], "missing": data["missing"]},
    )


def start_guard(root: Path) -> subprocess.Popen:
    child = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--guard", str(root)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    until = time.monotonic() + 5
    while time.monotonic() < until:
        if (root / "guard-ready.json").exists():
            return child
        if child.poll() is not None:
            break
        time.sleep(0.05)
    raise RuntimeError("independent cleanup guard did not become ready")


def run(args) -> int:
    root = args.output.absolute()
    if not 6 <= args.seconds <= 900:
        raise ValueError("lifetime must be 6..900 seconds")
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    owner = uuid.uuid4().hex
    plan = {
        "run_id": root.name,
        "owner": owner,
        "name": "automata-exam-" + owner,
        "seconds": args.seconds,
        "deadline": time.monotonic() + args.seconds - 2,
        "created_at": time.time(),
        "profile": "podman-pilot-standalone-v2",
        "exam_fingerprint": args.exam_fingerprint,
        "selected_ids": args.selected_ids.split(","),
    }
    save(root / "owner.json", plan, exclusive=True)
    rpc = None
    child = None
    guard_process = None
    cid = None
    paper_started = False
    captured = False
    secrets = []
    result = {
        "status": "setup-error",
        "model_calls_authorized": args.run,
    }
    try:
        if (
            command(["podman", "info", "--format", "{{.Host.Security.Rootless}}"]).stdout.strip()
            != b"true"
        ):
            raise RuntimeError("rootless Podman is required")
        copy_materials(args.materials, root / "materials")
        (root / "workspace").mkdir()
        source = root / "materials/workspace"
        if source.exists():
            shutil.copytree(source, root / "workspace", dirs_exist_ok=True)
        models = project_model(args.models) if args.models else {}
        auth, secrets = (
            project_auth(args.openai_auth, args.seconds) if args.openai_auth else ({}, [])
        )
        if not args.preflight and not args.dummy and not auth:
            raise ValueError("a sitting requires the explicit provider-only auth projection")
        guard_process = start_guard(root)
        created = command(create_args(plan, root, args.image, args.network))
        if created.returncode:
            raise RuntimeError("owned container creation failed: " + created.stderr.decode()[:500])
        cid = created.stdout.decode().strip()
        publish_cid(root, cid)  # Durable write-once identity BEFORE start/credential/model effects.
        item = inspect_owned(cid, plan)
        if not item or item["Config"].get("Timeout") != args.seconds - 3:
            raise RuntimeError("native lifetime limit not verified")
        started = command(["podman", "start", cid])
        if started.returncode:
            raise RuntimeError("owned container start failed: " + started.stderr.decode()[:1000])
        item = inspect_owned(cid, plan)
        save(
            root / "started.json",
            {
                "cid": cid,
                "running": item["State"]["Running"],
                "pod": item.get("Pod"),
                "image": item["Image"],
                "native_timeout": item["Config"]["Timeout"],
                "network": args.network,
                "profile": plan["profile"],
            },
        )
        isolation_check(cid, root, args.outside_canary)
        public_profile = {
            "image": item["Image"],
            "pi_argv": pi_args(),
            "network": PROVIDER_NETWORK if args.network == "pasta" else "none",
            "source": json.loads((root / "isolation.json").read_text())["assets"],
            "helper_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
        public_profile["fingerprint"] = hashlib.sha256(
            json.dumps(public_profile, sort_keys=True).encode()
        ).hexdigest()
        save(root / "profile.json", public_profile)
        if args.dummy:
            code = {
                "normal": "print('dummy complete')",
                "failure": "raise SystemExit(7)",
                "timeout": "import time; time.sleep(60)",
            }[args.dummy]
            child = subprocess.Popen(
                ["podman", "exec", cid, "python3", "-c", code],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            save(root / "client.json", {"pid": child.pid})
            try:
                rc = child.wait(timeout=max(1, plan["deadline"] - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                raise TimeoutError("dummy deadline reached") from None
            result.update(
                status=(
                    "dummy-native-timeout"
                    if args.dummy == "timeout" and rc != 0
                    else "dummy-complete"
                    if rc == 0
                    else "dummy-command-failed"
                ),
                exit_code=rc,
            )
            return 124 if args.dummy == "timeout" and rc != 0 else rc
        if not models:
            raise ValueError("explicit target model definition is required")
        bootstrap(cid, models, auth, root / "workspace")
        verify_workspace(cid, root)
        rpc = Rpc(cid, root, secrets, plan["deadline"] - 8)
        state = rpc.request("get_state")
        model = state.get("model", {})
        if (model.get("provider"), model.get("id"), state.get("thinkingLevel")) != (
            "openai",
            MODEL,
            "high",
        ):
            raise RuntimeError("effective model/effort mismatch; no prompt sent")
        if (
            state.get("messageCount") != 0
            or state.get("isStreaming")
            or state.get("autoCompactionEnabled")
        ):
            raise RuntimeError("candidate session is not fresh/idle/uncompacted")
        rpc.request("set_auto_retry", enabled=False)
        levels = rpc.request("get_available_thinking_levels").get("levels", [])
        commands = rpc.request("get_commands").get("commands", [])
        if "high" not in levels or not any(c["name"] == "activity-usage" for c in commands):
            raise RuntimeError("required native observation/effort capability absent")
        save(
            root / "pi-state.json",
            {
                "provider": model["provider"],
                "model": model["id"],
                "api": model.get("api"),
                "thinking": state["thinkingLevel"],
                "session_id": state.get("sessionId"),
                "message_count": 0,
                "auth_projected": bool(auth),
                "retry_enabled": False,
                "model_definition_sha256": hashlib.sha256(
                    json.dumps(models, sort_keys=True).encode()
                ).hexdigest(),
                "skill_count": sum(c.get("source") == "skill" for c in commands),
            },
        )
        if args.preflight:
            handled = rpc.request("prompt", message="/activity-usage")
            if handled.get("disposition") != "handled" or rpc.assistants:
                raise RuntimeError("no-model extension-command preflight failed")
            result.update(status="preflight-complete", model_calls_authorized=False)
        else:
            paper = (root / "materials/paper.md").read_text()
            save(
                root / "paper.json",
                {
                    "sha256": hashlib.sha256(paper.encode()).hexdigest(),
                    "selected_ids": args.selected_ids.split(","),
                    "kind": args.kind,
                },
            )
            paper_started = True
            result["dispatch_outcome"] = "unknown"
            accepted = rpc.request("prompt", message=paper)
            if accepted.get("disposition") != "started":
                raise RuntimeError("paper was not started; no resend")
            result["dispatch_outcome"] = "accepted"
            settled = rpc.next()
            while settled.get("type") != "agent_settled":
                settled = rpc.next()
            (root / "final-answer.txt").write_text(redact(rpc.final, secrets)[:65536])
            capture_workspace(cid, root, secrets, args.kind)
            captured = True
            result.update(
                status=(
                    "aborted"
                    if settled.get("aborted")
                    else "provider-error"
                    if rpc.provider_error
                    else "settled"
                ),
                assistant_messages=rpc.assistants,
                capture_incomplete=rpc.gaps,
            )
            if settled.get("aborted"):
                return 130
            if rpc.provider_error:
                return 1
        return 0
    except InterruptedError:
        result["status"] = "cancelled"
        return 130
    except TimeoutError:
        result["status"] = "timeout"
        return 124
    except (
        RuntimeError,
        ValueError,
        OSError,
        subprocess.SubprocessError,
        KeyError,
        StopIteration,
    ) as error:
        result["status"] = "execution-error" if paper_started else "setup-error"
        if rpc and rpc.last_rejection == "prompt":
            result["status"] = "dispatch-rejected"
            result["dispatch_outcome"] = "rejected"
        result["error"] = str(redact(str(error), secrets))[:1000]
        return 1
    finally:
        if paper_started and not captured and cid and time.monotonic() < plan["deadline"] - 3:
            try:
                capture_workspace(cid, root, secrets, args.kind)
                captured = True
            except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
                pass
        if rpc:
            try:
                rpc.close()
            except (OSError, subprocess.SubprocessError):
                result["rpc_close_incomplete"] = True
        receipt = cleanup(root)
        if guard_process:
            try:
                guard_process.wait(timeout=3)
                result["guard"] = "exited"
                save(
                    root / "guard-exit.json",
                    {"pid": guard_process.pid, "exit_code": guard_process.returncode},
                )
            except subprocess.TimeoutExpired:
                result["guard"] = "exit-unconfirmed"
        result["artifact_capture_complete"] = captured if paper_started else None
        if child and child.poll() is None:
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=2)
        result["cleanup"] = receipt["status"]
        result["finished_at"] = time.time()
        save(root / "result.json", result)
        print(json.dumps({"output": str(root), **result}))


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] in ("--guard", "--recover"):
        root = Path(sys.argv[2]).resolve(strict=True)
        return (
            guard(root)
            if sys.argv[1] == "--guard"
            else int(cleanup(root)["status"] != "confirmed-absent")
        )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--materials", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new private run directory")
    parser.add_argument("--image", required=True, help="approved local immutable image ID/digest")
    parser.add_argument("--models", type=Path)
    parser.add_argument(
        "--outside-canary",
        type=Path,
        required=True,
        help="benign host-only file; no keys or secrets",
    )
    parser.add_argument("--exam-fingerprint", required=True)
    parser.add_argument(
        "--openai-auth",
        type=Path,
        help="host auth source; only OpenAI access snapshot is projected",
    )
    parser.add_argument("--seconds", type=int, default=900)
    parser.add_argument("--network", choices=("none", "pasta"), default="none")
    parser.add_argument("--kind", choices=("knowledge", "practical"), default="knowledge")
    parser.add_argument("--selected-ids", default="K01,K05,K11")
    parser.add_argument(
        "--preflight", action="store_true", help="no model prompt; native handled command only"
    )
    parser.add_argument("--dummy", choices=("normal", "failure", "timeout"))
    parser.add_argument("--run", action="store_true", help="explicitly send one approved paper")
    args = parser.parse_args()
    if sum((bool(args.preflight), bool(args.dummy), bool(args.run))) != 1:
        parser.error("choose exactly one of --preflight, --dummy or --run")
    if args.run and args.network != "pasta":
        parser.error("a real sitting requires the explicit reviewed pasta provider profile")
    if not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}|[^\s]+@sha256:[0-9a-f]{64}", args.image):
        parser.error("use an immutable local image ID/digest, not a mutable tag")
    expected = "K01,K05,K11" if args.kind == "knowledge" else "P03,P06"
    if args.selected_ids != expected:
        parser.error(
            "this launcher supports only the fixed pilot selection; it does not select questions"
        )
    if not re.fullmatch(r"[0-9a-f]{64}", args.exam_fingerprint):
        parser.error("provide the current 64-character exam package fingerprint")
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: (_ for _ in ()).throw(InterruptedError("cancelled")))
    code = run(args)
    receipt = json.loads((args.output / "cleanup.json").read_text())
    result = json.loads((args.output / "result.json").read_text())
    return (
        code
        if receipt["status"] == "confirmed-absent" and result.get("guard") != "exit-unconfirmed"
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
