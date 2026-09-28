"""Post/save authority, component replay protection and separate private identity."""
import importlib
import json
from copy import deepcopy

import pytest
from starlette.requests import Request

from automata.apps.workspace.binding import read_binding
from automata.apps.workspace.posts import CONTEXT
from automata.apps.workspace.receiver import PostReceiver
from automata.apps.workspace.store import WorkspaceStore


def test_browser_posts_are_local_user_and_cannot_supply_author(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_RUNTIME_ROOT", str(tmp_path / "runtime"))
    server = importlib.import_module("automata.apps.workspace.server")
    store = WorkspaceStore(tmp_path / "data")
    monkeypatch.setattr(server, "store", store)
    value = {"operationId": "browser-post", "context": dict(CONTEXT),
             "content": [{"id": "text", "type": "text", "version": 1, "data": {"text": "Input"}}]}
    request = Request({"type": "http", "headers": [(b"sec-fetch-site", b"same-origin")]})
    receipt = server.save_user_post(value, request)
    assert receipt["status"] == "saved"
    message = store.load()["conversations"]["conversation-aster"]["messages"][0]
    assert message["role"] == "user" and "author" not in message
    assert message["delivery"]["status"] == "pending"
    assert server.save_user_post(value, request) == receipt
    assert server.save_user_post({**value, "author": {"kind": "agent"}}, request).status_code == 422
    for site in (b"cross-site", b"none", b""):
        request = Request({"type": "http", "headers": [(b"sec-fetch-site", site)]})
        assert server.save_user_post(value, request).status_code == 403


def test_form_submission_atomic_reference_and_no_reset_replay(tmp_path):
    store = WorkspaceStore(tmp_path)
    definition = {"fields": [{"name": "title", "kind": "text", "label": "Title"}]}
    source = store.post({"operationId": "source-form", "context": dict(CONTEXT), "content": [
        {"id": "form", "type": "form", "version": 1, "data": definition}]},
        provenance={"kind": "agent", "id": "workspace-agent", "sessionId": "synthetic"})
    value = {"operationId": "form-submit", "context": dict(CONTEXT), "content": [
        {"id": "response", "type": "form-response", "version": 1, "data": {
            "messageId": source["messageId"], "componentId": "form", "definition": definition,
            "values": {"title": "Original value"}}}]}
    wrong = deepcopy(value)
    wrong["content"][0]["data"]["definition"] = {"fields": []}
    with pytest.raises(ValueError, match="saved component"):
        store.post(wrong)
    receipt = store.post(value)
    assert store.post(value) == receipt
    with pytest.raises(ValueError, match="already submitted"):
        store.post({**value, "operationId": "new-attempt"})
    state = store.load()
    row = state["conversations"]["conversation-aster"]["messages"][0]
    assert row["interactions"]["form"]["values"] == {"title": "Original value"}
    row["interactions"] = {}
    with pytest.raises(ValueError, match="cannot be reset"):
        store.save(state, browser=True)
    assert store.load()["revision"] == 2


def test_backend_credential_never_bootstraps_browser(tmp_path, monkeypatch):
    endpoint = tmp_path / "app.json"
    endpoint.write_text(json.dumps({"kind": "page", "participant": "workspace-app",
        "wsUrl": "ws://127.0.0.1:49999/ws", "token": "synthetic-only" * 4}))
    endpoint.chmod(0o600)
    monkeypatch.setenv("WORKSPACE_PAGE_ENDPOINT", str(endpoint))
    with pytest.raises(ValueError, match="never browser"):
        read_binding()
    with pytest.raises(ValueError, match="must not share"):
        PostReceiver(WorkspaceStore(tmp_path / "data"), endpoint)
    monkeypatch.delenv("WORKSPACE_PAGE_ENDPOINT")
    endpoint.chmod(0o644)
    with pytest.raises(ValueError, match="private"):
        PostReceiver(WorkspaceStore(tmp_path / "data"), endpoint)
