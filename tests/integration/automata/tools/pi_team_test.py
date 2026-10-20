"""Black-box thin RPC checks. Local deterministic fake only, no model/relay."""

import concurrent.futures
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


def invoke(*args, timeout=10, cli=CLI):
    return subprocess.run(
        [sys.executable, str(cli), *map(str, args)], capture_output=True, text=True, timeout=timeout
    )


def decoded(result):
    assert result.returncode == 0, (result.stdout, result.stderr)
    return json.loads(result.stdout)


def spec_for(tmp_path, **config):
    cwd = tmp_path / "worker"
    cwd.mkdir()
    (cwd / "fake-worker.json").write_text(json.dumps(config))
    return {
        "version": 2,
        "run_dir": str(tmp_path / "run"),
        "cwd": str(cwd),
        "provider": "fake",
        "model": "model",
        "thinking": "medium",
        "resources": ["--no-approve", "--offline"],
        "persist_session": True,
        "pi_command": [sys.executable, str(FAKE)],
        "startup_timeout_seconds": 2,
        "shutdown_grace_seconds": 0.1,
        "storage": {
            "segment_bytes": 65536,
            "max_segments": 3,
            "max_record_bytes": 8192,
            "max_read_bytes": 262144,
            "max_read_records": 1000,
        },
    }


@pytest.fixture
def worker(tmp_path):
    spec = spec_for(tmp_path)
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    run = Path(spec["run_dir"])
    opened = decoded(invoke("create", "--spec", path))
    assert opened["status"] == "open", opened
    try:
        yield run
    finally:
        stopped = decoded(invoke("stop", "--worker", run))
        assert stopped["status"] == "closed"
        assert not stopped["worker_alive"] and not stopped["controller_alive"]


def rpc(run, command, *, timeout=2, send_only=False):
    path = run / ("command-" + str(time.monotonic_ns()) + ".json")
    path.write_text(json.dumps(command))
    args = ["rpc", "--worker", run, "--command", path, "--timeout", timeout]
    if send_only:
        args.append("--send-only")
    try:
        return invoke(*args)
    finally:
        path.unlink()


def events(run, cursor=0, limit=1000, max_bytes=262144):
    return decoded(
        invoke(
            "events",
            "--worker",
            run,
            "--cursor",
            cursor,
            "--limit",
            limit,
            "--max-bytes",
            max_bytes,
        )
    )


def traces(run):
    cwd = Path(json.loads((run / "spec.json").read_text())["cwd"])
    return [
        json.loads(line)
        for line in (cwd / "fake-worker-trace.jsonl").read_bytes().split(b"\n")
        if line
    ]


def test_idle_create_multiple_assignments_and_explicit_stop(worker):
    assert [t["command"]["type"] for t in traces(worker) if t["event"] == "command"] == [
        "get_state"
    ]
    for number in range(2):
        response = decoded(rpc(worker, {"type": "prompt", "message": f"PRIVATE_{number}"}))
        assert response["data"]["disposition"] == "started"
        state = decoded(invoke("status", "--worker", worker))
        assert state["status"] == "open" and state["worker_alive"]
    records = [json.loads(r["raw"]) for r in events(worker)["records"] if r["stream"] == "stdout"]
    assert sum(r["type"] == "agent_settled" for r in records) == 2
    assert any("\u2028" in json.dumps(r, ensure_ascii=False) for r in records)
    assert decoded(rpc(worker, {"type": "get_state"}))["success"]
    assert "PRIVATE" not in invoke("status", "--worker", worker).stdout


def test_raw_failure_unknown_fields_steer_followup_abort_ui(worker):
    response = decoded(rpc(worker, {"type": "fail", "id": "raw-fail"}))
    assert response == {
        "type": "response",
        "id": "raw-fail",
        "command": "fail",
        "success": False,
        "error": "PRIVATE_ERROR",
        "unknown": 42,
    }
    echo = decoded(rpc(worker, {"type": "echo", "futureInput": ["opaque"]}))
    assert echo["futureField"] == {"opaque": [1, 2]}
    assert echo["data"]["futureInput"] == ["opaque"]
    for kind in ("steer", "follow_up", "abort"):
        assert decoded(rpc(worker, {"type": kind, "message": "private"}))["command"] == kind
    ui = decoded(
        rpc(
            worker,
            {"type": "extension_ui_response", "id": "dialog", "confirmed": True},
            send_only=True,
        )
    )
    assert ui["transport"] == "stdin_drained" and ui["pi_acknowledgement"] is False
    assert rpc(worker, {"type": "extension_ui_response", "id": "wrong-mode"}).returncode == 1
    assert decoded(invoke("status", "--worker", worker))["worker_alive"]


def test_out_of_order_response_correlation(worker):
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        slow = pool.submit(rpc, worker, {"type": "delay", "id": "slow", "seconds": 0.3})
        time.sleep(0.03)
        fast = pool.submit(rpc, worker, {"type": "echo", "id": "fast"})
        assert decoded(fast.result())["id"] == "fast"
        assert decoded(slow.result())["id"] == "slow"
    responses = [json.loads(r["raw"]) for r in events(worker)["records"] if r["stream"] == "stdout"]
    ids = [r.get("id") for r in responses if r["type"] == "response"]
    assert ids.index("fast") < ids.index("slow")


