"""Black-box pi-team checks. All worker processes are local deterministic fakes."""

import asyncio
import copy
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
CLI = ROOT / "src/automata/tools/pi-team/pi_team.py"
FAKE = ROOT / "tests/fixtures/pi_team/fake_worker.py"


def spec_for(tmp_path):
    cwd = tmp_path / "worker"
    cwd.mkdir()
    (cwd / "fake-worker.json").write_text("{}")
    return {
        "version": 1,
        "run_dir": str(tmp_path / "run"),
        "deadline_seconds": 20,
        "startup_timeout_seconds": 3,
        "shutdown_grace_seconds": 0.2,
        "callback": {"endpoint": "tcp://127.0.0.1:5555", "name": "fixture-team",
                     "recipient": "fixture-manager", "timeout_seconds": 0.2},
        "pi_command": [sys.executable, str(FAKE)],
        "workers": [{"id": "worker1", "cwd": str(cwd), "provider": "fake",
                     "model": "model", "thinking": "medium", "prompt": "PRIVATE_PROMPT"}],
    }


def invoke(*args, timeout=5):
    return subprocess.run([sys.executable, str(CLI), *args], capture_output=True,
                          text=True, timeout=timeout)


@pytest.mark.parametrize("case", [
    "duplicate-id", "relative-cwd", "missing-cwd", "empty-prompt", "missing-provider",
    "missing-thinking", "negative-deadline", "unbounded-deadline", "empty-workers",
    "nonlocal-callback", "bad-version", "empty-command", "invalid-id",
])
def test_invalid_full_spec_never_spawns_or_allocates_run(tmp_path, case):
    """Later invalid workers must not leave earlier workers running or dispatched."""
    spec = spec_for(tmp_path)
    second = copy.deepcopy(spec["workers"][0])
    second["id"] = "worker2"
    spec["workers"].append(second)
    if case == "duplicate-id":
        second["id"] = "worker1"
    elif case == "relative-cwd":
        second["cwd"] = "."
    elif case == "missing-cwd":
        second["cwd"] = str(tmp_path / "absent")
    elif case == "empty-prompt":
        second["prompt"] = ""
    elif case == "missing-provider":
        second.pop("provider")
    elif case == "missing-thinking":
        second.pop("thinking")
    elif case == "negative-deadline":
        spec["deadline_seconds"] = -1
    elif case == "unbounded-deadline":
        spec["deadline_seconds"] = 86401
    elif case == "empty-workers":
        spec["workers"] = []
    elif case == "nonlocal-callback":
        spec["callback"]["endpoint"] = "tcp://192.0.2.1:5555"
    elif case == "bad-version":
        spec["version"] = 2
    elif case == "empty-command":
        spec["pi_command"] = []
    elif case == "invalid-id":
        second["id"] = "../escape"
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    result = invoke("start", "--spec", str(path))
    assert result.returncode != 0
    # Require a validation diagnosis, not missing program/dependency false positives.
    assert "can't open file" not in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert not Path(spec["run_dir"]).exists()
    assert not list(tmp_path.rglob("fake-worker-trace.jsonl"))


def test_existing_run_is_never_overwritten(tmp_path):
    spec = spec_for(tmp_path)
    run = Path(spec["run_dir"])
    run.mkdir()
    sentinel = run / "state.json"
    sentinel.write_text('{"private":"existing evidence"}')
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    result = invoke("start", "--spec", str(path))
    assert result.returncode != 0
    assert sentinel.read_text() == '{"private":"existing evidence"}'
    assert not list(tmp_path.rglob("fake-worker-trace.jsonl"))


@pytest.fixture(scope="module")
def team():
    spec = importlib.util.spec_from_file_location("pi_team_integration", CLI)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeCallback:
    """Callback double models receipts, never uses a relay or model."""

    def __init__(self, *, probe_error=False, send_error=False):
        self.probe_error = probe_error
        self.send_error = send_error
        self.sent = []
        self.closed = False

    async def connect(self, config):
        return self

    async def probe(self, run):
        assert not list(run.parent.rglob("fake-worker-trace.jsonl"))
        if self.probe_error:
            raise TimeoutError("probe not acknowledged")

    async def send(self, value):
        self.sent.append(value)
        if self.send_error:
            raise TimeoutError("receipt uncertain")

    async def close(self):
        self.closed = True


