"""Thin RPC validation, capture bounds and process ownership (model-free)."""

import asyncio
import importlib.util
import json
import os
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[4]
TOOL = ROOT / "src/automata/tools/pi-team/pi_team.py"


@pytest.fixture(scope="module")
def team():
    spec = importlib.util.spec_from_file_location("pi_team_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def limits():
    return {
        "segment_bytes": 8192,
        "max_segments": 2,
        "max_record_bytes": 1024,
        "max_read_bytes": 16384,
        "max_read_records": 100,
    }


@pytest.fixture
def valid_spec(tmp_path, limits):
    return {
        "version": 2,
        "run_dir": str(tmp_path / "run"),
        "cwd": str(tmp_path),
        "provider": "fake",
        "model": "model",
        "thinking": "medium",
        "resources": [],
        "persist_session": True,
        "storage": limits,
        "pi_command": [sys.executable, "fake-worker.py"],
    }


def test_validate_without_side_effects(team, valid_spec):
    assert team.validate_spec(valid_spec)["version"] == 2
    assert not Path(valid_spec["run_dir"]).exists()


@pytest.mark.parametrize(
    "field", ["provider", "model", "thinking", "resources", "storage", "persist_session"]
)
def test_explicit_choices_required(team, valid_spec, field):
    valid_spec.pop(field)
    with pytest.raises(team.TeamError):
        team.validate_spec(valid_spec)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, -1, 0])
def test_bad_timeouts(team, valid_spec, value):
    valid_spec["startup_timeout_seconds"] = value
    with pytest.raises(team.TeamError):
        team.validate_spec(valid_spec)


@pytest.mark.parametrize(
    "args", [["initial prompt"], ["--session", "existing"], ["--mode", "print"], ["--extension"]]
)
def test_resources_cannot_override_io_or_inject_prompt(team, valid_spec, args):
    valid_spec["resources"] = args
    with pytest.raises(team.TeamError):
        team.validate_spec(valid_spec)


@pytest.mark.parametrize("source_limit", [1024, 8192])
def test_all_retained_records_fit_configured_read_ceiling(team, valid_spec, source_limit):
    valid_spec["storage"].update(
        max_read_bytes=100, max_record_bytes=source_limit, segment_bytes=65536
    )
    with pytest.raises(team.TeamError, match="read_ceiling_too_small"):
        team.validate_spec(valid_spec)


def test_old_batch_spec_rejected(team):
    with pytest.raises(team.TeamError, match="version_2"):
        team.validate_spec({"version": 1, "workers": []})


def test_stale_identity_never_signals(team, monkeypatch):
    identity = team.process_identity(os.getpid())
    called = []
    monkeypatch.setattr(team.os, "killpg", lambda *args: called.append(args))
    for stale in ({**identity, "start_ticks": "0"}, {**identity, "boot_id": "old-boot"}):
        assert not team.identity_alive(stale)
        assert not team.signal_owned(stale, signal.SIGKILL)
    assert not called


def test_private_atomic_json(team, tmp_path):
    path = tmp_path / "state.json"
    team.write_json(path, {"private": "secret"})
    assert path.stat().st_mode & 0o777 == 0o600
    assert team.read_json(path) == {"private": "secret"}
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("socket_exists", [False, True])
def test_endpoint_cleanup_removes_directory_even_when_socket_already_missing(
    team, tmp_path, socket_exists
):
    directory = tmp_path / "private-endpoint"
    directory.mkdir(mode=0o700)
    path = directory / "io.sock"
    if socket_exists:
        path.touch(mode=0o600)
    team.remove_endpoint(str(path))
    assert not directory.exists()
    team.remove_endpoint(str(path))  # Idempotent cleanup must not recreate anything.


def test_capture_preserves_original_json_and_unicode(team, tmp_path, limits):
    capture = team.Capture(tmp_path / "capture", limits)
    raw = '{ "type":"unknown", "opaque":"a\u2028b\u2029c", "future":[1] }'.encode()
    capture.append("stdout", raw)
    capture.append("stderr", b"\xff\x00diagnostic")
    result = capture.read(0, 100, 16384)
    assert result["records"][0]["raw"].encode() == raw
    assert bytes.fromhex(result["records"][1]["raw"]) == b"\xff\x00diagnostic"
    assert result["cursor"] == 2 and not result["gap"]


