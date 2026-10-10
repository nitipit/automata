"""Recipient-bound composer preparation and one-shot dispatch."""

import base64
import hashlib
import json
import os
import re
import time
import uuid

from line_contracts import PreparedResult, validate_draft
from line_mentions import composer_mentions, prepare_mention
from line_runtime import HEADER, PREVIEW, ROOM, STATE, require

CHAT_ID = re.compile(r"[A-Za-z0-9_-]+")


def save_state(data):
    data = validate_draft(data)
    temp = STATE / "draft.tmp"
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(data, handle)
        handle.flush()
        os.fsync(handle.fileno())
    temp.replace(STATE / "draft.json")
    directory = os.open(STATE, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def load_state():
    try:
        data = json.loads((STATE / "draft.json").read_text())
    except (OSError, ValueError) as exc:
        from reading_state import ApiError

        raise ApiError(
            "DRAFT_STATE_INVALID", "Cannot decode composer receipt; preserve it"
        ) from exc
    return validate_draft(data)


class Line:
    def __init__(self, page):
        self.page = page
        self.room = page.locator(ROOM)

    def chat(self):
        require(self.room.count() == 1, "Open a chat first")
        header = self.room.locator(HEADER)
        require(header.count() == 1, "Ambiguous chat header")
        return header.inner_text().splitlines()[0].strip()

    def chat_id(self):
        require(self.room.count() == 1, "Open a chat first")
        chat_id = self.room.get_attribute("data-mid")
        require(
            chat_id is not None and CHAT_ID.fullmatch(chat_id),
            "Active chat ID missing; stopped",
        )
        return chat_id

    def verify(self, chat_id, chat=None):
        require(CHAT_ID.fullmatch(chat_id or ""), "A stable chat ID is required")
        require(self.chat_id() == chat_id, "Wrong active chat ID; stopped")
        if chat is not None:
            require(self.chat() == chat, "Active chat name changed; stopped")

    def verify_name(self, chat):
        require(self.chat() == chat, "Wrong active chat; stopped")

    def open(self, chat):
        # Names are not globally unique; refuse multiple matching visible rows.
        names = self.page.get_by_text(chat, exact=True)
        rows = names.locator('xpath=ancestor::*[.//button[@aria-label="Go chatroom"]][1]')
        require(
            rows.count() == 1, "Chat not uniquely visible. Find it manually in LINE, then retry"
        )
        rows.get_by_role("link", name="Go chatroom").click()
        self.room.locator(HEADER).wait_for()
        self.verify_name(chat)

    def snapshot(self, chat_id, chat=None):
        self.verify(chat_id, chat)
        text = self.room.locator("textarea").input_value()
        images = self.room.locator(PREVIEW).evaluate_all("""es => es.map(e => ({
            name:e.title, src:e.querySelector('img')?.src
        }))""")
        mentions = self.room.locator('[part~="mention"]').evaluate_all(
            "es => es.map(e => e.outerHTML)"
        )
        identities = composer_mentions(self.room.locator("textarea"), required=bool(mentions))
        require(len(identities) == len(mentions), "Composer marker and semantic identity differ")
        value = {
            "mention_identities": identities,
            "chat": self.chat(),
            "chat_id": chat_id,
            "route": self.page.url,
            "text": text,
            "images": images,
            "mentions": mentions,
        }
        digest = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        return value, digest

    def empty(self, chat_id, chat=None):
        if (STATE / "draft.json").exists():
            require(
                load_state().get("status") != "uncertain",
                "Previous send uncertain; reconcile explicitly, never prepare or retry",
            )
        value, _ = self.snapshot(chat_id, chat)
        require(
            not value["text"] and not value["images"] and not value["mentions"],
            "Existing draft found; refusing to overwrite or append",
        )

    def prepare(self, chat_id, expected_mention=None):
        value, digest = self.snapshot(chat_id)
        require(value["text"] or value["images"], "Composer is empty")
        verified = value["mention_identities"][0] if value["mention_identities"] else None
        require(verified == expected_mention, "Unexpected composer mention identity; stopped")
        state = {
            "version": 1,
            "kind": "composer",
            "expected_mention": expected_mention,
            "verified_mention": verified,
            "token": str(uuid.uuid4()),
            "digest": digest,
            "status": "prepared",
            "chat_id": chat_id,
            "route": value["route"],
        }
        save_state(state)
        return PreparedResult(
            {
                "status": "prepared",
                "chat": value["chat"],
                "chat_id": chat_id,
                "token": state["token"],
                "characters": len(value["text"]),
                "images": len(value["images"]),
                "mention": verified["name"] if verified else None,
                "mention_identity": verified,
            }
        ).dict()

    def draft(self, chat_id, text, chat=None):
        require(
            text and len(text.encode("utf-16-le")) // 2 <= 10000,
            "Text must be nonempty and at most 10000 UTF-16 units",
        )
        self.empty(chat_id, chat)
        self.room.locator("textarea").fill(text)
        require(
            self.room.locator("textarea").input_value() == text,
            "Draft verification failed; inspect composer",
        )
        return self.prepare(chat_id)

    def mention(self, chat_id, member, text, chat=None, member_id=None):
        return prepare_mention(self, chat_id, member, text, chat, member_id)

    def mention_all(self, chat_id, text, chat=None):
        return prepare_mention(self, chat_id, None, text, chat, mention_all=True)

    def attach(self, chat_id, path, chat=None):
        data = path.read_bytes()
        require(data.startswith(b"\x89PNG\r\n\x1a\n"), "Only PNG images supported currently")
        self.empty(chat_id, chat)
        self.room.locator("textarea").evaluate(
            """(el, data) => {
          const file = new File([Uint8Array.from(atob(data.b64), c=>c.charCodeAt(0))],
                                data.name, {type:'image/png'});
          const dt = new DataTransfer(); dt.items.add(file);
          el.focus(); el.dispatchEvent(new ClipboardEvent('paste', {
            clipboardData:dt, bubbles:true, cancelable:true, composed:true
          }));
        }""",
            {"name": path.name, "b64": base64.b64encode(data).decode()},
        )
        self.room.locator(PREVIEW).wait_for()
        require(self.room.locator(PREVIEW).count() == 1, "Unexpected image count")
        require(
            self.room.locator(PREVIEW).get_attribute("title") == path.name,
            "Image preview filename mismatch",
        )
        return self.prepare(chat_id)

    def send(self, chat_id, token, chat=None):
        if isinstance(token, str) and token.startswith("sticker:"):
            return sticker_operations(self).send(chat_id, token, chat)
        state = load_state()
        require(
            state.get("token") == token and state.get("status") == "prepared",
            "Token missing, consumed, or uncertain; do not retry a send",
        )
        require(
            state.get("chat_id") == chat_id and isinstance(state.get("route"), str),
            "Token has no recipient identity binding; prepare a new draft",
        )
        require(
            self.page.url == state["route"],
            "LINE navigation changed since preparation; stopped",
        )
        value, digest = self.snapshot(chat_id, chat)
        actual = value["mention_identities"][0] if value["mention_identities"] else None
        require(
            actual == state["expected_mention"] == state["verified_mention"],
            "Prepared mention identity changed; stopped",
        )
        require(digest == state["digest"], "Chat or draft changed; stopped")
        require(value["text"] or value["images"], "Empty draft")
        require(
            self.page.get_by_role("option").count() == 0,
            "Active picker would consume Enter instead of dispatching; stopped",
        )
        # Consume before dispatch. Crashes/timeouts must never authorize replay.
        state["status"] = "uncertain"
        save_state(state)
        self.verify(chat_id, chat)
        self.room.locator("textarea").press("Enter")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current, _ = self.snapshot(chat_id, chat)
            if not current["text"] and not current["images"]:
                state["status"] = "dispatched"
                save_state(state)
                return {
                    "status": "dispatched",
                    "chat": value["chat"],
                    "chat_id": chat_id,
                    "delivery": (
                        "Composer cleared; server delivery/read receipt not verified. "
                        "Do not resend."
                    ),
                }
            self.page.wait_for_timeout(100)
        raise RuntimeError("Send outcome uncertain. Inspect LINE; never automatically retry")


def sticker_operations(line):
    from sticker_api import StickerOperations, verified_picker

    return StickerOperations(line, STATE, verified_picker)