def test_timeout_late_reply_no_resend_and_duplicate_rejection(worker):
    command = {"type": "delay", "id": "uncertain", "seconds": 0.4}
    result = rpc(worker, command, timeout=0.03)
    assert result.returncode == 1
    assert json.loads(result.stdout)["transport_error"] == "response_timeout_outcome_unknown"
    duplicate = rpc(worker, command)
    assert duplicate.returncode == 1 and "unresolved" in duplicate.stdout
    time.sleep(0.45)
    records = [json.loads(r["raw"]) for r in events(worker)["records"] if r["stream"] == "stdout"]
    assert any(r.get("id") == "uncertain" and r.get("data", {}).get("late") for r in records)
    sent = [t for t in traces(worker) if t.get("command", {}).get("id") == "uncertain"]
    assert len(sent) == 1


def test_flood_rotates_stdout_and_stderr_within_encoded_budget(worker):
    assert decoded(rpc(worker, {"type": "flood", "count": 500, "size": 1000}))["success"]
    state = decoded(invoke("status", "--worker", worker))
    assert state["worker_alive"]
    paths = list((worker / "capture").glob("*.jsonl"))
    assert len(paths) <= 3
    assert all(p.stat().st_size <= 65536 for p in paths)
    assert sum(p.stat().st_size for p in paths) <= 3 * 65536
    result = events(worker)
    assert result["gap"] and result["earliest_cursor"] > 1
    assert {r["stream"] for r in result["records"]} == {"stdout", "stderr"}


def test_oversized_record_visible_without_stopping_worker(worker):
    result = rpc(worker, {"type": "oversize", "size": 1000000}, timeout=1)
    # The reply may already arrive in the same drain chunk. Raw reply + stderr capture facts,
    # or explicit unknown transport outcome; neither claims complete captured evidence.
    if result.returncode == 0:
        assert "capture" in result.stderr
    else:
        assert "capture_loss" in result.stdout
    state = decoded(invoke("status", "--worker", worker))
    assert state["worker_alive"] and state["capture"]["lost_records"] == 1
    assert state["capture"]["capture_error"] == "oversized_record"
    assert events(worker)["gap"]
    assert decoded(rpc(worker, {"type": "get_state"}))["success"]


def test_controller_loss_explicit_orphan_cleanup(worker):
    state = decoded(invoke("status", "--worker", worker))
    os.kill(state["controller"]["pid"], signal.SIGKILL)
    time.sleep(0.1)
    missing = decoded(invoke("status", "--worker", worker))
    assert missing["status"] == "controller_unavailable"
    assert rpc(worker, {"type": "get_state"}).returncode == 1
    assert events(worker)["controller_unavailable"]
    stopped = decoded(invoke("stop", "--worker", worker))
    assert stopped["status"] == "closed" and not stopped["worker_alive"]


def test_private_permissions_and_no_unbounded_request_ledger(worker):
    assert worker.stat().st_mode & 0o777 == 0o700
    for path in worker.rglob("*"):
        if path.is_file():
            assert path.stat().st_mode & 0o077 == 0
    assert not (worker / "requests").exists()


def test_invalid_spec_allocates_nothing_and_existing_run_never_overwritten(tmp_path):
    spec = spec_for(tmp_path)
    spec["storage"].pop("max_segments")
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    assert invoke("create", "--spec", path).returncode == 1
    assert not Path(spec["run_dir"]).exists()
    spec["storage"]["max_segments"] = 3
    path.write_text(json.dumps(spec))
    run = Path(spec["run_dir"])
    run.mkdir()
    sentinel = run / "sentinel"
    sentinel.write_text("existing")
    assert invoke("create", "--spec", path).returncode == 1
    assert sentinel.read_text() == "existing" and list(run.iterdir()) == [sentinel]


def test_settings_mismatch_never_dispatches_and_cleans_up(tmp_path):
    spec = spec_for(tmp_path, state={"thinkingLevel": "low"})
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    state = decoded(invoke("create", "--spec", path))
    run = Path(spec["run_dir"])
    try:
        assert (
            state["status"] == "closed"
            and state["startup_error"] == "effective_settings_unverified"
        )
        assert not state["worker_alive"]
        assert all(t.get("command", {}).get("type") != "prompt" for t in traces(run))
    finally:
        invoke("stop", "--worker", run)


def test_copied_tool_help_and_fake_lifecycle(tmp_path):
    import shutil

    copied = tmp_path / "installed" / "pi-team"
    shutil.copytree(CLI.parent, copied, ignore=shutil.ignore_patterns("__pycache__"))
    cli = copied / "pi_team.py"
    assert "create" in invoke("--help", cli=cli).stdout
    spec = spec_for(tmp_path)
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    run = Path(spec["run_dir"])
    try:
        assert decoded(invoke("create", "--spec", path, cli=cli))["status"] == "open"
        assert decoded(rpc(run, {"type": "prompt", "message": "fake only"}))["success"]
    finally:
        assert decoded(invoke("stop", "--worker", run, cli=cli))["status"] == "closed"