def test_rotation_bounds_encoded_storage_and_exposes_expiry(team, tmp_path, limits):
    capture = team.Capture(tmp_path / "capture", limits)
    # ASCII escaping can expand a source record sixfold; count actual bytes on disk.
    raw = json.dumps({"text": "\u0000" * 100}, ensure_ascii=False).encode()
    for _ in range(100):
        capture.append("stdout", raw)
        paths = list(capture.directory.glob("*.jsonl"))
        assert len(paths) <= limits["max_segments"]
        assert all(p.stat().st_size <= limits["segment_bytes"] for p in paths)
        assert sum(p.stat().st_size for p in paths) <= 16384
    result = capture.read(0, 100, 16384)
    assert result["gap"] and result["earliest_cursor"] > 1
    cursors = [entry["cursor"] for entry in result["records"]]
    assert cursors == sorted(set(cursors))


def test_worst_case_escaping_envelope_and_lf_fit_accepted_boundary(team, valid_spec):
    limits = valid_spec["storage"]
    source_limit = limits["max_record_bytes"]
    encoded_ceiling = 6 * source_limit + 1024
    limits.update(segment_bytes=encoded_ceiling, max_read_bytes=encoded_ceiling)
    team.validate_spec(valid_spec)
    capture = team.Capture(Path(valid_spec["run_dir"]).parent / "capture", limits)
    # Literal DEL is valid JSON string content: one source byte expands to six
    # ASCII bytes (\\u007f) inside the raw field of the capture envelope.
    prefix, suffix = b'{"value":"', b'"}'
    raw = prefix + b"\x7f" * (source_limit - len(prefix) - len(suffix)) + suffix
    assert len(raw) == source_limit
    assert len(json.loads(raw)["value"]) == source_limit - len(prefix) - len(suffix)
    capture.append("stdout", raw)
    path = next(capture.directory.glob("*.jsonl"))
    actual_encoded_size = path.stat().st_size
    assert source_limit * 5 < actual_encoded_size <= encoded_ceiling
    assert path.read_bytes().endswith(b"\n")
    blocked = capture.read(0, 100, actual_encoded_size - 1)
    assert blocked["records"] == [] and blocked["cursor"] == 0
    assert blocked["blocked"]["required_bytes"] == actual_encoded_size
    exact = capture.read(0, 100, actual_encoded_size)
    assert exact["read_bytes"] == actual_encoded_size
    assert exact["records"][0]["raw"].encode() == raw
    assert exact["blocked"] is None and not exact["gap"]


def test_capture_count_byte_limits_no_skip(team, tmp_path, limits):
    capture = team.Capture(tmp_path / "capture", limits)
    for _ in range(3):
        capture.append("stdout", b'{"type":"event"}')
    blocked = capture.read(0, 100, 1)
    assert blocked["cursor"] == 0 and not blocked["records"]
    assert blocked["blocked"]["cursor"] == 1
    first = capture.read(0, 1, 16384)
    assert len(first["records"]) == 1 and first["cursor"] == 1
    assert capture.read(1, 100, 16384)["cursor"] == 3


def test_oversize_visible_no_partial_payload(team, tmp_path, limits):
    capture = team.Capture(tmp_path / "capture", limits)
    capture.append("stdout", b"x" * 1025)
    capture.append("stdout", b"{}")
    result = capture.read(0, 100, 16384)
    assert result["lost_records"] == 1 and result["lost_bytes"] == 1025
    assert result["capture_error"] == "oversized_record" and result["gap"]
    assert [r["cursor"] for r in result["records"]] == [2]
    assert capture.read(1, 100, 16384)["records"][0]["cursor"] == 2


def test_partial_trailing_frame_read_recovery(team, tmp_path, limits):
    capture = team.Capture(tmp_path / "capture", limits)
    capture.append("stdout", b"{}")
    path = next(capture.directory.glob("*.jsonl"))
    with path.open("ab") as stream:
        stream.write(b'{"cursor":2')
    recovered = team.Capture(capture.directory, limits)
    result = recovered.read(0, 100, 16384)
    assert result["partial_tail"] and len(result["records"]) == 1


def test_disk_failure_latches_and_drain_accounting_continues(team, tmp_path, limits, monkeypatch):
    capture = team.Capture(tmp_path / "capture", limits)

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(team.os, "open", fail)
    assert capture.append("stdout", b"{}") is None
    assert capture.append("stderr", b"more") is None
    assert capture.facts()["capture_error"] == "storage_io_error"
    assert capture.lost_records == 2 and capture.lost_bytes == 6
    capture.loss(10000, "oversized_record")
    assert capture.error == "storage_io_error"  # Cannot accidentally re-enable writes.
    result = capture.read(0, 100, 16384)
    assert result["gap"] and result["capture_error"] == "storage_io_error"


