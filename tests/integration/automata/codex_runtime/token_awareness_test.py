"""Filtered fixture/CLI tests; native request proof is separately opt-in."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from automata.install.codex import install_codex
from automata.install.directory import DirectoryInstallError

IDENTITY = "00000000-0000-4000-8000-000000000001"
OTHER = "00000000-0000-4000-8000-000000000002"
RUNTIME = Path(__file__).parents[4] / "src/automata/runtimes/codex"


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.syspath_prepend(str(RUNTIME))
    return importlib.import_module("token_awareness")


def fixture(path, *, version="0.159.0", complete=True, compact=False, missing=False):
    usage = {
        "input_tokens": 120000,
        "cached_input_tokens": 10000,
        "cache_write_input_tokens": 2000,
        "output_tokens": 25,
        "reasoning_output_tokens": 5,
        "total_tokens": 120025,
    }
    if missing:
        usage.pop("cache_write_input_tokens")
    rows = [
        ("session_meta", {"id": IDENTITY, "session_id": IDENTITY, "cli_version": version}),
        ("event_msg", {"type": "task_started", "turn_id": "turn-1"}),
        ("response_item", {"type": "message", "content": "PRIVATE_BODY_NEVER_SAVE"}),
        (
            "token_usage_record",
            {
                "thread_id": IDENTITY,
                "turn_id": "turn-1",
                "response_id": "response-1",
                "usage": usage,
            },
        ),
        ("event_msg", {"type": "token_count", "info": {"total_tokens": 999999999}}),
    ]
    if compact:
        rows.append(("compacted", {"compaction_response_id": "response-1"}))
    if complete:
        rows.append(("event_msg", {"type": "task_complete", "turn_id": "turn-1"}))
    path.write_text(
        "".join(
            json.dumps({"ordinal": n, "type": kind, "payload": payload}) + "\n"
            for n, (kind, payload) in enumerate(rows)
        )
    )
    return path


def test_normalization_dedup_delayed_checkpoint_and_replay(adapter, tmp_path):
    transcript = fixture(tmp_path / "owned.jsonl")
    state = tmp_path / "state"
    status = adapter.observe(state, transcript, IDENTITY, "inspect")
    assert status["counted"] == 110025
    assert status["cumulative"] == {
        "input": 108000,
        "cacheRead": 10000,
        "cacheWrite": 2000,
        "output": 25,
    }
    assert status["latestCheckpoint"] is None
    packet = adapter.observe(state, transcript, IDENTITY, "hook")["latestCheckpoint"]
    assert packet["throughResponse"] == "response-1"
    assert packet["throughRecordOrdinal"] == 3
    assert packet["measuredResponses"] == 1
    assert adapter.observe(state, transcript, IDENTITY, "hook")["latestCheckpoint"] == packet
    assert "PRIVATE_BODY" not in (state / f"{IDENTITY}.json").read_text()
    assert "PRIVATE_BODY" not in json.dumps(
        adapter.hook_output({"latestCheckpoint": packet}, "UserPromptSubmit")
    )


def test_threshold_set_retains_usage_and_waits_for_hook(adapter, tmp_path):
    transcript = fixture(tmp_path / "owned.jsonl")
    state = tmp_path / "state"
    status = adapter.observe(state, transcript, IDENTITY, "set", 200000)
    assert not status["pending"]
    status = adapter.observe(state, transcript, IDENTITY, "set", 100)
    assert status["pending"] and status["latestCheckpoint"] is None
    assert (
        adapter.observe(state, transcript, IDENTITY, "hook")["latestCheckpoint"]["deltaCounted"]
        == 110025
    )
    for value in [0, -1, True, 1.5, 1000000001, None]:
        with pytest.raises(adapter.CoverageError):
            adapter.observe(state, transcript, IDENTITY, "set", value)


@pytest.mark.parametrize("complete,compact", [(False, False), (True, True)])
def test_unfinished_and_compaction_turns_not_counted(adapter, tmp_path, complete, compact):
    transcript = fixture(tmp_path / "owned.jsonl", complete=complete, compact=compact)
    result = adapter.observe(tmp_path / "state", transcript, IDENTITY, "hook")
    assert result["counted"] == 0
    assert result["latestCheckpoint"] is None
    assert result["excludedCompactionRecords"] == int(compact)
    assert result["unclassifiedRecords"] == int(not complete)


@pytest.mark.parametrize("case", ["version", "identity", "missing", "corrupt", "symlink"])
def test_unknown_input_fails_closed_without_reset(adapter, tmp_path, case):
    transcript = fixture(tmp_path / "owned.jsonl")
    state = tmp_path / "state"
    adapter.observe(state, transcript, IDENTITY, "hook")
    before = (state / f"{IDENTITY}.json").read_bytes()
    identity = IDENTITY
    if case == "version":
        fixture(transcript, version="0.160.0")
    elif case == "identity":
        identity = OTHER
    elif case == "missing":
        fixture(transcript, missing=True)
    elif case == "corrupt":
        with transcript.open("a") as stream:
            stream.write('{"SECRET_INVALID_BODY"\n')
    else:
        link = tmp_path / "link.jsonl"
        link.symlink_to(transcript)
        transcript = link
    with pytest.raises(adapter.CoverageError) as error:
        adapter.observe(state, transcript, identity, "hook")
    assert "SECRET" not in str(error.value)
    assert (state / f"{IDENTITY}.json").read_bytes() == before


def test_partial_tail_and_snapshot_restore(adapter, tmp_path):
    transcript = fixture(tmp_path / "owned.jsonl")
    with transcript.open("ab") as stream:
        stream.write(b'{"incomplete')
    state = tmp_path / "state"
    first = adapter.observe(state, transcript, IDENTITY, "hook")
    assert first["partialTailDeferred"]
    transcript.write_text(
        json.dumps(
            {
                "ordinal": 0,
                "type": "session_meta",
                "payload": {"id": IDENTITY, "session_id": IDENTITY, "cli_version": "0.159.0"},
            }
        )
        + "\n"
    )
    resumed = adapter.observe(state, transcript, IDENTITY, "hook")
    assert resumed["counted"] == 110025
    assert resumed["retainedRecordsNotInCurrentSnapshot"] == 1
    assert "NOT active-branch" in resumed["scope"]
    assert resumed["latestCheckpoint"] == first["latestCheckpoint"]
    assert "inherited completeness unknown" in resumed["baseline"]


@pytest.mark.parametrize(
    "corruption", ["records", "usage", "latest", "packet", "baseline", "turns"]
)
def test_corrupt_saved_state_is_sanitized_and_retained(adapter, tmp_path, corruption):
    transcript = fixture(tmp_path / "owned.jsonl")
    state_root = tmp_path / "state"
    adapter.observe(state_root, transcript, IDENTITY, "hook")
    path = state_root / f"{IDENTITY}.json"
    state = json.loads(path.read_text())
    if corruption == "records":
        state["records"] = {"PRIVATE": None}
    elif corruption == "usage":
        next(iter(state["records"].values()))["usage"] = ["PRIVATE"]
    elif corruption == "latest":
        state["latest"] = ["PRIVATE"]
    elif corruption == "packet":
        state["latest"]["throughResponse"] = {"PRIVATE": [1]}
    elif corruption == "baseline":
        state["checkpointCounted"] = "PRIVATE"
    else:
        state["compactionTurns"] = {"PRIVATE": 1}
    path.write_text(json.dumps(state))
    before = path.read_bytes()
    with pytest.raises(adapter.CoverageError, match="invalid saved token state"):
        adapter.observe(state_root, transcript, IDENTITY, "hook")
    assert path.read_bytes() == before


def test_malformed_nested_event_and_hook_are_sanitized(adapter, tmp_path):
    transcript = fixture(tmp_path / "owned.jsonl")
    with transcript.open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "ordinal": 7,
                    "type": "event_msg",
                    "payload": {"type": "item_completed", "item": ["PRIVATE"]},
                }
            )
            + "\n"
        )
    with pytest.raises(adapter.CoverageError, match="unknown turn item envelope"):
        adapter.observe(tmp_path / "state", transcript, IDENTITY, "inspect")
    result = subprocess.run(
        [
            sys.executable,
            str(RUNTIME / "token_awareness.py"),
            "hook",
            "--state-root",
            str(tmp_path / "state"),
        ],
        input='["PRIVATE"]',
        capture_output=True,
        text=True,
        check=True,
    )
    assert not result.stderr and "PRIVATE" not in result.stdout
    assert "coverage unavailable" in result.stdout
    result = subprocess.run(
        [
            sys.executable,
            str(RUNTIME / "token_awareness.py"),
            "hook",
            "--state-root",
            str(tmp_path / "state"),
        ],
        input=json.dumps(
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": IDENTITY,
                "transcript_path": str(transcript),
            }
        ),
        capture_output=True,
        text=True,
        check=True,
    )
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "UserPromptSubmit"
    assert "coverage unavailable" in output["additionalContext"]
    assert not result.stderr and "PRIVATE" not in result.stdout


def test_precompact_provenance_excludes_failed_summary_without_compacted_record(adapter, tmp_path):
    transcript = fixture(tmp_path / "owned.jsonl", complete=False)
    state = tmp_path / "state"
    adapter.observe(state, transcript, IDENTITY, "inspect", compaction_turn="turn-1")
    fixture(transcript)  # Simulate task ending after failed compaction, no compacted row.
    result = adapter.observe(state, transcript, IDENTITY, "hook")
    assert result["counted"] == 0 and result["excludedCompactionRecords"] == 1


def test_shared_session_tree_uses_distinct_thread_ledger(adapter, tmp_path):
    transcript = fixture(tmp_path / "owned.jsonl")
    state = tmp_path / "state"
    parent = adapter.observe(state, transcript, IDENTITY, "hook")
    rows = [json.loads(line) for line in transcript.read_text().splitlines()]
    rows[0]["payload"]["id"] = OTHER
    rows[3]["payload"]["thread_id"] = OTHER
    transcript.write_text("".join(json.dumps(row) + "\n" for row in rows))
    child = adapter.observe(state, transcript, IDENTITY, "hook")
    assert child["session"] == parent["session"] and child["thread"] != parent["thread"]
    assert child["counted"] == parent["counted"] == 110025
    assert len(list(state.glob("*.json"))) == 2


def test_oversized_file_fails_without_reading_body(adapter, tmp_path):
    transcript = fixture(tmp_path / "owned.jsonl")
    with transcript.open("ab") as stream:
        stream.truncate(64 * 1024 * 1024 + 1)
    with pytest.raises(adapter.CoverageError, match="unsupported transcript file or size"):
        adapter.observe(tmp_path / "state", transcript, IDENTITY, "inspect")


def test_installer_and_installed_cli(tmp_path):
    result = install_codex(target_root=tmp_path / "assets", state_root=tmp_path / "state")
    target = Path(result.target)
    hooks = json.loads((target / "hooks.json").read_text())["hooks"]
    assert set(hooks) == {"SessionStart", "UserPromptSubmit", "PreCompact", "PostCompact"}
    assert not (tmp_path / "state").exists()
    transcript = fixture(tmp_path / "owned.jsonl")
    command = [
        sys.executable,
        str(target / "token_awareness.py"),
        "inspect",
        "--state-root",
        str(tmp_path / "state"),
        "--transcript",
        str(transcript),
        "--session",
        IDENTITY,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["counted"] == 110025
    assert not result.stderr
    with pytest.raises(DirectoryInstallError):
        install_codex(target_root=tmp_path / "assets", state_root=tmp_path / "state")
    with pytest.raises(DirectoryInstallError):
        install_codex(target_root=tmp_path / "assets", state_root=target / "state", mode="replace")
    install_codex(target_root=tmp_path / "assets", state_root=tmp_path / "state", mode="replace")
    assert (tmp_path / "state" / f"{IDENTITY}.json").exists()
