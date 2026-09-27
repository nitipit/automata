"""One configured RPC child. Router presence is deliberately not process ownership."""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from uuid import uuid4

from .lifecycle_config import AgentConfig
from .lifecycle_record import atomic_json, load_record, new_record, process_start, validate_session


class AgentLifecycle:
    def __init__(self, config: AgentConfig, *, timeout: float = 90):
        self.config = config
        config.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.timeout = timeout
        self.mutex = threading.RLock()
        self.condition = threading.Condition()
        self.process = None
        self.lock_file = None
        self.responses = {}
        self.opened = False
        self.settled = False
        self.stopping = False
        self.error = None

    def _record(self, **changes):
        record = load_record(self.config)
        if record:
            record.update(changes)
            atomic_json(self.config.root / "lifecycle.json", record)
        return record

    def _claim(self):
        stream = (self.config.root / "process.lock").open("a+b")
        os.chmod(stream.name, 0o600)
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            stream.close()
            return None
        return stream

    def status(self) -> dict:
        with self.mutex:
            try:
                record = load_record(self.config)
                probe = self._claim()
                held = probe is None
                if probe:
                    probe.close()
                phase = (record or {}).get("phase", "offline")
                # A lock without this host's child is known ownership, not permission
                # to kill/adopt a PID or to start a replacement.
                if held and not self.process:
                    phase = "starting" if phase == "starting" else "running"
                elif not held and phase in {"starting", "running"}:
                    phase = "failed"
                action = None if held else ("resume" if record else "start")
                if action == "resume":
                    try:
                        validate_session(self.config, record)
                    except (OSError, ValueError, KeyError, StopIteration):
                        action, phase = None, "failed"
                return {"configured": True, "agentId": self.config.agent_id,
                        "phase": phase, "action": action,
                        "sessionId": (record or {}).get("sessionId"),
                        "detail": self.error or (record or {}).get("detail", "")}
            except (OSError, ValueError, KeyError):
                return {"configured": True, "agentId": self.config.agent_id,
                        "phase": "failed", "action": None,
                        "detail": "Private lifecycle record requires operator review"}

    def launch(self, action: str) -> dict:
        if action not in {"start", "resume"}:
            raise ValueError("Only start or resume is supported")
        with self.mutex:
            if self.process and self.process.poll() is None:
                return self.status()
            claim = self._claim()
            if claim is None:
                return self.status()
            try:
                record = load_record(self.config)
                if (action == "start" and record) or (action == "resume" and not record):
                    raise ValueError("Action does not match exact owned lifecycle")
                record = record or new_record(self.config)
                session_file = validate_session(self.config, record)
                self._record(phase="starting", detail="", pid=None, processStart=None)
                self.error, self.opened, self.settled, self.stopping = None, False, False, False
                self.responses.clear()
                env = {key: value for key, value in os.environ.items()
                       if not key.startswith("PI_SESSION") and key not in {
                           "PI_CODING_AGENT", "PI_MODEL", "PI_PROVIDER", "PI_REASONING_LEVEL",
                           "AUTOMATA_MESSAGE_ROUTER_ENDPOINT", "AUTOMATA_AGENT_ROUTER_ENDPOINT"}}
                env["AUTOMATA_MESSAGE_ROUTER_ENDPOINT"] = str(self.config.endpoint)
                env["PI_OFFLINE"] = "1"
                # No shell, user argv, arbitrary RPC forwarding, or endpoint credentials
                # in stdout logs. The inherited flock survives host failure until exit.
                process = subprocess.Popen(
                    self.config.command(session_file), cwd=self.config.cwd, env=env,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    pass_fds=(claim.fileno(),), start_new_session=True,
                )
                self.process, self.lock_file = process, claim
                self._record(pid=process.pid, processStart=process_start(process.pid))
                threading.Thread(target=self._read, args=(process,), daemon=True).start()
                threading.Thread(target=self._startup, args=(process, record,), daemon=True).start()
                return self.status()
            except Exception:
                claim.close()
                raise

    def _send(self, kind: str, **fields) -> str:
        identifier = str(uuid4())
        with self.mutex:
            if not self.process or self.process.poll() is not None:
                raise RuntimeError("Owned agent exited")
            wire = json.dumps({"id": identifier, "type": kind, **fields}).encode() + b"\n"
            self.process.stdin.write(wire)
            self.process.stdin.flush()
        return identifier

    def rpc(self, kind: str, **fields) -> dict:
        # Internal host API only. No HTTP route accepts RPC commands.
        process = self.process
        identifier = self._send(kind, **fields)
        with self.condition:
            found = self.condition.wait_for(
                lambda: identifier in self.responses or process.poll() is not None,
                timeout=min(15, self.timeout),
            )
            if not found or identifier not in self.responses:
                raise RuntimeError("Agent RPC did not acknowledge")
            response = self.responses.pop(identifier)
            if not response.get("success"):
                raise RuntimeError("Agent RPC rejected startup")
            return response.get("data", {})

    def _read(self, process):
        try:
            for line in process.stdout:
                if len(line) > 8 * 1024 * 1024:
                    raise ValueError("Oversized RPC record")
                event = json.loads(line)
                with self.condition:
                    if event.get("type") == "response" and event.get("id"):
                        self.responses[event["id"]] = event
                    elif event.get("type") == "tool_execution_end":
                        details = event.get("result", {}).get("details", {})
                        if (not event.get("isError") and event.get("toolName") == "message_router"
                                and details.get("status") == "open"
                                and details.get("participant") == self.config.participant):
                            record = load_record(self.config)
                            self.opened = details.get("sessionId") == record["sessionId"]
                    elif event.get("type") == "agent_settled":
                        self.settled = True
                    self.condition.notify_all()
        except (OSError, ValueError, TypeError):
            self.error = "Agent protocol failed; no automatic retry"
            try:
                process.stdin.close()
            except OSError:
                pass
        finally:
            process.wait()
            with self.mutex:
                if self.process is process:
                    detail = "" if self.stopping else "Agent exited; explicit resume required"
                    self._record(phase="offline" if self.stopping else "failed", detail=detail)
                    self.process = None
                    if self.lock_file:
                        self.lock_file.close()
                        self.lock_file = None
            with self.condition:
                self.condition.notify_all()

    def _startup(self, process, record):
        try:
            actual = self.rpc("get_state")
            if (actual.get("sessionId") != record["sessionId"]
                    or actual.get("sessionFile") != record["sessionFile"]
                    or actual.get("model", {}).get("provider") != self.config.provider
                    or actual.get("model", {}).get("id") != self.config.model
                    or actual.get("thinkingLevel") != self.config.thinking):
                raise RuntimeError("Agent identity, model or effort mismatch")
            atomic_json(self.config.root / "verified-state.json", {
                "sessionId": actual["sessionId"], "sessionFile": actual["sessionFile"],
                "model": self.config.model, "provider": self.config.provider,
                "thinking": actual["thinkingLevel"], "cwd": str(self.config.cwd),
                "participant": self.config.participant, "pid": process.pid,
            })
            self.rpc("prompt", message=self.config.startup_prompt())
            with self.condition:
                done = self.condition.wait_for(
                    lambda: self.settled or process.poll() is not None, timeout=self.timeout)
            if not done or not self.settled or not self.opened or process.poll() is not None:
                raise RuntimeError("Agent did not establish its configured router binding")
            with self.mutex:
                if self.process is process and not self.stopping:
                    self._record(phase="running", detail="")
        except (OSError, RuntimeError, ValueError) as error:
            with self.mutex:
                # A late startup result must never stop or relabel a replacement.
                current = load_record(self.config)
                if current.get("pid") != process.pid:
                    return
                self.error = str(error)
            self.shutdown(expected=process)
            with self.mutex:
                if load_record(self.config).get("pid") == process.pid:
                    self._record(phase="failed", detail=self.error)

    def shutdown(self, *, expected=None):
        with self.mutex:
            process = self.process
            if not process or (expected is not None and process is not expected):
                return
            record = load_record(self.config)
            if (record.get("pid") != process.pid
                    or record.get("processStart") != process_start(process.pid)):
                self.error = "Process ownership changed; operator review required"
                return
            self.stopping = True
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if record["processStart"] == process_start(process.pid):
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.error = "Owned agent did not stop; lock retained, no replacement allowed"
        # Reader owns releasing the lifetime lock only after actual child exit.
        deadline = time.monotonic() + 1
        while (self.process is process and process.poll() is not None
               and time.monotonic() < deadline):
            time.sleep(0.01)


def configured_lifecycle(runtime: Path) -> AgentLifecycle | None:
    path = os.environ.get("WORKSPACE_AGENT_CONFIG")
    return AgentLifecycle(AgentConfig.load(Path(path), runtime)) if path else None