def controller_for(team, valid_spec):
    run = Path(valid_spec["run_dir"])
    run.mkdir(mode=0o700)
    team.write_json(run / "spec.json", valid_spec)
    team.write_json(run / "state.json", {"status": "open", "ownership_token": "test"})
    return team.Controller(run)


def test_bounded_pending_and_ambiguous_ids_late_response_frees_slot(team, valid_spec, monkeypatch):
    async def scenario():
        owner = controller_for(team, valid_spec)
        sent = []

        class Stdin:
            def write(self, value):
                sent.append(json.loads(value))

            async def drain(self):
                pass

        owner.process = SimpleNamespace(stdin=Stdin(), returncode=None)
        monkeypatch.setattr(team, "MAX_OUTSTANDING", 2)
        for request_id in ("first", "second"):
            result = await owner.rpc({"id": request_id, "type": "prompt"}, 0.001)
            assert result["transport_error"] == "response_timeout_outcome_unknown"
        assert owner.pending == {"first": None, "second": None}
        with pytest.raises(team.TeamError, match="unresolved"):
            await owner.rpc({"id": "first", "type": "prompt"}, 1)
        with pytest.raises(team.TeamError, match="outstanding_request_limit"):
            await owner.rpc({"id": "third", "type": "prompt"}, 1)
        assert len(sent) == 2
        await owner.record(b'{"type":"response","id":"first","success":true}')
        assert owner.pending == {"second": None}
        assert owner.capture.read(0, 100, 16384)["records"][0]["stream"] == "stdout"
        third = await owner.rpc({"id": "third", "type": "prompt"}, 0.001)
        assert "timeout" in third["transport_error"] and len(owner.pending) == 2

    asyncio.run(scenario())


def test_storage_and_state_failure_continue_draining_and_signal_pending(
    team, valid_spec, monkeypatch
):
    async def scenario():
        owner = controller_for(team, valid_spec)
        stdout, stderr = asyncio.StreamReader(), asyncio.StreamReader()
        stdout.feed_data(b'{"type":"event"}\n' * 300)
        stdout.feed_eof()
        stderr.feed_data(b"d" * 100000)
        stderr.feed_eof()
        owner.process = SimpleNamespace(stdout=stdout, stderr=stderr)
        future = asyncio.get_running_loop().create_future()
        owner.pending["waiting"] = future

        def fail(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(team.os, "open", fail)
        await asyncio.gather(owner.stdout(), owner.stderr())
        assert stdout.at_eof() and stderr.at_eof()
        assert owner.capture.error == "storage_io_error"
        assert owner.capture.lost_records >= 300
        assert owner.state["state_error"] == "state_io_error"
        with pytest.raises(team.TeamError, match="capture_loss"):
            await future

    asyncio.run(scenario())


def test_short_disk_write_is_explicit_partial_loss(team, tmp_path, limits, monkeypatch):
    capture = team.Capture(tmp_path / "capture", limits)
    fdopen = team.os.fdopen

    class ShortWriter:
        def __init__(self, fd, *args, **kwargs):
            self.file = fdopen(fd, *args, **kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.file.close()

        def write(self, value):
            return self.file.write(value[:10])

    monkeypatch.setattr(team.os, "fdopen", ShortWriter)
    assert capture.append("stdout", b'{"type":"event"}') is None
    assert capture.error == "storage_io_error" and capture.partial_tail
    assert capture.read(0, 100, 16384)["gap"]


def test_oversize_without_lf_signals_immediately_and_keeps_draining(team, valid_spec):
    async def scenario():
        owner = controller_for(team, valid_spec)
        stdout = asyncio.StreamReader()
        owner.process = SimpleNamespace(stdout=stdout)
        future = asyncio.get_running_loop().create_future()
        owner.pending["waiting"] = future
        task = asyncio.create_task(owner.stdout())
        stdout.feed_data(b"x" * 100000)
        with pytest.raises(team.TeamError, match="capture_loss"):
            await asyncio.wait_for(future, 1)
        assert owner.capture.lost_records == 1
        assert not task.done()
        stdout.feed_data(b"y" * 100000 + b"\n" + b'{"type":"event"}\n')
        stdout.feed_eof()
        await task
        assert owner.capture.lost_records == 1 and owner.capture.lost_bytes == 200000
        assert len(owner.capture.read(0, 100, 16384)["records"]) == 1

    asyncio.run(scenario())
