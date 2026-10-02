"""Volatile browser-requested pairing; locators are lookup keys, not credentials.

All mutations run synchronously on the auth owner's event loop. Sessions remain
in AuthStore; restart discards requests, and a lost committed cookie needs explicit
operator repair rather than token replay. No pending request authenticates Router.
"""
from __future__ import annotations

import re
import secrets
import time
from typing import Callable

from .auth_store import AuthStore, digest

REQUEST_SECONDS = 300
MAX_REQUESTS = 32
CAPABILITY = re.compile(r"[0-9a-f]{64}\Z")
LOCATOR = re.compile(r"RP-[0-9A-F]{10}\Z")


class RequestLimit(ValueError):
    """A bounded request budget is exhausted; caller must not auto-retry."""


class Bucket:
    def __init__(self, capacity: int, per_minute: int):
        self.capacity, self.rate = capacity, per_minute / 60
        self.tokens, self.updated = float(capacity), time.monotonic()

    def take(self) -> None:
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
        self.updated = now
        if self.tokens < 1:
            raise RequestLimit("Request rate reached")
        self.tokens -= 1


class PairingRequests:
    def __init__(self, store: AuthStore):
        self.store = store
        self.presence: Callable[[str], bool] | None = None
        self.records: dict[str, dict] = {}
        self.creation = Bucket(8, 8)
        self.operations = Bucket(30, 120)

    @staticmethod
    def capability(value: str) -> str:
        if not isinstance(value, str) or not CAPABILITY.fullmatch(value):
            raise ValueError("Invalid requester capability")
        return digest(value)

    @staticmethod
    def view(record: dict) -> dict:
        return {key: record[key] for key in
                ("request", "state", "expiresAt", "participant") if key in record}

    def lookup(self, locator: str) -> dict:
        if not isinstance(locator, str) or not LOCATOR.fullmatch(locator):
            raise ValueError("Invalid request locator")
        record = self.records.get(locator)
        if record is None:
            raise ValueError("Request unavailable; restart or expiry requires fresh intent")
        if record["expiresAt"] <= time.time() and record["state"] in ("pending", "approved"):
            record["state"] = "expired"
        return record

    def owned(self, locator: str, capability: str) -> dict:
        hashed = self.capability(capability)
        record = self.lookup(locator)
        if not secrets.compare_digest(record["capability"], hashed):
            raise ValueError("Request unavailable")
        return record

    def create(self, capability: str) -> dict:
        hashed = self.capability(capability)
        now = time.time()
        self.records = {key: record for key, record in self.records.items()
                        if record["expiresAt"] > now}
        for record in self.records.values():
            if secrets.compare_digest(record["capability"], hashed):
                return self.view(record)
        self.creation.take()
        if len(self.records) >= MAX_REQUESTS:
            raise RequestLimit("Request capacity reached")
        for _ in range(16):
            locator = "RP-" + secrets.token_hex(5).upper()
            if locator not in self.records:
                break
        else:
            raise RequestLimit("Request locator unavailable")
        record = {"request": locator, "capability": hashed, "state": "pending",
                  "expiresAt": now + REQUEST_SECONDS, "checkedAt": None}
        self.records[locator] = record
        return self.view(record)

    def status(self, locator: str, capability: str) -> dict:
        record = self.owned(locator, capability)
        now = time.monotonic()
        if record["checkedAt"] is not None and now - record["checkedAt"] < 1:
            raise RequestLimit("Check approval at most once per second")
        record["checkedAt"] = now
        return self.view(record)

    def available(self, participant: str, current: dict) -> None:
        if participant not in self.store.pages:
            raise ValueError("Approval requires a configured page")
        # Missing/throwing/invalid callback must fail closed, not invent presence.
        if self.presence is None:
            raise ValueError("Router presence unavailable")
        try:
            occupied = self.presence(participant)
        except Exception:
            raise ValueError("Router presence unavailable") from None
        if type(occupied) is not bool:
            raise ValueError("Router presence unavailable")
        now = time.time()
        if (occupied or any(session["participant"] == participant and
                            session["expiresAt"] > now
                            for session in self.store.state["sessions"].values())
                or any(record is not current and record["state"] == "approved"
                       and record["expiresAt"] > now
                       and record["participant"] == participant
                       for record in self.records.values())):
            raise ValueError("Page identity is already occupied or reserved")

    def approve(self, locator: str, participant: str) -> dict:
        record = self.lookup(locator)
        if (record["state"] not in ("pending", "approved") or
                (record["state"] == "approved" and record["participant"] != participant)):
            raise ValueError("Request cannot be approved")
        self.available(participant, record)
        record.update(state="approved", participant=participant)
        return self.view(record)

    def cancel(self, locator: str, capability: str | None = None) -> dict:
        record = self.lookup(locator) if capability is None else self.owned(locator, capability)
        if record["state"] not in ("pending", "approved", "cancelled"):
            raise ValueError("Request cannot be cancelled")
        record["state"] = "cancelled"
        return self.view(record)

    def redeem(self, locator: str, capability: str) -> tuple[str, dict]:
        record = self.owned(locator, capability)
        if record["state"] != "approved":
            raise ValueError("Request is not approved or was already consumed")
        self.available(record["participant"], record)
        token, session = self.store.issue_session(record["participant"])
        # Persistence succeeded. Never reissue token, even if HTTP delivery fails.
        record["state"] = "redeemed"
        return token, session
