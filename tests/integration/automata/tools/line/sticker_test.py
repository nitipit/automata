"""Offline lifecycle fixtures; these do NOT verify LINE's live popup selectors."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).parents[5] / "src/automata/tools/line"
spec = importlib.util.spec_from_file_location("sticker_fixture", SOURCE / "sticker_api.py")
stickers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stickers)
STICKER = {
    "package_id": "package-one",
    "sticker_id": "sticker-one",
    "preview_url": "https://fixture.invalid/stickers/one.png",
}


class FakeLine:
    def __init__(self):
        self.value = {
            "chat_id": "chat-one",
            "route": "fixture://line#/chats/chat-one",
            "chat": "Fixture",
            "text": "",
            "images": [],
            "mentions": [],
        }

    def snapshot(self, chat_id, chat=None):
        if chat_id != self.value["chat_id"] or (chat is not None and chat != self.value["chat"]):
            raise RuntimeError("Wrong active chat")
        return dict(self.value), stickers.fingerprint(self.value)


class FakePicker:
    def __init__(self, context):
        self.context = context
        self.closed = False

    def catalog(self, package_id, limit):
        return {"stickers": [dict(STICKER)][:limit], "coverage": {"complete": False}}

    def find(self, package_id, sticker_id):
        if self.context.ambiguous:
            raise stickers.StickerError("STICKER_AMBIGUOUS", "Ambiguous sticker")
        return dict(self.context.selection)

    def outgoing_ids(self):
        return ["old-message"]

    def click_once(self, selected):
        # The central invariant is checked at the actual side-effect boundary.
        assert self.context.service.load()["status"] == "uncertain"
        self.context.clicks += 1
        if self.context.click_error:
            raise RuntimeError("Connection lost during click")

    def wait_outgoing(self, selected, baseline):
        if self.context.wait_error:
            raise TimeoutError("No evidence before deadline")
        return self.context.evidence

    def close(self):
        self.context.close_calls += 1
        if self.context.close_error:
            raise RuntimeError("Close failed")
        self.closed = True


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SOURCE))
    line = FakeLine()
    context = SimpleNamespace(
        line=line,
        clicks=0,
        close_calls=0,
        pickers=[],
        selection=dict(STICKER),
        ambiguous=False,
        click_error=False,
        wait_error=False,
        close_error=False,
        evidence={
            "message_id": "new-message",
            "chat_id": "chat-one",
            "direction": "outgoing",
            "package_id": "package-one",
            "sticker_id": "sticker-one",
        },
    )

    def factory(line, chat_id):
        picker = FakePicker(context)
        context.pickers.append(picker)
        return picker

    context.factory = factory
    context.service = stickers.StickerOperations(line, tmp_path, factory)
    return context


def prepare(context):
    return context.service.prepare("chat-one", "package-one", "sticker-one")


def test_catalog_is_bounded_metadata_and_closes_owned_picker(setup):
    result = setup.service.inspect("chat-one", limit=1)
    assert result["catalog"]["coverage"]["complete"] is False
    assert result["cleanup"] == {"attempted": True, "closed": True}
    assert setup.clicks == 0 and not setup.service.path.exists()
    with pytest.raises(stickers.StickerError, match="limit"):
        setup.service.inspect("chat-one", limit=101)


def test_prepare_is_metadata_only_with_bound_identity(setup):
    result = prepare(setup)
    saved = setup.service.load()
    assert result["token"].startswith("sticker:")
    assert saved["status"] == "prepared" and saved["chat_id"] == "chat-one"
    assert saved["route"] == setup.line.value["route"]
    assert saved["sticker"] == STICKER
    assert setup.clicks == 0 and setup.pickers[0].closed
    assert setup.service.path.stat().st_mode & 0o777 == 0o600


def test_success_is_one_click_and_new_outgoing_evidence(setup):
    token = prepare(setup)["token"]
    result = setup.service.send("chat-one", token)
    assert result["status"] == "dispatched" and result["retry_send"] is False
    assert result["cleanup"]["closed"] is True
    assert setup.clicks == 1
    assert setup.service.load()["status"] == "dispatched"
    with pytest.raises(stickers.StickerError, match="consumed"):
        setup.service.send("chat-one", token)
    assert setup.clicks == 1


@pytest.mark.parametrize("change", ["recipient", "route", "text", "image", "mention", "preview"])
def test_changed_context_or_identity_never_clicks(setup, change):
    token = prepare(setup)["token"]
    if change == "recipient":
        setup.line.value["chat_id"] = "chat-two"
    elif change == "route":
        setup.line.value["route"] += "/changed"
    elif change == "text":
        setup.line.value["text"] = "Existing draft"
    elif change == "image":
        setup.line.value["images"] = [{"name": "keep.png"}]
    elif change == "mention":
        setup.line.value["mentions"] = ["native-mention"]
    else:
        setup.selection["preview_url"] += "?changed=1"
    with pytest.raises(stickers.StickerError) as error:
        setup.service.send("chat-one", token)
    assert error.value.code == "STICKER_SEND_BLOCKED"
    assert setup.clicks == 0


@pytest.mark.parametrize(
    "failure", ["click", "timeout", "old", "wrong-chat", "wrong-sticker", "none"]
)
def test_uncertain_is_consumed_closes_picker_and_holds_new_preparation(setup, failure):
    token = prepare(setup)["token"]
    if failure == "click":
        setup.click_error = True
    elif failure == "timeout":
        setup.wait_error = True
    elif failure == "old":
        setup.evidence["message_id"] = "old-message"
    elif failure == "wrong-chat":
        setup.evidence["chat_id"] = "chat-two"
    elif failure == "wrong-sticker":
        setup.evidence["sticker_id"] = "another-sticker"
    else:
        setup.evidence = None
    with pytest.raises(stickers.StickerError) as error:
        setup.service.send("chat-one", token)
    assert error.value.code == "STICKER_SEND_UNCERTAIN"
    assert error.value.details["cleanup"]["closed"] is True
    assert setup.service.load()["status"] == "uncertain"
    assert setup.clicks == 1
    with pytest.raises(stickers.StickerError, match="uncertain"):
        setup.service.send("chat-one", token)
    with pytest.raises(stickers.StickerError) as blocked:
        prepare(setup)
    assert blocked.value.code == "STICKER_RECONCILIATION_REQUIRED"
    assert setup.clicks == 1


def test_close_failure_does_not_reclassify_confirmed_dispatch(setup):
    token = prepare(setup)["token"]
    setup.close_error = True
    result = setup.service.send("chat-one", token)
    assert result["status"] == "dispatched"
    assert result["cleanup"]["closed"] is False
    assert setup.service.load()["status"] == "dispatched"
    with pytest.raises(stickers.StickerError):
        setup.service.send("chat-one", token)
    assert setup.clicks == 1


def test_uncertain_close_failure_stays_uncertain(setup):
    token = prepare(setup)["token"]
    setup.wait_error = setup.close_error = True
    with pytest.raises(stickers.StickerError) as error:
        setup.service.send("chat-one", token)
    assert error.value.details["cleanup"]["closed"] is False
    assert setup.service.load()["status"] == "uncertain"


def test_ambiguous_identity_is_never_prepared(setup):
    setup.ambiguous = True
    with pytest.raises(stickers.StickerError) as error:
        prepare(setup)
    assert error.value.code == "STICKER_AMBIGUOUS"
    assert not setup.service.path.exists() and setup.clicks == 0
    assert setup.pickers[0].closed


def test_wrong_requested_identity_is_not_prepared(setup):
    with pytest.raises(stickers.StickerError, match="identity"):
        setup.service.prepare("chat-one", "wrong-package", "sticker-one")
    assert setup.clicks == 0 and not setup.service.path.exists()


def test_corrupt_receipt_is_preserved_not_replaced(setup):
    setup.service.path.write_text('{"corrupt": true}')
    before = setup.service.path.read_bytes()
    with pytest.raises(stickers.StickerError) as error:
        prepare(setup)
    assert error.value.code == "STICKER_STATE_INVALID"
    assert setup.service.path.read_bytes() == before


def test_failed_consume_write_prevents_click(setup, monkeypatch):
    token = prepare(setup)["token"]

    def failure(state):
        raise OSError("disk full")

    monkeypatch.setattr(setup.service, "save", failure)
    with pytest.raises(stickers.StickerError) as error:
        setup.service.send("chat-one", token)
    assert error.value.code == "STICKER_SEND_BLOCKED"
    assert setup.clicks == 0 and setup.pickers[-1].closed


def test_preexisting_uncertainty_does_not_touch_composer_receipt(setup):
    draft = setup.service.path.parent / "draft.json"
    draft.write_text(json.dumps({"token": "existing-composer-token", "status": "prepared"}))
    before = draft.read_bytes()
    token = prepare(setup)["token"]
    setup.wait_error = True
    with pytest.raises(stickers.StickerError):
        setup.service.send("chat-one", token)
    assert draft.read_bytes() == before


def test_partial_picker_cleanup_failure_survives_error_wrapping(setup):
    cleanup = {"attempted": True, "closed": False, "error": "close failed"}

    def failure(line, chat_id):
        raise stickers.StickerError("STICKER_PICKER_FAILED", "UI failed", cleanup=cleanup)

    token = prepare(setup)["token"]
    setup.service.picker_factory = failure
    for operation in (
        lambda: setup.service.inspect("chat-one"),
        lambda: prepare(setup),
        lambda: setup.service.send("chat-one", token),
    ):
        with pytest.raises(stickers.StickerError) as error:
            operation()
        assert error.value.details["cleanup"] == cleanup
    assert setup.clicks == 0


def test_unverified_picker_is_explicitly_fail_closed(setup):
    def unverified(line, chat_id):
        raise stickers.StickerError("STICKER_UI_UNVERIFIED", "Unknown live UI")

    service = stickers.StickerOperations(setup.line, setup.service.path.parent, unverified)
    with pytest.raises(stickers.StickerError) as error:
        service.prepare("chat-one", "package-one", "sticker-one")
    assert error.value.code == "STICKER_UI_UNVERIFIED"
    assert error.value.details["cleanup"]["attempted"] is False
    assert not service.path.exists()