def initialize(team, spec):
    spec = team.validate_spec(spec)
    run = Path(spec["run_dir"])
    run.mkdir(mode=0o700)
    (run / "workers").mkdir(mode=0o700)
    team.write_json(run / "spec.json", spec)
    team.write_json(run / "state.json", {
        "version": 1, "run_id": "fixture-run", "run_dir": str(run),
        "status": "starting", "created_at": time.time(),
        "deadline_at": time.time() + spec["deadline_seconds"], "timings": {},
        "workers": {w["id"]: {"id": w["id"], "status": "pending", "timings": {}}
                    for w in spec["workers"]},
    })
    return run


def supervise(team, run, callback=None):
    callback = callback or FakeCallback()
    asyncio.run(asyncio.wait_for(team.supervise(run, callback.connect), timeout=8))
    return json.loads((run / "state.json").read_text()), callback


def configure(spec, **config):
    cwd = Path(spec["workers"][0]["cwd"])
    (cwd / "fake-worker.json").write_text(json.dumps(config))


@pytest.mark.parametrize(("scenario", "status"), [
    ("success", "succeeded"), ("continuation", "succeeded"), ("noise", "succeeded"),
    ("reject", "failed"), ("handled", "failed"), ("error", "failed"),
    ("aborted", "failed"), ("length", "failed"), ("no-final", "failed"),
    ("exit", "failed"), ("wrong-id", "failed"),
])
def test_rpc_completion_semantics(team, tmp_path, scenario, status):
    spec = spec_for(tmp_path)
    spec["startup_timeout_seconds"] = 0.5
    configure(spec, scenario=scenario)
    run = initialize(team, spec)
    state, callback = supervise(team, run)
    assert state["status"] == status
    assert state["workers"]["worker1"]["status"] == status
    assert state["shutdown"] == "confirmed"
    assert callback.closed and len(callback.sent) == 1
    assert callback.sent[0]["status"] == status
    assert not team.identity_alive(state["workers"]["worker1"].get("identity"))
    if scenario in {"success", "continuation", "noise"}:
        result = json.loads((run / "workers/worker1.result.json").read_text())
        assert result["content"][0]["text"] == "PRIVATE_RESULT\u2028line\u2029paragraph"
    if scenario == "continuation":
        assert state["workers"]["worker1"]["timings"]["execution_seconds"] >= 0.25
    if scenario == "noise":
        assert (run / "workers/worker1.stderr.log").stat().st_size > 262144
        assert (run / "workers/worker1.rpc.jsonl").stat().st_size > 262144


@pytest.mark.parametrize("override", [
    {"model": {"provider": "wrong", "id": "model"}},
    {"model": {"provider": "fake", "id": "wrong"}},
    {"thinkingLevel": "low"}, {"sessionId": ""}, {"sessionFile": "/unowned/session"},
    {"isStreaming": True}, {"pendingMessageCount": 1}, {"messageCount": 1},
])
def test_effective_settings_mismatch_prevents_all_dispatch(team, tmp_path, override):
    spec = spec_for(tmp_path)
    configure(spec, state=override)
    state, _ = supervise(team, initialize(team, spec))
    assert state["status"] == "failed"
    trace = Path(spec["workers"][0]["cwd"]) / "fake-worker-trace.jsonl"
    traces = [json.loads(line) for line in trace.read_text().splitlines()]
    assert not any(t.get("command", {}).get("type") == "prompt" for t in traces)
    assert not team.identity_alive(state["workers"]["worker1"].get("identity"))


def test_callback_probe_failure_prevents_spawn(team, tmp_path):
    spec = spec_for(tmp_path)
    state, callback = supervise(team, initialize(team, spec), FakeCallback(probe_error=True))
    assert state["status"] == "failed"
    assert not list(tmp_path.rglob("fake-worker-trace.jsonl"))
    assert callback.closed


