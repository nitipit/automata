"""Context/timestamp semantics using owned, content-redacted transcript fixtures."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

IDENTITY = "00000000-0000-4000-8000-000000000001"
RUNTIME = Path(__file__).parents[4] / "src/automata/runtimes/codex"
NOW = "2026-09-30T03:00:10+00:00"
LATER = "2026-09-30T03:10:10+00:00"


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(RUNTIME))
    return importlib.import_module("token_awareness"), importlib.import_module("context_awareness")


def rows(window=240050, total=120025):
    usage = {
        "input_tokens": 100,
        "output_tokens": 2,
        "cached_input_tokens": 10,
        "cache_write_input_tokens": 5,
        "reasoning_output_tokens": 1,
        "total_tokens": total,
    }
    return [
        ("session_meta", {"id": IDENTITY, "session_id": IDENTITY, "cli_version": "0.159.0"}),
        (
            "event_msg",
            {
                "type": "task_started",
                "turn_id": "turn-1",
                "started_at": 1790737200,
                "model_context_window": window,
            },
        ),
        (
            "event_msg",
            {
                "type": "item_completed",
                "turn_id": "turn-1",
                "started_at_ms": 1790737201000,
                "completed_at_ms": 1790737201001,
                "item": {"type": "UserMessage", "id": "user-1", "content": "PRIVATE"},
            },
        ),
        (
            "event_msg",
            {
                "type": "item_completed",
                "turn_id": "turn-1",
                "started_at_ms": 1790737201000,
                "completed_at_ms": 1790737201001,
                "item": {"type": "AgentMessage", "id": "assistant-1", "content": "PRIVATE"},
            },
        ),
        (
            "token_usage_record",
            {
                "thread_id": IDENTITY,
                "turn_id": "turn-1",
                "response_id": "response-1",
                "usage": usage,
            },
        ),
        (
            "event_msg",
            {
                "type": "token_count",
                "info": {
                    "last_token_usage": usage,
                    "total_token_usage": {"total_tokens": 999999},
                    "model_context_window": window,
                },
            },
        ),
        ("event_msg", {"type": "task_complete", "turn_id": "turn-1"}),
    ]


def transcript(path, entries):
    path.write_text(
        "".join(
            json.dumps(
                {
                    "ordinal": index,
                    "timestamp": "2026-09-30T10:00:02+07:00",
                    "type": kind,
                    "payload": payload,
                }
            )
            + "\n"
            for index, (kind, payload) in enumerate(entries)
        )
    )
    return path


def project(modules, tmp_path, *, window=240050, total=120025):
    adapter, awareness = modules
    path = transcript(tmp_path / "owned.jsonl", rows(window, total))
    snapshot = adapter.scan(path, IDENTITY)
    state = {}
    packet = awareness.update(
        state, snapshot, snapshot["records"], "UserPromptSubmit", "turn-1", NOW
    )
    return adapter, awareness, path, snapshot, state, packet


def test_context_uses_last_not_cumulative_or_normalized_billing(modules, tmp_path):
    _, _, _, _, _, packet = project(modules, tmp_path)
    assert packet["context"]["tokens"] == 120025
    assert packet["context"]["percent"] == 50
    assert packet["pressureBand"] == "moderate"
    assert packet["anchorUsage"]["counted"] == 92
    assert packet["anchorUsage"]["normalized"]["cacheRead"] == 10
    assert "billing" in packet["coverage"] and "not active work" in packet["coverage"]


@pytest.mark.parametrize("window", [None, 0, -1, "PRIVATE", True])
def test_unknown_window_never_fabricates_pressure(modules, tmp_path, window):
    _, _, _, _, _, packet = project(modules, tmp_path, window=window)
    assert packet["context"]["tokens"] == 120025
    assert packet["context"]["window"] is None
    assert packet["context"]["percent"] is None
    assert packet["pressureBand"] == "unknown"


@pytest.mark.parametrize(
    "total,expected",
    [
        (1, "low"),
        (50, "moderate"),
        (75, "elevated"),
        (90, "high"),
        (95, "critical"),
        (110, "critical"),
        (0, "unknown"),
    ],
)
def test_pressure_bands_and_ambiguous_zero(modules, tmp_path, total, expected):
    _, _, _, _, _, packet = project(modules, tmp_path, window=100, total=total)
    assert packet["pressureBand"] == expected
    if total == 0:
        assert packet["context"]["tokens"] is None
        assert packet["context"]["reportedTokens"] == 0


def test_stable_event_timestamps_distinct_from_observation_and_elapsed(modules, tmp_path):
    _, awareness, _, snapshot, state, packet = project(modules, tmp_path)
    messages = packet["recentMessages"]
    assert [message["item"] for message in messages] == ["user-1", "assistant-1"]
    assert messages[0]["startedAt"] == messages[1]["startedAt"]
    assert messages[0]["recordedAt"] == "2026-09-30T03:00:02+00:00"
    assert packet["inputAnchor"]["at"] == NOW != messages[0]["startedAt"]
    repeated = awareness.update(
        state, snapshot, snapshot["records"], "UserPromptSubmit", "turn-1", LATER
    )
    assert repeated == packet
    inspected = awareness.update(
        state, snapshot, snapshot["records"], None, None, LATER, inspecting=True
    )
    assert inspected["packetId"] == packet["packetId"]
    assert inspected["elapsedWallSecondsAtInspect"] == 600
    assert inspected["elapsedWallSecondsAtObservation"] == 0
    assert "PRIVATE" not in json.dumps(state)
    assert awareness.elapsed(packet["inputAnchor"], "2026-09-30T02:00:00+00:00") is None


def test_new_input_observation_gets_new_anchor_without_rewriting_event_times(modules, tmp_path):
    _, awareness, _, snapshot, state, packet = project(modules, tmp_path)
    later = awareness.update(
        state, snapshot, snapshot["records"], "UserPromptSubmit", "turn-2", LATER
    )
    assert later["inputAnchor"]["id"] != packet["inputAnchor"]["id"]
    assert later["recentMessages"] == packet["recentMessages"]
    assert later["anchorUsage"]["measuredResponses"] == 0
    assert later["inputAnchor"]["at"] == LATER


def test_recomputed_context_and_rate_limit_only_notification(modules, tmp_path):
    adapter, awareness = modules
    entries = rows()
    entries[5][1]["info"]["last_token_usage"] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 1234,
    }
    entries.append(("event_msg", {"type": "token_count", "info": None, "rate_limits": {}}))
    snapshot = adapter.scan(transcript(tmp_path / "owned.jsonl", entries), IDENTITY)
    packet = awareness.update({}, snapshot, {}, None, None, NOW)
    assert packet["context"]["tokens"] == 1234
    assert packet["context"]["source"] == "recomputed-context-estimate"
    assert packet["context"]["recordOrdinal"] == 5


def test_restores_recent_facts_after_truncation_with_explicit_scope(modules, tmp_path):
    adapter, awareness, path, _, state, packet = project(modules, tmp_path)
    transcript(path, rows()[:1])
    snapshot = adapter.scan(path, IDENTITY)
    restored = awareness.update(state, snapshot, {}, "SessionStart", None, LATER)
    assert restored["context"] == packet["context"]
    assert restored["contextAvailability"] == "restored-last-known-observation"
    assert restored["recentMessages"] == packet["recentMessages"]
    assert restored["restoredRecentMessages"] == 2
    assert restored["inputAnchor"] == packet["inputAnchor"]
    # Native-user fallback anchors also survive losing their transcript rows.
    original = adapter.scan(transcript(path, rows()), IDENTITY)
    native_state = {}
    native = awareness.update(native_state, original, {}, None, None, NOW)
    assert native["inputAnchor"]["kind"] == "native-user-item-lifecycle"
    restored_native = awareness.update(native_state, snapshot, {}, "SessionStart", None, LATER)
    assert restored_native["inputAnchor"] == native["inputAnchor"]


def test_own_developer_context_does_not_recursively_change_packet(modules, tmp_path):
    adapter, awareness, path, _, state, packet = project(modules, tmp_path)
    entries = rows() + [("response_item", {"role": "developer", "content": json.dumps(packet)})]
    snapshot = adapter.scan(transcript(path, entries), IDENTITY)
    repeated = awareness.update(
        state, snapshot, snapshot["records"], "UserPromptSubmit", "turn-1", LATER
    )
    assert repeated == packet


@pytest.mark.parametrize("field", ["anchors", "packet", "sourceKey"])
def test_malformed_awareness_state_sanitized_in_installed_control(modules, tmp_path, field):
    adapter, _ = modules
    path = transcript(tmp_path / "owned.jsonl", rows())
    state_root = tmp_path / "state"
    adapter.observe(state_root, path, IDENTITY, "context")
    saved = state_root / f"{IDENTITY}.json"
    state = json.loads(saved.read_text())
    state["awareness"][field] = ["PRIVATE"]
    saved.write_text(json.dumps(state))
    before = saved.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            str(RUNTIME / "token_awareness.py"),
            "context",
            "--transcript",
            str(path),
            "--session",
            IDENTITY,
            "--state-root",
            str(state_root),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1 and not result.stderr
    assert json.loads(result.stdout)["coverage"] == "unknown"
    assert "PRIVATE" not in result.stdout and saved.read_bytes() == before


@pytest.mark.parametrize("event", [["PRIVATE"], {"PRIVATE": 1}])
def test_malformed_hook_event_has_sanitized_failure(tmp_path, event):
    result = subprocess.run(
        [
            sys.executable,
            str(RUNTIME / "token_awareness.py"),
            "hook",
            "--state-root",
            str(tmp_path / "state"),
        ],
        input=json.dumps({"hook_event_name": event}),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "coverage unavailable" in result.stdout
    assert "PRIVATE" not in result.stdout and not result.stderr


def test_missing_lifecycle_clock_labels_record_clock_fallback(modules, tmp_path):
    adapter, awareness = modules
    entries = rows()
    entries[2][1]["started_at_ms"] = None
    entries[2][1]["completed_at_ms"] = None
    snapshot = adapter.scan(transcript(tmp_path / "owned.jsonl", entries), IDENTITY)
    packet = awareness.update({}, snapshot, {}, None, None, NOW)
    assert packet["inputAnchor"]["kind"] == "native-user-item-record-time"
    assert packet["inputAnchor"]["at"] == "2026-09-30T03:00:02+00:00"


def test_existing_token_only_state_gains_context_without_reset(modules, tmp_path):
    adapter, _ = modules
    path = transcript(tmp_path / "owned.jsonl", rows())
    state_root = tmp_path / "state"
    initial = adapter.observe(state_root, path, IDENTITY, "set", 1)
    initial = adapter.observe(state_root, path, IDENTITY, "hook")
    state_path = state_root / f"{IDENTITY}.json"
    saved = json.loads(state_path.read_text())
    del saved["awareness"]  # The accepted CX-004 state has no awareness field.
    state_path.write_text(json.dumps(saved))
    upgraded = adapter.observe(state_root, path, IDENTITY, "context")
    assert upgraded["cumulative"] == initial["cumulative"]
    assert upgraded["latestCheckpoint"] == initial["latestCheckpoint"]
    assert upgraded["contextStatus"]["context"]["tokens"] == 120025


def test_changed_native_timestamp_identity_fails_instead_of_rewriting(modules, tmp_path):
    adapter, awareness, path, _, state, _ = project(modules, tmp_path)
    entries = rows()
    entries[2][1]["completed_at_ms"] += 1000
    snapshot = adapter.scan(transcript(path, entries), IDENTITY)
    with pytest.raises(ValueError, match="conflicting native timestamp identity"):
        awareness.update(state, snapshot, snapshot["records"], None, None, LATER)


def test_evicted_input_observation_is_not_reassigned_same_id(modules, tmp_path):
    _, awareness, _, snapshot, state, packet = project(modules, tmp_path)
    for index in range(2, 11):
        awareness.update(state, snapshot, {}, "UserPromptSubmit", f"turn-{index}", LATER)
    assert len(state["awareness"]["anchors"]) == 8
    observed_again = awareness.update(state, snapshot, {}, "UserPromptSubmit", "turn-1", LATER)
    assert observed_again["inputAnchor"]["id"] != packet["inputAnchor"]["id"]
    assert observed_again["inputAnchor"]["at"] == LATER


def test_recent_timestamps_bounded_and_malformed_values_unknown(modules, tmp_path):
    adapter, awareness = modules
    entries = rows()
    for index in range(10):
        entries.append(
            (
                "event_msg",
                {
                    "type": "item_completed",
                    "turn_id": "turn-1",
                    "started_at_ms": None,
                    "completed_at_ms": "PRIVATE",
                    "item": {"type": "AgentMessage", "id": f"later-{index}", "content": "PRIVATE"},
                },
            )
        )
    snapshot = adapter.scan(transcript(tmp_path / "owned.jsonl", entries), IDENTITY)
    packet = awareness.update({}, snapshot, {}, None, None, NOW)
    assert len(packet["recentMessages"]) == 6
    assert all(message["completedAt"] is None for message in packet["recentMessages"])
    assert "PRIVATE" not in json.dumps(packet)
