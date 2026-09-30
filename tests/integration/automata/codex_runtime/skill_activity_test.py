"""No real history: native-shaped metadata and installed subprocess controls."""

import concurrent.futures
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from automata.install.codex import install_codex

IDENTITY = "00000000-0000-4000-8000-000000000001"
OTHER = "00000000-0000-4000-8000-000000000002"
RUNTIME = Path(__file__).parents[4] / "src/automata/runtimes/codex"
STAMP = "2026-09-30T03:00:00+00:00"
SECRET = "PRIVATE_SKILL_BODY_NEVER_PERSIST"


@pytest.fixture
def api(monkeypatch):
    monkeypatch.syspath_prepend(str(RUNTIME))
    return importlib.import_module("skill_activity")


def row(n, kind, payload):
    return {"ordinal": n, "type": kind, "timestamp": STAMP, "payload": payload}


def meta(identity=IDENTITY, version="0.159.0"):
    return row(
        0,
        "session_meta",
        {
            "id": identity,
            "session_id": identity,
            "cli_version": version,
            "cwd": "/owned/project",
        },
    )


def insertion(
    n=1, name="fixture-skill", message="msg-1", kind="skills.selected_skill_instructions"
):
    return row(
        n,
        "response_item",
        {
            "type": "message",
            "id": message,
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        f"<skill>\n<name>{name}</name>\n"
                        f"<path>/owned/{name}/SKILL.md</path>\n{SECRET}\n</skill>"
                    ),
                }
            ],
            "internal_chat_message_metadata_passthrough": {
                "turn_id": f"turn-{message}",
                "content_item_kinds": [kind],
            },
        },
    )


