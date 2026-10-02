"""Strict request-pairing HTTP packets, sharing SessionAuth's origin/body boundary."""
from __future__ import annotations

from typing import Any

REQUEST_PATHS = frozenset({"/session/request", "/session/request-status",
                           "/session/request-cancel", "/session/request-redeem"})


def request_packet(auth: Any, path: str, packet: dict, headers: dict) -> tuple[dict, str | None]:
    requests = auth.requests
    requests.operations.take()
    if path == "/session/request":
        if set(packet) != {"capability"}:
            raise ValueError("Request requires requester capability only")
        if auth.store.session(auth.token(headers)):
            raise ValueError("Forget existing pairing before requesting again")
        return requests.create(packet["capability"]), None
    if set(packet) != {"request", "capability"}:
        raise ValueError("Request requires exact locator and requester capability")
    locator, capability = packet["request"], packet["capability"]
    if path == "/session/request-status":
        return requests.status(locator, capability), None
    if path == "/session/request-cancel":
        return requests.cancel(locator, capability), None
    if path != "/session/request-redeem":
        raise ValueError("Unknown request action")
    # Any existing valid session matters, not only the newly selected page.
    # Reject before consuming/minting or emitting a replacement cookie.
    if auth.store.session(auth.token(headers)):
        raise ValueError("Forget existing pairing before claiming this request")
    token, session = requests.redeem(locator, capability)
    return {"authenticated": True, "participant": session["participant"],
            "expiresAt": session["expiresAt"]}, token
