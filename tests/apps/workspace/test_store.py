"""Persistence, validation, and local simulation boundary tests."""

import pytest
from shelfdb.shelf import DB

from automata.apps.workspace import store as store_module
from automata.apps.workspace.store import (
    CONVERSATIONS,
    PROJECT_ID,
    RevisionConflict,
    WorkspaceStore,
    append_message,
    default_state,
    validate_state,
)


def test_default_view_has_no_page_route_and_uses_schema_v2():
    state = default_state()
    assert state["version"] == 2
    assert state["view"] == {
        "selectedArtifactId": "artifact-launch-brief",
        "selectedConversationId": "conversation-aster",
    }
    with pytest.raises(ValueError, match="workspace view state"):
        validate_state({**state, "view": {**state["view"], "mode": "chat"}})


def test_shelfdb_update_and_reload_preserve_artifact_and_conversation_drafts(tmp_path):
    store = WorkspaceStore(tmp_path / "workspace")
    state = default_state()
    state["artifact"]["content"] = "Shared revision"
    state["conversations"]["conversation-mira"]["draft"] = "Keep this unsent"
    assert store.save(state)["artifact"]["content"] == "Shared revision"
    revision = store.load()
    revision["artifact"]["content"] = "Updated revision"
    store.save(revision)

    recovered = WorkspaceStore(tmp_path / "workspace").load()
    assert recovered["artifact"]["content"] == "Updated revision"
    assert recovered["conversations"]["conversation-mira"]["draft"] == "Keep this unsent"
    assert recovered["view"]["selectedArtifactId"] == "artifact-launch-brief"


def test_previous_schema_is_not_migrated_automatically(tmp_path):
    path = tmp_path / "workspace"
    store = WorkspaceStore(path)
    previous = default_state()
    previous["version"] = 1
    previous["view"]["mode"] = "workspace"
    with DB(str(path)) as database, database.transaction(write=True) as tx:
        tx.shelf("workspace").put(PROJECT_ID, previous)

    with pytest.raises(RuntimeError, match="could not be read"):
        store.load()


def test_stale_whole_state_write_conflicts_without_replacing_new_revision(tmp_path):
    store = WorkspaceStore(tmp_path / "workspace")
    first = default_state()
    second = default_state()
    first["artifact"]["content"] = "First writer"
    second["artifact"]["content"] = "Stale writer"
    saved = store.save(first)

    with pytest.raises(RevisionConflict) as conflict:
        store.save(second)

    assert conflict.value.current_revision == saved["revision"] == 1
    assert store.load()["artifact"]["content"] == "First writer"


def test_storage_open_failure_is_reported_without_replacing_saved_state(tmp_path, monkeypatch):
    path = tmp_path / "workspace"
    store = WorkspaceStore(path)
    original = default_state()
    original["artifact"]["content"] = "Last committed value"
    store.save(original)

    edit = store.load()

    class FailedDatabase:
        def __init__(self, _path):
            raise OSError("injected storage open failure")

    monkeypatch.setattr(store_module, "DB", FailedDatabase)
    edit["artifact"]["content"] = "Unsaved local value"
    with pytest.raises(RuntimeError, match="not saved"):
        store.save(edit)
    monkeypatch.setattr(store_module, "DB", DB)

    assert store.load()["artifact"]["content"] == "Last committed value"


def test_message_router_shaped_simulation_is_recipient_scoped_and_idempotent(tmp_path):
    store = WorkspaceStore(tmp_path / "workspace")
    envelope = {
        "projectId": PROJECT_ID,
        "conversationId": "conversation-mira",
        "agentId": "agent-b",
        "clientOperationId": "operation-12345678",
        "payload": {"text": "Plan a small launch"},
    }
    state, duplicate = append_message(store, envelope)
    assert not duplicate
    row = state["conversations"]["conversation-mira"]
    assert [message["role"] for message in row["messages"]] == ["user", "agent"]
    assert "Simulation" in row["messages"][1]["text"]
    assert row["draft"] == ""
    assert state["conversations"]["conversation-aster"]["messages"] == []
    recovered, duplicate = append_message(store, envelope)
    assert duplicate
    assert len(recovered["conversations"]["conversation-mira"]["messages"]) == 2


def test_malformed_envelope_field_types_are_rejected_without_type_errors(tmp_path):
    store = WorkspaceStore(tmp_path / "workspace")
    base = {
        "projectId": PROJECT_ID,
        "conversationId": "conversation-mira",
        "agentId": "agent-b",
        "clientOperationId": "operation-12345678",
        "payload": {"text": "Valid text"},
    }
    malformed_values = [
        ("clientOperationId", None),
        ("clientOperationId", []),
        ("payload", {"text": None}),
    ]
    for key, value in malformed_values:
        malformed = {**base, key: value}
        with pytest.raises(ValueError):
            append_message(store, malformed)
    missing_id = {key: value for key, value in base.items() if key != "clientOperationId"}
    with pytest.raises(ValueError, match="operation ID"):
        append_message(store, missing_id)


def test_mismatched_recipient_and_malformed_state_are_rejected(tmp_path):
    store = WorkspaceStore(tmp_path / "workspace")
    envelope = {
        "projectId": PROJECT_ID,
        "conversationId": "conversation-mira",
        "agentId": "agent-a",
        "clientOperationId": "operation-12345678",
        "payload": {"text": "Wrong recipient"},
    }
    with pytest.raises(ValueError, match="recipient"):
        append_message(store, envelope)

    state = default_state()
    state["conversations"]["conversation-mira"]["sessionId"] = "session-agent-a"
    with pytest.raises(ValueError, match="conversation-mira"):
        validate_state(state)
    assert set(CONVERSATIONS) == {"conversation-aster", "conversation-mira"}
