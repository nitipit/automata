"""Thin RPC validation, capture bounds and process ownership (model-free)."""

import importlib.util
import json
import os
import signal
import sys
from pathlib import Path

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