def save(path, *rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def test_enrollment_ignores_history_dedups_and_preserves_metadata(api, tmp_path):
    path = save(tmp_path / "owned.jsonl", meta(), insertion())
    state = tmp_path / "state"
    assert api.observe(state, path, IDENTITY)["retainedCount"] == 0
    save(path, meta(), insertion(), insertion(2, message="msg-2"))
    result = api.observe(state, path, IDENTITY)
    assert result["retainedCount"] == 1
    record = result["records"][0]
    assert record["timestamp"] == STAMP
    assert record["runtime"] == "codex"
    assert record["evidenceKind"] == "native_instruction_insertion"
    assert record["project"] == "/owned/project"
    assert record["session"] == IDENTITY
    assert api.observe(state, path, IDENTITY)["records"] == [record]
    save(path, meta(), insertion(), insertion(2, message="msg-2"), insertion(3, message="msg-2"))
    assert api.observe(state, path, IDENTITY)["records"] == [record]
    assert SECRET not in json.dumps(result)
    assert SECRET not in (state / "skill-activity" / f"{IDENTITY}.json").read_text()
    assert not (state / f"{IDENTITY}.json").exists()


@pytest.mark.parametrize("kind", ["user.text", "skills.available_skills", "unknown", None])
def test_skill_shaped_text_without_native_kind_is_not_activation(api, tmp_path, kind):
    path = save(tmp_path / "owned.jsonl", meta())
    state = tmp_path / "state"
    api.observe(state, path, IDENTITY)
    item = insertion(kind=kind)
    if kind is None:
        item["payload"].pop("internal_chat_message_metadata_passthrough")
    save(path, meta(), item)
    assert api.observe(state, path, IDENTITY)["retainedCount"] == 0


@pytest.mark.parametrize("exit_code", [0, 1])
def test_shell_commands_and_read_output_are_not_native_insertions(api, tmp_path, exit_code):
    path = save(tmp_path / "owned.jsonl", meta())
    state = tmp_path / "state"
    api.observe(state, path, IDENTITY)
    save(
        path,
        meta(),
        row(
            1,
            "event_msg",
            {
                "type": "exec_command_end",
                "exit_code": exit_code,
                "command": ["cat", "/owned/fixture-skill/SKILL.md"],
                "stdout": SECRET,
            },
        ),
    )
    assert api.observe(state, path, IDENTITY)["retainedCount"] == 0


def test_disable_enable_drops_intervening_history_and_filter_limit(api, tmp_path):
    path = save(tmp_path / "owned.jsonl", meta())
    state = tmp_path / "state"
    assert not api.observe(state, path, IDENTITY, "disable")["enabled"]
    save(path, meta(), insertion())
    result = api.observe(state, path, IDENTITY, "enable")
    assert result["enabled"] and result["disabledSkipped"] == 1
    assert result["retainedCount"] == 0
    save(path, meta(), insertion(), insertion(2, message="msg-2"), insertion(3, "other", "msg-3"))
    result = api.observe(state, path, IDENTITY, limit=1)
    assert result["retainedCount"] == 2 and result["truncated"]
    assert result["records"][0]["skill"] == "other"
    assert api.observe(state, path, IDENTITY, skill="fixture-skill")["matchedCount"] == 1


def test_capacity_is_bounded_without_deleting_or_losing_dedup(api, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "MAX_RECORDS", 1)
    path = save(tmp_path / "owned.jsonl", meta())
    state = tmp_path / "state"
    api.observe(state, path, IDENTITY)
    save(path, meta(), insertion(), insertion(2, message="msg-2"))
    result = api.observe(state, path, IDENTITY)
    assert result["retainedCount"] == result["capacitySkipped"] == 1
    assert api.observe(state, path, IDENTITY)["capacitySkipped"] == 1


@pytest.mark.parametrize(
    "case", ["version", "identity", "symlink", "corrupt", "rewind", "project", "conflict"]
)
def test_failed_observation_keeps_previous_state(api, tmp_path, case):
    path = save(tmp_path / "owned.jsonl", meta())
    state = tmp_path / "state"
    api.observe(state, path, IDENTITY)
    save(path, meta(), insertion())
    api.observe(state, path, IDENTITY)
    stored = state / "skill-activity" / f"{IDENTITY}.json"
    before = stored.read_bytes()
    if case == "version":
        save(path, meta(version="0.160.0"))
    elif case == "identity":
        save(path, meta(OTHER))
    elif case == "symlink":
        link = tmp_path / "link"
        link.symlink_to(path)
        path = link
    elif case == "corrupt":
        path.write_text("{SECRET_INVALID_JSON}\n")
    elif case == "rewind":
        save(path, meta())
    elif case == "project":
        header = meta()
        header["payload"]["cwd"] = "/another/project"
        save(path, header, insertion())
    elif case == "conflict":
        save(path, meta(), insertion(), insertion(2, name="changed"))
    with pytest.raises(api.CoverageError):
        api.observe(state, path, IDENTITY)
    assert stored.read_bytes() == before


def test_fork_no_parent_history_and_partial_tail(api, tmp_path):
    path = save(tmp_path / "owned.jsonl", meta(OTHER), insertion())
    state = tmp_path / "state"
    with path.open("a") as stream:
        stream.write('{"partial')
    result = api.observe(state, path, OTHER)
    assert result["retainedCount"] == 0 and result["partialTailDeferred"]
    assert not (state / "skill-activity" / f"{IDENTITY}.json").exists()


def test_saved_corruption_not_silently_reset(api, tmp_path):
    path = save(tmp_path / "owned.jsonl", meta())
    state = tmp_path / "state"
    api.observe(state, path, IDENTITY)
    stored = state / "skill-activity" / f"{IDENTITY}.json"
    stored.write_text("{}")
    with pytest.raises(api.CoverageError):
        api.observe(state, path, IDENTITY)
    assert stored.read_text() == "{}"


def test_installed_controls_hooks_and_concurrency(api, tmp_path):
    install_codex(target_root=tmp_path / "assets", state_root=tmp_path / "state")
    bundle = tmp_path / "assets/token-awareness"
    hooks = json.loads((bundle / "hooks.json").read_text())["hooks"]
    assert all(len(groups[0]["hooks"]) == 2 for groups in hooks.values())
    path = save(tmp_path / "owned.jsonl", meta())
    command = [
        sys.executable,
        str(bundle / "skill_activity.py"),
        "list",
        "--state-root",
        str(tmp_path / "state"),
        "--transcript",
        str(path),
        "--session",
        IDENTITY,
    ]

    def run():
        return json.loads(subprocess.check_output(command, text=True))

    assert run()["retainedCount"] == 0
    save(path, meta(), insertion())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: run(), range(8)))
    assert all(r["retainedCount"] == 1 for r in results)
    assert len({r["records"][0]["observedAt"] for r in results}) == 1
    hook = [
        sys.executable,
        str(bundle / "skill_activity.py"),
        "hook",
        "--state-root",
        str(tmp_path / "state"),
    ]
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "transcript_path": str(path),
        "session_id": IDENTITY,
    }
    output = json.loads(subprocess.check_output(hook, input=json.dumps(payload), text=True))
    text = output["hookSpecificOutput"]["additionalContext"]
    assert "Retained native insertion observations: 1" in text and "skill_activity.py" in text
    assert "saved" in text and "--thread" in text
    assert SECRET not in text
    path.unlink()
    historical = [
        sys.executable,
        str(bundle / "skill_activity.py"),
        "saved",
        "--state-root",
        str(tmp_path / "state"),
        "--thread",
        IDENTITY,
    ]
    state_path = tmp_path / "state/skill-activity" / f"{IDENTITY}.json"
    before = state_path.read_bytes()
    result = json.loads(subprocess.check_output(historical, text=True))
    assert result["retainedCount"] == 1 and result["readOnly"]
    assert result["coverage"] == "saved-observations-only"
    assert result["currentCoverage"] == "unknown; transcript not consulted"
    assert state_path.read_bytes() == before


