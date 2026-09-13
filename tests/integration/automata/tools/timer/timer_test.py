from __future__ import annotations

import importlib.util
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import ModuleType

import pytest

TIMER_PATH = Path(__file__).parents[5] / "src" / "automata" / "tools" / "timer" / "timer.py"


def load_timer_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("automata_timer_tool", TIMER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_timer_uses_external_repo_local_state_by_default() -> None:
    timer = load_timer_module()

    assert timer.DEFAULT_STATE_DIR == Path(".agents/var/skills/automata-timer")
    assert timer.DEFAULT_STATE_DIR not in TIMER_PATH.parents


def test_timer_executes_due_job_and_records_log(tmp_path: Path) -> None:
    timer = load_timer_module()
    state_dir = tmp_path / "state"
    job = timer.create_job(
        state_dir=state_dir,
        command=[sys.executable, "-c", "print('timer-ok')"],
        schedule_kind="after",
        next_run_at=timer.utc_now(),
        name="smoke",
    )

    assert timer.execute_due_job(state_dir, job["id"])

    completed = timer.load_job(state_dir, job["id"])
    assert completed["status"] == "completed"
    assert completed["run_count"] == 1
    assert completed["last_exit_code"] == 0
    assert completed["worker_pid"] is None
    log_path = state_dir / completed["log_files"][-1]
    assert "timer-ok" in log_path.read_text()


def test_timer_recurring_job_returns_to_pending(tmp_path: Path) -> None:
    timer = load_timer_module()
    state_dir = tmp_path / "state"
    job = timer.create_job(
        state_dir=state_dir,
        command=[sys.executable, "-c", "pass"],
        schedule_kind="every",
        next_run_at=timer.utc_now(),
        name=None,
        interval_seconds=60,
        max_runs=2,
    )

    assert timer.execute_due_job(state_dir, job["id"])

    pending = timer.load_job(state_dir, job["id"])
    assert pending["status"] == "pending"
    assert pending["run_count"] == 1
    assert pending["next_run_at"] is not None


def test_timer_cleanup_removes_only_terminal_jobs(tmp_path: Path) -> None:
    timer = load_timer_module()
    state_dir = tmp_path / "state"
    terminal = timer.create_job(
        state_dir=state_dir,
        command=[sys.executable, "-c", "pass"],
        schedule_kind="after",
        next_run_at=timer.utc_now(),
        name="terminal",
    )
    pending = timer.create_job(
        state_dir=state_dir,
        command=[sys.executable, "-c", "pass"],
        schedule_kind="after",
        next_run_at=timer.utc_now(),
        name="pending",
    )
    assert timer.execute_due_job(state_dir, terminal["id"])

    timer.cleanup(all_terminal=True, state_dir=state_dir)

    assert not timer.job_path(state_dir, terminal["id"]).exists()
    assert timer.job_path(state_dir, pending["id"]).exists()


def make_job(timer: ModuleType, state: Path, name: str = "one") -> dict:
    return timer.create_job(
        state_dir=state,
        command=[sys.executable, "-c", "pass"],
        schedule_kind="after",
        next_run_at=timer.utc_now(),
        name=name,
    )


def test_targeted_cleanup_and_selector_validation(tmp_path: Path) -> None:
    timer = load_timer_module()
    job = make_job(timer, tmp_path)
    with pytest.raises(ValueError, match="not terminal"):
        timer.cleanup(job="one", state_dir=tmp_path)
    for kwargs in (
        {"job": "one", "all_terminal": True},
        {"job": "one", "older_than": "7d"},
        {"all_terminal": True, "older_than": "7d"},
    ):
        with pytest.raises(ValueError, match="one selector"):
            timer.cleanup(state_dir=tmp_path, **kwargs)
    timer.execute_due_job(tmp_path, job["id"])
    timer.cleanup(job="one", state_dir=tmp_path)
    assert not timer.job_path(tmp_path, job["id"]).exists()
    assert not timer.job_log_dir(tmp_path, job["id"]).exists()
    assert not timer.lock_path(tmp_path, job["id"]).exists()
    assert not timer.execute_due_job(tmp_path, job["id"])


def test_cleanup_refuses_leased_terminal_and_batch_preserves_it(tmp_path: Path) -> None:
    timer = load_timer_module()
    job = make_job(timer, tmp_path)
    timer.cancel(job["id"], state_dir=tmp_path)
    with timer.active_job(tmp_path, job["id"]):
        with pytest.raises(ValueError, match="active worker"):
            timer.cleanup(job=job["id"], state_dir=tmp_path)
        timer.cleanup(all_terminal=True, state_dir=tmp_path)
        assert timer.job_path(tmp_path, job["id"]).exists()
    timer.cleanup(job=job["id"], state_dir=tmp_path)


def test_cancel_between_reservation_and_launch_does_not_execute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timer = load_timer_module()
    job = make_job(timer, tmp_path)
    original = timer.save_job
    reserved = threading.Event()
    canceled = threading.Event()

    def save(state: Path, item: dict) -> None:
        original(state, item)
        if item["status"] == "running" and item["command_pid"] is None:
            reserved.set()

    monkeypatch.setattr(timer, "save_job", save)
    original_open = Path.open

    def gated_open(path: Path, *args, **kwargs):
        if path.name == "run-001.log" and args == ("ab",):
            assert canceled.wait(5)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", gated_open)
    calls = []
    monkeypatch.setattr(timer.subprocess, "Popen", lambda *a, **k: calls.append(a))
    thread = threading.Thread(target=timer.execute_due_job, args=(tmp_path, job["id"]))
    thread.start()
    try:
        assert reserved.wait(5)
        timer.cancel(job["id"], state_dir=tmp_path)
    finally:
        canceled.set()
        thread.join(5)
    assert not thread.is_alive()
    assert calls == []
    assert timer.load_job(tmp_path, job["id"])["status"] == "canceled"


def test_cleanup_refuses_known_live_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    timer = load_timer_module()
    job = make_job(timer, tmp_path)
    job.update(status="canceled", command_pid=123)
    timer.save_job(tmp_path, job)
    monkeypatch.setattr(timer, "process_group_alive", lambda pid: pid == 123)
    with pytest.raises(ValueError, match="shutdown is not confirmed"):
        timer.cleanup(job=job["id"], state_dir=tmp_path)


def test_cancel_preserves_unconfirmed_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    timer = load_timer_module()
    job = make_job(timer, tmp_path)
    job.update(status="running", command_pid=123, command_identity="old")
    timer.save_job(tmp_path, job)
    monkeypatch.setattr(timer, "process_identity", lambda pid: "new")
    monkeypatch.setattr(timer, "process_group_alive", lambda pid: pid == 123)
    monkeypatch.setattr(timer, "kill_pid", lambda *a, **k: pytest.fail("recycled PID signaled"))
    timer.cancel(job["id"], state_dir=tmp_path)
    item = timer.load_job(tmp_path, job["id"])
    assert item["status"] == "canceling"
    assert item["command_pid"] == 123


def test_live_cancellation_then_cli_cleanup(tmp_path: Path) -> None:
    timer = load_timer_module()
    ready = tmp_path / "ready"
    job = timer.create_job(
        state_dir=tmp_path,
        command=[
            sys.executable,
            "-c",
            f"from pathlib import Path; import time; Path({str(ready)!r}).touch(); time.sleep(60)",
        ],
        schedule_kind="after",
        next_run_at=timer.utc_now(),
        name="live",
    )
    process = subprocess.Popen(
        [sys.executable, str(TIMER_PATH), "worker", job["id"], "--state-dir", str(tmp_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            assert process.poll() is None
            time.sleep(0.01)
        assert ready.exists()
        with pytest.raises(ValueError, match="not terminal"):
            timer.cleanup(job="live", state_dir=tmp_path)
        timer.cancel("live", state_dir=tmp_path)
        _, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
        assert timer.load_job(tmp_path, job["id"])["status"] == "canceled"
        result = subprocess.run(
            [sys.executable, str(TIMER_PATH), "cleanup", "live", "--state-dir", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        assert "terminal jobs removed: 1" in result.stdout
        assert not timer.job_path(tmp_path, job["id"]).exists()
    finally:
        if process.poll() is None:
            item = timer.load_job(tmp_path, job["id"])
            if isinstance(item.get("command_pid"), int):
                timer.kill_pid(item["command_pid"], process_group=True)
            process.kill()
            process.wait(timeout=10)


def test_cleanup_age_default_and_ambiguous_names(tmp_path: Path) -> None:
    timer = load_timer_module()
    first = make_job(timer, tmp_path, "duplicate")
    second = make_job(timer, tmp_path, "duplicate")
    for item in (first, second):
        timer.cancel(item["id"], state_dir=tmp_path)
    with pytest.raises(ValueError, match="ambiguous"):
        timer.cleanup(job="duplicate", state_dir=tmp_path)
    timer.cleanup(state_dir=tmp_path)
    assert len(timer.list_jobs(tmp_path)) == 2
    old = timer.load_job(tmp_path, first["id"])
    old["finished_at"] = "2000-01-01T00:00:00+00:00"
    timer.save_job(tmp_path, old)
    timer.cleanup(state_dir=tmp_path)
    assert [item["id"] for item in timer.list_jobs(tmp_path)] == [second["id"]]
