"""Management transport deadlines without a real process or real configuration."""

import importlib
import itertools
from pathlib import Path
from types import SimpleNamespace

import pytest

RUNTIME = Path(__file__).parents[4] / "src/automata/runtimes/codex"


@pytest.fixture
def native(monkeypatch):
    monkeypatch.syspath_prepend(str(RUNTIME))
    return importlib.import_module("session_native")


def test_expired_buffered_reply_cannot_bypass_deadline(native, monkeypatch):
    client = native.NativeClient.__new__(native.NativeClient)
    client.buffer = b'{"id":1,"result":{}}\n'
    monkeypatch.setattr(native.time, "monotonic", lambda: 100)
    with pytest.raises(native.CoverageError, match="timed out"):
        client._receive(99)


def test_continuous_ready_notifications_cannot_extend_request(native, monkeypatch):
    client = native.NativeClient.__new__(native.NativeClient)
    client.sequence = 0
    client._send = lambda _value: None
    received = []

    def ready(_deadline):
        received.append(True)
        return {"method": "notification"}

    client._receive = ready
    clocks = itertools.count()
    monkeypatch.setattr(native.time, "monotonic", lambda: next(clocks))
    with pytest.raises(native.CoverageError, match="timed out"):
        client._request("thread/read", {})
    assert len(received) == 29


def test_continuous_partial_bytes_have_absolute_receive_deadline(native, monkeypatch):
    client = native.NativeClient.__new__(native.NativeClient)
    client.buffer = b""
    client.selector = SimpleNamespace(select=lambda _timeout: [True])
    client.process = SimpleNamespace(stdout=SimpleNamespace(fileno=lambda: 99))
    clocks = itertools.count()
    monkeypatch.setattr(native.time, "monotonic", lambda: next(clocks))
    monkeypatch.setattr(native.os, "read", lambda *_args: b"x")
    with pytest.raises(native.CoverageError, match="timed out"):
        client._receive(5)
    assert len(client.buffer) < 5


def test_model_turn_rpc_is_never_available(native):
    client = native.NativeClient.__new__(native.NativeClient)
    with pytest.raises(native.CoverageError, match="not an authorized"):
        client.request("turn/start", {"input": []})


def test_invalid_cwd_fails_before_store_or_scratch_creation(native, monkeypatch, tmp_path):
    monkeypatch.setattr(native.shutil, "which", lambda _name: "/fixture/bwrap")
    client = native.NativeClient("/fixture/codex", tmp_path / "store", tmp_path / "scratch", ["/"])
    with pytest.raises(native.CoverageError, match="working directory"):
        client.__enter__()
    assert not (tmp_path / "store").exists() and not (tmp_path / "scratch").exists()


def test_process_start_failure_closes_stderr_and_temporary_root(native, monkeypatch, tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    monkeypatch.setattr(native.shutil, "which", lambda _name: "/fixture/bwrap")
    monkeypatch.setattr(
        native.subprocess, "check_output", lambda *_args, **_kwargs: b"codex-cli 0.159.0"
    )

    def fail(*_args, **_kwargs):
        raise OSError("fixture process start failure")

    monkeypatch.setattr(native.subprocess, "Popen", fail)
    client = native.NativeClient(
        "/fixture/codex", store, tmp_path / "scratch", [str(tmp_path / "cwd")]
    )
    with pytest.raises(OSError):
        client.__enter__()
    assert client.stderr is None and client.temporary is None
    assert list((tmp_path / "scratch").iterdir()) == []