def test_notification_failure_retains_results_without_retry(team, tmp_path):
    spec = spec_for(tmp_path)
    run = initialize(team, spec)
    state, callback = supervise(team, run, FakeCallback(send_error=True))
    assert state["status"] == "succeeded"
    assert state["callback"]["notification"] == "uncertain"
    assert len(callback.sent) == 1
    assert (run / "workers/worker1.result.json").exists()


def test_compact_cli_views_readonly_private_and_no_model_use(team, tmp_path):
    spec = spec_for(tmp_path)
    run = initialize(team, spec)
    supervise(team, run)
    trace = Path(spec["workers"][0]["cwd"]) / "fake-worker-trace.jsonl"
    before = {path: (path.stat().st_mtime_ns, path.read_bytes())
              for path in run.rglob("*") if path.is_file()}
    commands = trace.read_bytes()
    for command in ("status", "watch", "results"):
        result = invoke(command, "--run", str(run))
        assert result.returncode == 0, result.stderr
        assert "PRIVATE_PROMPT" not in result.stdout
        assert "PRIVATE_RESULT" not in result.stdout
        assert "pi_command" not in result.stdout
        assert json.loads(result.stdout)["status"] == "succeeded"
    assert trace.read_bytes() == commands
    assert before == {path: (path.stat().st_mtime_ns, path.read_bytes())
                      for path in run.rglob("*") if path.is_file()}
    full = invoke("results", "--run", str(run), "--full")
    assert "PRIVATE_RESULT" in full.stdout


def test_concurrent_start_and_all_ready_before_dispatch(team, tmp_path):
    spec = spec_for(tmp_path)
    configure(spec, startup_delay=0.25)
    second_cwd = tmp_path / "worker2"
    second_cwd.mkdir()
    (second_cwd / "fake-worker.json").write_text('{"startup_delay":0.25}')
    spec["workers"].append({**spec["workers"][0], "id": "worker2", "cwd": str(second_cwd)})
    state, _ = supervise(team, initialize(team, spec))
    assert state["status"] == "succeeded"
    traces = [[json.loads(line) for line in
               (Path(w["cwd"]) / "fake-worker-trace.jsonl").read_text().splitlines()]
              for w in spec["workers"]]
    spawns = [next(t["at"] for t in trace if t["event"] == "spawn") for trace in traces]
    assert max(spawns) - min(spawns) < 0.2
    ready_commands = [t["at"] for trace in traces for t in trace
                      if t.get("command", {}).get("type") == "set_auto_retry"]
    prompts = [t["at"] for trace in traces for t in trace
               if t.get("command", {}).get("type") == "prompt"]
    assert min(prompts) >= max(ready_commands)


def test_partial_startup_failure_closes_ready_sibling_without_dispatch(team, tmp_path):
    spec = spec_for(tmp_path)
    second_cwd = tmp_path / "worker2"
    second_cwd.mkdir()
    (second_cwd / "fake-worker.json").write_text('{"startup_exit":true}')
    spec["workers"].append({**spec["workers"][0], "id": "worker2", "cwd": str(second_cwd)})
    state, _ = supervise(team, initialize(team, spec))
    assert state["status"] == "failed" and state["shutdown"] == "confirmed"
    for worker in state["workers"].values():
        assert not team.identity_alive(worker.get("identity"))
    for trace in tmp_path.rglob("fake-worker-trace.jsonl"):
        assert not any(json.loads(line).get("command", {}).get("type") == "prompt"
                       for line in trace.read_text().splitlines())


@pytest.mark.parametrize("scenario", ["descendant", "orphan-descendant"])
def test_deadline_accounts_for_active_descendants(team, tmp_path, scenario):
    spec = spec_for(tmp_path)
    spec["deadline_seconds"] = 0.35
    configure(spec, scenario=scenario)
    run = initialize(team, spec)
    descendant = None
    try:
        state, _ = supervise(team, run)
        trace = Path(spec["workers"][0]["cwd"]) / "fake-worker-trace.jsonl"
        descendant = next(json.loads(line)["child_pid"] for line in trace.read_text().splitlines()
                          if json.loads(line)["event"] == "descendant")
        assert state["status"] in {"timed_out", "failed"}
        assert state["shutdown"] == "confirmed"
        assert team.process_identity(descendant) is None
    finally:
        # The fake is ours; ensure a failing lifecycle assertion cannot leave it running.
        if descendant and team.process_identity(descendant):
            os.kill(descendant, signal.SIGKILL)


