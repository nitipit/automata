"""Synthetic state only: atomic post/receipt and immutable browser boundaries."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from shelfdb.shelf import DB

from automata.apps.workspace.posts import CONTEXT
from automata.apps.workspace.store import (
    PROJECT_ID,
    RevisionConflict,
    WorkspaceStore,
    default_state,
)

AUTHOR = {"kind": "agent", "id": "workspace-agent", "sessionId": "synthetic-session"}


def envelope(operation="operation-1", text="Hello"):
    return {"operationId": operation, "context": dict(CONTEXT),
            "content": [{"id": "text", "type": "text", "version": 1, "data": {"text": text}}]}


def test_post_retry_restart_and_conflict(tmp_path):
    store = WorkspaceStore(tmp_path)
    receipt = store.post(envelope(), provenance=AUTHOR)
    assert receipt["status"] == "saved" and receipt["seq"] == 1
    assert receipt["createdAt"] and receipt["messageId"]
    restarted = WorkspaceStore(tmp_path)
    assert restarted.post(envelope(), provenance={**AUTHOR, "sessionId": "new-session"}) == receipt
    assert restarted.load()["revision"] == 1
    with pytest.raises(ValueError, match="different payload"):
        restarted.post(envelope(text="Changed"), provenance=AUTHOR)
    message = restarted.load()["conversations"]["conversation-aster"]["messages"][0]
    assert message["author"]["sessionId"] == "synthetic-session"
    # Opposite direction is independently scoped, never threaded by operationId.
    user = restarted.post(envelope())
    assert user["seq"] == 2 and user["messageId"] != receipt["messageId"]


def test_concurrent_stores_same_operation_have_one_atomic_receipt(tmp_path):
    def post(_):
        return WorkspaceStore(tmp_path).post(envelope(), provenance=AUTHOR)
    with ThreadPoolExecutor(max_workers=8) as workers:
        receipts = list(workers.map(post, range(24)))
    assert all(value == receipts[0] for value in receipts)
    state = WorkspaceStore(tmp_path).load()
    assert state["revision"] == 1 and len(state["postOperations"]) == 1
    assert len(state["conversations"]["conversation-aster"]["messages"]) == 1


@pytest.mark.parametrize("author", [
    {**AUTHOR, "kind": "page"}, {**AUTHOR, "id": "other-agent"},
    {**AUTHOR, "sessionId": ""}, {**AUTHOR, "sessionId": None}, {},
])
def test_reject_unauthenticated_author(tmp_path, author):
    with pytest.raises(ValueError, match="Unauthorized"):
        WorkspaceStore(tmp_path).post(envelope(), provenance=author)


@pytest.mark.parametrize("change", [
    lambda v: v.update(author=AUTHOR),
    lambda v: v["context"].update(projectId="northstar"),
    lambda v: v["context"].update(conversationId="conversation-mira"),
    lambda v: v["context"].update(webboardId="other"),
    lambda v: v["context"].update(componentId="not-context"),
    lambda v: v["content"][0].update(type="executable-html"),
])
def test_reject_invalid_envelope_and_destination(tmp_path, change):
    value = envelope()
    change(value)
    with pytest.raises(ValueError):
        WorkspaceStore(tmp_path).post(value, provenance=AUTHOR)


def test_stale_and_current_revision_cannot_remove_or_edit_backend_posts(tmp_path):
    store = WorkspaceStore(tmp_path)
    stale = store.load()
    store.post(envelope(), provenance=AUTHOR)
    with pytest.raises(RevisionConflict):
        store.save(stale, browser=True)
    for change in (
        lambda s: s["conversations"]["conversation-aster"]["messages"].clear(),
        lambda s: s["conversations"]["conversation-aster"]["messages"][0].update(text="forged"),
        lambda s: s["postOperations"].clear(),
        lambda s: s["conversations"]["conversation-aster"]["messages"].append({
            **s["conversations"]["conversation-aster"]["messages"][0], "id": "forged"}),
    ):
        value = store.load()
        change(value)
        with pytest.raises(ValueError, match="backend-owned"):
            store.save(value, browser=True)
    value = store.load()
    value["conversations"]["conversation-aster"]["draft"] = "Preserve draft"
    store.save(value, browser=True)
    assert store.load()["revision"] == 2


def test_legacy_additive_normalization_no_read_rewrite(tmp_path):
    store = WorkspaceStore(tmp_path)
    old = default_state()
    old["revision"] = 8
    old["conversations"]["conversation-mira"]["draft"] = "Untouched"
    old["conversations"]["conversation-aster"]["messages"] = [
        {"id": "legacy", "operationId": "old-operation", "role": "agent", "text": "History"}]
    original = deepcopy(old)
    with DB(str(tmp_path)) as db, db.transaction(write=True) as tx:
        tx.shelf("workspace").put(PROJECT_ID, old)
    loaded = store.load()
    assert loaded["revision"] == 8
    message = loaded["conversations"]["conversation-aster"]["messages"][0]
    assert message["messageId"] == "legacy" and message["seq"] == 1
    assert message["createdAt"] is None and "author" not in message
    with DB(str(tmp_path)) as db, db.transaction(write=False) as tx:
        assert tx.shelf("workspace").key(PROJECT_ID).item().value == original
    receipt = store.post(envelope(), provenance=AUTHOR)
    assert receipt["seq"] == 2 and store.load()["revision"] == 9
    assert store.load()["conversations"]["conversation-mira"]["draft"] == "Untouched"


def test_transaction_rolls_back_failed_post(tmp_path, monkeypatch):
    from automata.apps.workspace import store as module
    store = WorkspaceStore(tmp_path)
    original = module.apply_post

    def fail(*args):
        original(*args)
        raise RuntimeError("Injected before commit")

    monkeypatch.setattr(module, "apply_post", fail)
    with pytest.raises(RuntimeError):
        store.post(envelope(), provenance=AUTHOR)
    monkeypatch.setattr(module, "apply_post", original)
    assert store.load()["revision"] == 0
    assert store.post(envelope(), provenance=AUTHOR)["seq"] == 1
