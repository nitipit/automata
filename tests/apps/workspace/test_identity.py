"""Explicit assignment and non-destructive legacy preservation (synthetic data)."""
import json
from copy import deepcopy

import pytest
from shelfdb.shelf import DB

from automata.apps.workspace.binding import read_binding
from automata.apps.workspace.store import PROJECT_ID, WorkspaceStore, default_state, validate_state


@pytest.fixture
def provision(tmp_path, monkeypatch):
    endpoint = tmp_path / "synthetic-page.json"
    endpoint.write_text(json.dumps({"kind": "page", "wsUrl": "ws://127.0.0.1:8791/ws",
                                    "participant": "test-page", "token": "synthetic-only"}))
    monkeypatch.setenv("WORKSPACE_PAGE_ENDPOINT", str(endpoint))
    monkeypatch.setenv("WORKSPACE_AGENT_ID", "agent-automata")
    monkeypatch.setenv("WORKSPACE_AGENT_PARTICIPANT", "workspace-agent")


def test_explicit_stable_assignment(provision):
    binding = read_binding()
    assert binding["agentId"] == "agent-automata"
    assert binding["displayName"] == "Automata"
    assert binding["conversationId"] == "conversation-aster"
    assert binding["to"] == "workspace-agent"
    assert "sessionId" not in binding  # Never invent runtime identity from a name.


@pytest.mark.parametrize("name,value", [
    ("WORKSPACE_AGENT_ID", ""), ("WORKSPACE_AGENT_ID", "agent-a"),
    ("WORKSPACE_AGENT_ID", "Automata"), ("WORKSPACE_AGENT_PARTICIPANT", "other-agent"),
])
def test_no_implicit_assignment_by_name_or_online_participant(provision, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match="Explicit Automata assignment"):
        read_binding()


def test_no_endpoint_means_no_connection(monkeypatch):
    monkeypatch.delenv("WORKSPACE_PAGE_ENDPOINT", raising=False)
    assert read_binding() is None


def test_v2_mixed_history_is_preserved_without_relabeling_or_transfer(tmp_path):
    old = default_state()
    old["view"]["selectedConversationId"] = "conversation-mira"
    old["conversations"]["conversation-mira"]["draft"] = "Mira private legacy draft"
    aster = old["conversations"]["conversation-aster"]
    aster["draft"] = "Aster unsent draft"
    aster["messages"] = [
        {"id": "sim", "operationId": "sim-operation", "role": "agent",
         "text": "[Simulation] Aster noted a historical message"},
        {"id": "user", "operationId": "real-operation", "role": "user", "text": "Synthetic user",
         "content": [{"id": "text", "type": "text", "version": 1,
                      "data": {"text": "Synthetic user"}}],
         "delivery": {"status": "completed", "operationId": "real-operation",
                      "participant": "workspace-agent", "sessionId": "old-test-session"}},
        {"id": "reply", "operationId": "real-operation", "role": "agent", "text": "Synthetic form",
         "content": [{"id": "form", "type": "form", "version": 1,
                      "data": {"fields": [{"name": "title", "kind": "text", "label": "Title"}]}}],
         "interactions": {"form": {"status": "completed", "operationId": "form-operation",
                                    "values": {"title": "Previously submitted"},
                                    "participant": "workspace-agent",
                                    "sessionId": "old-test-session"}}},
    ]
    original = deepcopy(old)
    store = WorkspaceStore(tmp_path)
    with DB(str(tmp_path)) as db, db.transaction(write=True) as tx:
        tx.shelf("workspace").put(PROJECT_ID, old)
    loaded = store.load()
    assert (loaded["conversations"]["conversation-mira"]
            == original["conversations"]["conversation-mira"])
    assert loaded["artifact"] == original["artifact"] and loaded["view"] == original["view"]
    messages = loaded["conversations"]["conversation-aster"]["messages"]
    assert messages[0]["provenance"] == "historical-simulation"
    assert messages[0]["text"] == aster["messages"][0]["text"]
    assert messages[1:] == [
        {**message, "messageId": message["id"], "seq": seq, "createdAt": None}
        for seq, message in enumerate(aster["messages"][1:], 2)
    ]
    assert "author" not in messages[2]  # No retroactive author fabrication.
    with DB(str(tmp_path)) as db, db.transaction(write=False) as tx:
        assert tx.shelf("workspace").key(PROJECT_ID).item().value == original
    store.save(loaded)
    assert store.load()["conversations"] == loaded["conversations"]


def test_author_identity_is_bounded_to_assignment():
    state = default_state()
    message = {"id": "reply", "operationId": "operation", "role": "agent", "text": "Test",
               "author": {"agentId": "agent-automata", "participant": "workspace-agent",
                          "sessionId": "test-session"}}
    state["conversations"]["conversation-aster"]["messages"].append(message)
    validate_state(state)
    wrong_conversation = default_state()
    wrong_conversation["conversations"]["conversation-mira"]["messages"].append(message)
    with pytest.raises(ValueError, match="does not own"):
        validate_state(wrong_conversation)
    for field, value in [("agentId", "other-agent"), ("participant", "other-participant"),
                         ("sessionId", ""), ("sessionId", "not an id")]:
        altered = deepcopy(state)
        altered["conversations"]["conversation-aster"]["messages"][0]["author"][field] = value
        with pytest.raises(ValueError, match="assigned author"):
            validate_state(altered)
