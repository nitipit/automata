"""Independent validation boundaries, without transports or model processes."""

import asyncio
import importlib.util
import json
import math
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
def valid_spec(tmp_path):
    return {
        "version": 1, "run_dir": str(tmp_path / "run"), "deadline_seconds": 30,
        "startup_timeout_seconds": 2, "shutdown_grace_seconds": 0.2,
        "callback": {"endpoint": "tcp://127.0.0.1:5555", "name": "test-team",
                     "recipient": "test-manager", "timeout_seconds": 1},
        "pi_command": [sys.executable, "fake-worker.py"],
        "workers": [{"id": "first", "cwd": str(tmp_path), "provider": "fake",
                     "model": "model", "thinking": "medium", "prompt": "PRIVATE_PROMPT"}],
    }


def test_valid_spec_is_accepted_without_allocating_run(team, valid_spec):
    team.validate_spec(valid_spec)
    assert not Path(valid_spec["run_dir"]).exists()


@pytest.mark.parametrize("field", [
    "deadline_seconds", "startup_timeout_seconds", "shutdown_grace_seconds",
])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, -1])
def test_nonfinite_boolean_negative_timeouts_are_rejected(team, valid_spec, field, value):
    valid_spec[field] = value
    with pytest.raises(team.TeamError):
        team.validate_spec(valid_spec)
    assert not Path(valid_spec["run_dir"]).exists()


@pytest.mark.parametrize("value", [math.nan, math.inf, True, -1])
def test_callback_timeout_is_bounded_numeric(team, valid_spec, value):
    valid_spec["callback"]["timeout_seconds"] = value
    with pytest.raises(team.TeamError):
        team.validate_spec(valid_spec)


@pytest.mark.parametrize("field", ["provider", "model", "thinking", "prompt"])
def test_explicit_worker_settings_mandatory(team, valid_spec, field):
    valid_spec["workers"][0].pop(field)
    with pytest.raises(team.TeamError):
        team.validate_spec(valid_spec)


def test_later_worker_invalidates_entire_spec_before_allocation(team, valid_spec):
    valid_spec["workers"].append({**valid_spec["workers"][0], "id": "../escape"})
    with pytest.raises(team.TeamError):
        team.validate_spec(valid_spec)
    assert not Path(valid_spec["run_dir"]).exists()


def test_stale_pid_identity_never_signals_reused_process(team, monkeypatch):
    identity = team.process_identity(os.getpid())
    assert identity is not None
    stale = {**identity, "start_ticks": str(int(identity["start_ticks"]) - 1)}
    called = []
    monkeypatch.setattr(team.os, "killpg", lambda *args: called.append(args))
    assert not team.identity_alive(stale)
    assert not team.signal_owned(stale, signal.SIGTERM)
    assert called == []


def test_wrong_boot_identity_never_signals(team, monkeypatch):
    identity = {**team.process_identity(os.getpid()), "boot_id": "previous-boot"}
    called = []
    monkeypatch.setattr(team.os, "killpg", lambda *args: called.append(args))
    assert not team.signal_owned(identity, signal.SIGKILL)
    assert called == []


def test_compact_state_excludes_unrecognized_private_payloads(team):
    state = {"status": "running", "prompt": "PRIVATE_PROMPT", "pi_command": ["SECRET"],
             "workers": {"first": {"id": "first", "status": "running",
                                   "prompt": "PRIVATE_PROMPT", "tool_arguments": "SECRET",
                                   "last_assistant": {"content": "PRIVATE_RESULT"}}}}
    compact = team.compact_state(state)
    assert compact == {"status": "running", "workers": {
        "first": {"id": "first", "status": "running"}}}


def test_first_settled_evidence_survives_later_disposal_records(team, tmp_path):
    async def scenario():
        (tmp_path / "workers").mkdir()
        view = {"id": "first", "status": "running", "timings": {}}
        owner = SimpleNamespace(state={"workers": {"first": view}}, run=tmp_path)
        worker = team.Worker(owner, {"id": "first"})
        worker.dispatched = True
        reader = asyncio.StreamReader()
        worker.process = SimpleNamespace(stdout=reader)
        records = [
            {"type": "message_end", "message": {"role": "assistant", "stopReason": "stop"}},
            {"type": "agent_settled", "aborted": False},
            {"type": "message_end", "message": {"role": "assistant", "stopReason": "aborted"}},
            {"type": "agent_end", "messages": [{"role": "assistant", "stopReason": "error"}]},
            {"type": "agent_settled", "aborted": True},
        ]
        reader.feed_data(b"".join(json.dumps(record).encode() + b"\n" for record in records))
        reader.feed_eof()
        await worker.drain_stdout()
        assert worker.last_assistant["stopReason"] == "stop"
        assert view["settled"] == {"aborted": False}
        assert worker.settled.is_set() and not worker.protocol_error
        assert len((tmp_path / "workers/first.rpc.jsonl").read_text().splitlines()) == 5

    asyncio.run(scenario())


@pytest.mark.parametrize("fault", [None, "sender", "nonce", "version", "unwrapped"])
def test_callback_requires_correlated_ack_not_send_acceptance(team, tmp_path, fault):
    class NodeDouble:
        def __init__(self):
            self.queue = asyncio.Queue()
            self.sent = []
            self.closed = False

        async def receive(self):
            return await self.queue.get()

        async def send(self, recipient, payload, timeout):
            envelope = json.loads(payload)
            assert envelope["version"] == 1 and envelope["type"] == "message"
            probe = json.loads(envelope["text"])
            self.sent.append(probe)
            ack = {"version": 0 if fault == "version" else 1,
                   "type": "pi_team_probe_ack",
                   "nonce": "wrong" if fault == "nonce" else probe["nonce"]}
            wire = ack if fault == "unwrapped" else {
                "version": 1, "type": "message", "text": json.dumps(ack)}
            self.queue.put_nowait(SimpleNamespace(
                sender="imposter" if fault == "sender" else recipient,
                payload=json.dumps(wire).encode()))

        async def close(self, timeout):
            self.closed = True

    async def scenario():
        node = NodeDouble()
        callback = team.Callback(node, {"name": "fixture-team", "recipient": "manager",
                                        "timeout_seconds": 0.03})
        try:
            if fault is None:
                await callback.probe(tmp_path)
                assert callback.acked.is_set()
            else:
                with pytest.raises(TimeoutError):
                    await callback.probe(tmp_path)
                assert not callback.acked.is_set()
            assert len(node.sent) == 1
        finally:
            await callback.close()
        assert node.closed
    asyncio.run(scenario())