def test_watch_detaches_without_stopping_owned_worker(team, tmp_path):
    spec = spec_for(tmp_path)
    configure(spec, scenario="hang")
    run = initialize(team, spec)

    async def scenario():
        task = asyncio.create_task(team.supervise(run, FakeCallback().connect))
        watcher = None
        try:
            async with asyncio.timeout(4):
                while True:
                    state = team.read_json(run / "state.json")
                    if state["workers"]["worker1"]["status"] == "running":
                        break
                    await asyncio.sleep(0.01)
                watcher = await asyncio.create_subprocess_exec(
                    sys.executable, str(CLI), "watch", "--run", str(run),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                first = json.loads(await watcher.stdout.readline())
                assert first["status"] == "running"
                watcher.send_signal(signal.SIGINT)
                await watcher.wait()
                assert watcher.returncode == 130
                state = team.read_json(run / "state.json")
                assert team.identity_alive(state["workers"]["worker1"]["identity"])
                assert not (run / "stop-request.json").exists()
        finally:
            if watcher and watcher.returncode is None:
                watcher.kill()
                await watcher.wait()
            team.write_json(run / "stop-request.json", {"reason": "test_finished"})
            await asyncio.wait_for(task, 3)
    asyncio.run(scenario())
    final = team.read_json(run / "state.json")
    assert final["status"] == "stopped" and final["shutdown"] == "confirmed"


@pytest.mark.parametrize("mode", ["death", "suspended-stop", "lease-only"])
def test_separate_watchdog_survives_supervisor_death_and_stops_worker(team, tmp_path, mode):
    spec = spec_for(tmp_path)
    run = initialize(team, spec)
    owner = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                             start_new_session=True)
    worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                              start_new_session=True)
    watchdog = None
    try:
        state = team.read_json(run / "state.json")
        state["supervisor"] = team.process_identity(owner.pid)
        if mode == "lease-only":
            team.write_json(run / "workers/worker1.lease.json", {
                "identity": team.process_identity(worker.pid), "ownership_token": None})
        else:
            state["workers"]["worker1"].update(
                status="running", identity=team.process_identity(worker.pid))
        team.write_json(run / "state.json", state)
        team.write_json(run / "launch-ready.json", {"ready": True})
        watchdog = subprocess.Popen(
            [sys.executable, str(CLI), "_watchdog", "--run", str(run)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        if mode == "suspended-stop":
            owner.send_signal(signal.SIGSTOP)
            team.write_json(run / "stop-request.json", {"reason": "user_requested"})
        else:
            owner.kill()
            owner.wait(timeout=2)
        stdout, stderr = watchdog.communicate(timeout=7)
        assert watchdog.returncode == 0, (stdout, stderr)
        worker.wait(timeout=2)
        evidence = team.read_json(run / "watchdog.json")
        assert evidence["status"] == "triggered"
        expected = "stop_requested" if mode == "suspended-stop" else "supervisor_died"
        assert evidence["reason"] == expected
        assert evidence["shutdown"] == "confirmed"
        assert not team.identity_alive(state["supervisor"])
        assert evidence["notification"] in {"uncertain", "relay_accepted"}
        assert team.status(run)["status"] == "failed"
    finally:
        for process in (watchdog, worker, owner):
            if process and process.poll() is None:
                process.kill()
                process.wait(timeout=2)


def test_watchdog_cancels_when_completed_evidence_exists(team, tmp_path):
    spec = spec_for(tmp_path)
    run = initialize(team, spec)
    state = team.read_json(run / "state.json")
    state.update(status="succeeded", shutdown="confirmed",
                 supervisor={"pid": 99999999, "pgrp": 99999999,
                             "start_ticks": "1", "boot_id": "absent"})
    state["callback"] = {"notification": "relay_accepted"}
    team.write_json(run / "state.json", state)
    asyncio.run(asyncio.wait_for(team.watchdog(run), 2))
    evidence = team.read_json(run / "watchdog.json")
    assert evidence["status"] == "complete"
    assert "notification" not in evidence

