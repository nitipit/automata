"""Sticker intent lifecycle, separate from composer drafts and UI adapter mechanics.

One workspace receipt and the caller's operation lock protect one active intent.
A consumed intent is never made prepared again, including after popup cleanup.
UI adapters must bind one fresh picker to the exact active LINE index page.
"""

import hashlib
import json
import uuid

TOKEN_PREFIX = "sticker:"


class StickerError(RuntimeError):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code = code
        self.details = details


def require(condition, code, message):
    if not condition:
        raise StickerError(code, message)


def identity(value):
    """Only verified, stable catalog identities can become an intent."""
    fields = ("package_id", "sticker_id", "preview_url")
    require(
        isinstance(value, dict)
        and all(isinstance(value.get(key), str) and value[key] for key in fields),
        "STICKER_IDENTITY_INVALID",
        "Sticker package, ID, or preview identity missing",
    )
    return {key: value[key] for key in fields}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class StickerOperations:
    """Call only under LINE's existing operation lock and verified profile binding.

    picker_factory(line, chat_id) returns an operation-owned picker with catalog,
    find, outgoing_ids, click_once, wait_outgoing, and close methods. find must not
    click a sticker. The factory must clean up its own partial acquisition on error;
    this owner never closes pre-existing or ambiguously related browser pages.
    """

    def __init__(self, line, state_root, picker_factory):
        self.line = line
        self.path = state_root / "sticker.json"
        self.picker_factory = picker_factory

    def load(self):
        if not self.path.exists():
            return None
        try:
            state = json.loads(self.path.read_text())
            valid = (
                isinstance(state, dict)
                and state.get("version") == 1
                and state.get("kind") == "sticker"
                and isinstance(state.get("token"), str)
                and state["token"].startswith(TOKEN_PREFIX)
                and state.get("status") in {"prepared", "uncertain", "dispatched"}
                and all(
                    isinstance(state.get(key), str) and state[key]
                    for key in ("chat_id", "route", "composer_digest", "sticker_digest")
                )
            )
            require(valid, "STICKER_STATE_INVALID", "Invalid sticker receipt; preserve it")
            selected = identity(state.get("sticker"))
            require(
                fingerprint(selected) == state["sticker_digest"],
                "STICKER_STATE_INVALID",
                "Sticker receipt identity changed; preserve it",
            )
            return state
        except (OSError, ValueError, TypeError, StickerError) as exc:
            raise StickerError(
                "STICKER_STATE_INVALID", "Cannot validate sticker receipt; preserve it"
            ) from exc

    def save(self, state):
        from reading_state import atomic, json_bytes

        atomic(self.path, json_bytes(state))

    def context(self, chat_id, chat=None):
        value, digest = self.line.snapshot(chat_id, chat)
        require(
            not value["text"] and not value["images"] and not value["mentions"],
            "STICKER_COMPOSER_NOT_EMPTY",
            "Existing draft found; stickers cannot be combined with a composer draft",
        )
        return value, digest

    @staticmethod
    def close(picker):
        if picker is None:
            return {"attempted": False, "closed": False}
        try:
            picker.close()
            return {"attempted": True, "closed": True}
        except Exception as exc:
            return {"attempted": True, "closed": False, "error": str(exc)}

    def inspect(self, chat_id, package_id=None, limit=100, chat=None):
        require(1 <= limit <= 100, "INVALID_ARGUMENT", "Catalog limit must be 1..100")
        before, digest = self.context(chat_id, chat)
        picker = None
        try:
            picker = self.picker_factory(self.line, chat_id)
            result = picker.catalog(package_id, limit)
            after, current = self.context(chat_id, chat)
            require(
                current == digest and after["route"] == before["route"],
                "STICKER_CONTEXT_CHANGED",
                "Recipient or composer changed during catalog inspection",
            )
        except Exception as exc:
            cleanup = self.close(picker)
            if isinstance(exc, StickerError):
                exc.details.setdefault("cleanup", cleanup)
                raise
            raise StickerError("STICKER_INSPECTION_FAILED", str(exc), cleanup=cleanup) from exc
        return {"chat_id": chat_id, "catalog": result, "cleanup": self.close(picker)}

    def prepare(self, chat_id, package_id, sticker_id, chat=None):
        previous = self.load()
        require(
            previous is None or previous["status"] != "uncertain",
            "STICKER_RECONCILIATION_REQUIRED",
            "An uncertain sticker intent remains; do not prepare another or reset its receipt",
        )
        before, digest = self.context(chat_id, chat)
        picker = None
        try:
            picker = self.picker_factory(self.line, chat_id)
            selected = identity(picker.find(package_id, sticker_id))
            require(
                selected["package_id"] == package_id and selected["sticker_id"] == sticker_id,
                "STICKER_IDENTITY_CHANGED",
                "Requested sticker identity did not match the catalog",
            )
            after, current = self.context(chat_id, chat)
            require(
                current == digest and after["route"] == before["route"],
                "STICKER_CONTEXT_CHANGED",
                "Recipient or composer changed during preparation",
            )
            state = {
                "version": 1,
                "kind": "sticker",
                "token": TOKEN_PREFIX + str(uuid.uuid4()),
                "status": "prepared",
                "chat_id": chat_id,
                "route": before["route"],
                "composer_digest": digest,
                "sticker": selected,
                "sticker_digest": fingerprint(selected),
            }
            self.save(state)
        except Exception as exc:
            cleanup = self.close(picker)
            if isinstance(exc, StickerError):
                exc.details.setdefault("cleanup", cleanup)
                raise
            raise StickerError("STICKER_PREPARATION_FAILED", str(exc), cleanup=cleanup) from exc
        return {
            "status": "prepared",
            "kind": "sticker",
            "chat_id": chat_id,
            "token": state["token"],
            "sticker": selected,
            "cleanup": self.close(picker),
        }

    def send(self, chat_id, token, chat=None):
        state = self.load()
        require(
            state is not None and state["token"] == token and state["status"] == "prepared",
            "STICKER_TOKEN_INVALID",
            "Sticker token missing, consumed, or uncertain; do not retry",
        )
        require(state["chat_id"] == chat_id, "STICKER_WRONG_CHAT", "Wrong token recipient")
        picker = None
        attempted = False
        try:
            before, digest = self.context(chat_id, chat)
            require(
                before["route"] == state["route"] and digest == state["composer_digest"],
                "STICKER_CONTEXT_CHANGED",
                "Recipient route or composer changed",
            )
            picker = self.picker_factory(self.line, chat_id)
            selected = identity(
                picker.find(**{key: state["sticker"][key] for key in ("package_id", "sticker_id")})
            )
            require(
                fingerprint(selected) == state["sticker_digest"],
                "STICKER_IDENTITY_CHANGED",
                "Sticker identity or preview changed",
            )
            baseline = set(picker.outgoing_ids())
            state["status"] = "uncertain"
            self.save(state)  # Durably consume BEFORE entering any dispatch path.
            attempted = True
            current, current_digest = self.context(chat_id, chat)
            require(
                current["route"] == state["route"] and current_digest == digest,
                "STICKER_CONTEXT_CHANGED",
                "Context changed immediately before dispatch",
            )
            picker.click_once(selected)
            evidence = picker.wait_outgoing(selected, baseline)
            current, _ = self.context(chat_id, chat)
            require(
                current["route"] == state["route"]
                and isinstance(evidence, dict)
                and isinstance(evidence.get("message_id"), str)
                and evidence["message_id"]
                and evidence["message_id"] not in baseline
                and evidence.get("chat_id") == chat_id
                and evidence.get("direction") == "outgoing"
                and evidence.get("sticker_id") == selected["sticker_id"]
                and evidence.get("package_id") == selected["package_id"],
                "STICKER_EVIDENCE_MISSING",
                "No matching new outgoing sticker evidence",
            )
            state["status"] = "dispatched"
            state["evidence"] = evidence
            self.save(state)
        except Exception as exc:
            cleanup = self.close(picker)
            if picker is None and isinstance(exc, StickerError):
                cleanup = exc.details.get("cleanup", cleanup)
            raise StickerError(
                "STICKER_SEND_UNCERTAIN" if attempted else "STICKER_SEND_BLOCKED",
                "Sticker outcome uncertain; inspect LINE, never retry" if attempted else str(exc),
                cleanup=cleanup,
                cause=getattr(exc, "code", type(exc).__name__),
                retry_send=False,
            ) from exc
        return {
            "status": "dispatched",
            "kind": "sticker",
            "chat_id": chat_id,
            "sticker": selected,
            "evidence": evidence,
            "cleanup": self.close(picker),
            "delivery": "New outgoing sticker observed in UI; server delivery/read unverified.",
            "retry_send": False,
        }


def verified_picker(line, chat_id):
    from sticker_ui import open_picker

    return open_picker(line, chat_id)