@pytest.mark.parametrize("case", ["missing", "rewound", "oversized"])
def test_saved_query_needs_no_live_transcript_and_never_writes(api, tmp_path, monkeypatch, case):
    path = save(tmp_path / "owned.jsonl", meta())
    root = tmp_path / "state"
    api.observe(root, path, IDENTITY)
    save(path, meta(), insertion(), insertion(2, name="other", message="msg-2"))
    expected = api.observe(root, path, IDENTITY)["records"]
    if case == "missing":
        path.unlink()
    elif case == "rewound":
        save(path, meta())
    else:
        with path.open("r+b") as stream:
            stream.truncate(64 * 1024 * 1024 + 1)  # sparse owned fixture
    with pytest.raises((api.CoverageError, OSError)):
        api.observe(root, path, IDENTITY)

    def never_scan(*_args, **_kwargs):
        raise AssertionError("saved query must not consult a transcript")

    monkeypatch.setattr(api, "scan", never_scan)
    before = {
        p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in (root / "skill-activity").iterdir()
    }
    result = api.saved(root, IDENTITY)
    assert result["records"] == expected and result["available"] and result["readOnly"]
    assert result["savedThroughOrdinal"] == 2
    assert api.saved(root, IDENTITY, skill="fixture-skill")["matchedCount"] == 1
    assert api.saved(root, IDENTITY, limit=1)["truncated"]
    after = {
        p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in (root / "skill-activity").iterdir()
    }
    assert after == before


def test_saved_absent_state_does_not_enroll_or_create_root(api, tmp_path):
    root = tmp_path / "absent-state"
    result = api.saved(root, IDENTITY)
    assert not result["available"] and result["retainedCount"] == 0
    assert "unknown" in result["coverage"]
    assert not root.exists()
    with pytest.raises(api.CoverageError):
        api.saved(root, "../not-a-thread")
    assert not root.exists()


@pytest.mark.parametrize("case", ["role", "id", "timestamp", "wrapper", "relative", "parts"])
def test_unsupported_native_metadata_never_writes_event(api, tmp_path, case):
    path = save(tmp_path / "owned.jsonl", meta())
    state = tmp_path / "state"
    api.observe(state, path, IDENTITY)
    stored = state / "skill-activity" / f"{IDENTITY}.json"
    before = stored.read_bytes()
    item = insertion()
    payload = item["payload"]
    if case == "role":
        payload["role"] = "assistant"
    elif case == "id":
        payload.pop("id")
    elif case == "timestamp":
        item["timestamp"] = "2026-09-30T03:00:00"  # no offset
    elif case == "wrapper":
        payload["content"][0]["text"] = "<skill>SECRET_MALFORMED</skill>"
    elif case == "relative":
        payload["content"][0]["text"] = payload["content"][0]["text"].replace("/owned/", "owned/")
    elif case == "parts":
        payload["content"].append({"type": "input_text", "text": "SECRET_EXTRA_PART"})
    save(path, meta(), item)
    with pytest.raises(api.CoverageError):
        api.observe(state, path, IDENTITY)
    assert stored.read_bytes() == before


@pytest.mark.parametrize("case", ["body", "path", "key", "ordinal", "time", "project"])
def test_saved_event_validation_prevents_reinterpretation(api, tmp_path, case):
    path = save(tmp_path / "owned.jsonl", meta())
    root = tmp_path / "state"
    api.observe(root, path, IDENTITY)
    save(path, meta(), insertion())
    api.observe(root, path, IDENTITY)
    stored = root / "skill-activity" / f"{IDENTITY}.json"
    state = json.loads(stored.read_text())
    record = next(iter(state["records"].values()))
    if case == "body":
        record["body"] = "DO_NOT_RETAIN_OR_ECHO"
    elif case == "path":
        record["path"] = "relative/SKILL.md"
    elif case == "key":
        record["message"] = "other-message"
    elif case == "ordinal":
        record["ordinal"] = 0
    elif case == "time":
        record["timestamp"] = "yesterday"
    elif case == "project":
        record["project"] = "/other/project"
    stored.write_text(json.dumps(state))
    before = stored.read_bytes()
    with pytest.raises(api.CoverageError):
        api.observe(root, path, IDENTITY)
    assert stored.read_bytes() == before
