"""Storage envelopes and explicit non-destructive v2 component normalization."""
from copy import deepcopy

import pytest
from shelfdb.shelf import DB

from automata.apps.workspace.binding import read_binding
from automata.apps.workspace.store import PROJECT_ID, WorkspaceStore, default_state, validate_state


def example_message():
    return {"id": "message-test", "operationId": "operation-test", "role": "agent", "text": "Hello",
            "content": [{"id": "intro", "type": "text", "version": 1, "data": {"text": "Hello"}},
                        {"id": "form", "type": "form", "version": 1, "data": {"fields": []}}],
            "interactions": {"form": {"status": "draft", "values": {"title": "Retain draft"}}}}


def test_legacy_v2_read_adds_content_without_rewriting_db(tmp_path):
    store = WorkspaceStore(tmp_path)
    old = default_state()
    row = old["conversations"]["conversation-aster"]
    row["draft"] = "Unsent text"
    row["messages"] = [{"id": "old-message", "operationId": "old-operation",
                        "role": "agent", "text": "Historical text"}]
    original = deepcopy(old)
    with DB(str(tmp_path)) as database, database.transaction(write=True) as tx:
        tx.shelf("workspace").put(PROJECT_ID, old)
    loaded = store.load()
    message = loaded["conversations"]["conversation-aster"]["messages"][0]
    assert loaded["version"] == 2 and loaded["revision"] == 0
    assert message["text"] == message["content"][0]["data"]["text"] == "Historical text"
    assert message["provenance"] == "historical-simulation"
    assert loaded["conversations"]["conversation-aster"]["draft"] == "Unsent text"
    with DB(str(tmp_path)) as database, database.transaction(write=False) as tx:
        assert tx.shelf("workspace").key(PROJECT_ID).item().value == original
    store.save(loaded)
    assert store.load()["artifact"] == original["artifact"]


def test_components_interactions_roundtrip_without_execution(tmp_path):
    store = WorkspaceStore(tmp_path)
    state = default_state()
    message = example_message()
    state["conversations"]["conversation-aster"]["messages"].append(message)
    store.save(state)
    assert store.load()["conversations"]["conversation-aster"]["messages"][0] == message
    # Python does NOT duplicate the catalog Form schema: JS rejects this empty
    # field list before rendering. Storage never executes payloads.


@pytest.mark.parametrize("change", [
    lambda m: m["content"].append(m["content"][0]),
    lambda m: m["content"][0].update(version=True),
    lambda m: m["content"][0].update(id="../unsafe"),
    lambda m: m["interactions"].update(other={"status": "draft"}),
    lambda m: m["interactions"]["form"].update(status="execute"),
    lambda m: m["interactions"]["form"].update(values={"title": 42}),
    lambda m: m.update(delivery={"status": "pending", "operationId": "not valid"}),
])
def test_malformed_component_envelopes_rejected(change):
    state = default_state()
    message = example_message()
    change(message)
    state["conversations"]["conversation-aster"]["messages"].append(message)
    with pytest.raises(ValueError):
        validate_state(state)


def test_bootstrap_rejects_agent_credentials_and_remote_router(tmp_path, monkeypatch):
    import json
    endpoint = tmp_path / "endpoint.json"
    monkeypatch.setenv("WORKSPACE_PAGE_ENDPOINT", str(endpoint))
    monkeypatch.setenv("WORKSPACE_AGENT_PARTICIPANT", "workspace-agent")
    monkeypatch.setenv("WORKSPACE_AGENT_ID", "agent-automata")
    endpoint.write_text(json.dumps({"wsUrl": "ws://127.0.0.1:8791/ws", "kind": "agent",
                                    "participant": "page", "token": "test-only"}))
    with pytest.raises(ValueError, match="Only page"):
        read_binding()
    endpoint.write_text(json.dumps({"wsUrl": "ws://example.com:8791/ws", "kind": "page"}))
    with pytest.raises(ValueError, match="loopback"):
        read_binding()
    endpoint.write_text(json.dumps({"wsUrl": "ws://127.0.0.1:8791/ws", "kind": "page",
                                    "participant": "page", "token": "test-only",
                                    "secret": "not exposed"}))
    assert "secret" not in read_binding()["credentials"]
