"""Explicit single-pair v1 compatibility; new routing does not depend on it."""

from __future__ import annotations

import secrets
import uuid

from .protocol import (
    MAX_FRAME_BYTES,
    Connection,
    JsonObject,
    json_bytes,
    require_string,
    utc_now,
    validate_delivery,
    validate_message,
    validate_payload,
    validate_reply,
)


class Broker:
    """Own one control session and one paired browser connection."""

    def __init__(self, *, public_url: str, session_id: str):
        self.public_url = public_url.rstrip("/")
        self.session_id = require_string(session_id, "session id")
        self.control_token = secrets.token_urlsafe(32)
        self.pair_token = secrets.token_urlsafe(32)
        self.channel_id = str(uuid.uuid4())
        self.control: Connection | None = None
        self.control_session_id: str | None = None
        self.browser: Connection | None = None
        self.pending_id: str | None = None
        self.context_ids: set[str] = set()
        self.agent_busy = False
        self.delivery_options = False
        self.seen: dict[str, str] = {}
        self.closed = False

    async def emit(self, target: Connection | None, value: JsonObject) -> bool:
        if target is None:
            return False
        try:
            if len(json_bytes(value)) > MAX_FRAME_BYTES:
                return False
            await target.send(value)
            return True
        except Exception:  # transport failures are reported as uncertain delivery
            return False

    def remember(self, identity: str, status: str) -> None:
        self.seen[identity] = status
        while len(self.seen) > 128:
            self.seen.pop(next(iter(self.seen)))

    def endpoint(self, *, port: int, pid: int) -> JsonObject:
        return {
            "wsUrl": f"ws://127.0.0.1:{port}/ws",
            "publicUrl": self.public_url,
            "controlToken": self.control_token,
            "sessionId": self.session_id,
            "pid": pid,
            "startedAt": utc_now(),
        }

    async def authenticate(self, connection: Connection, hello: JsonObject) -> str:
        if hello.get("type") != "hello":
            raise ValueError("First WebSocket message must authenticate a role")
        role = hello.get("role")
        if role == "control":
            if hello.get("token") != self.control_token or self.control is not None:
                raise ValueError("Unauthorized or competing Pi session")
            control_session_id = hello.get("sessionId")
            if not isinstance(control_session_id, str) or not control_session_id:
                raise ValueError("A Pi session id is required")
            self.control_session_id = control_session_id
            self.delivery_options = (
                type(hello.get("deliveryOptions")) is int and hello["deliveryOptions"] == 1
            )
            self.control = connection
            await self.emit(connection, {"type": "hello_ack", "role": "control"})
            return "control"
        if role == "browser":
            if hello.get("token") != self.pair_token:
                raise ValueError("Unauthorized browser pairing token")
            if self.control is None:
                raise ValueError("The Pi session is not connected yet")
            if self.browser is not None:
                raise ValueError("A browser is already connected")
            if hello.get("sessionId") != self.session_id:
                raise ValueError("Wrong browser session route")
            self.browser = connection
            await self.emit(
                connection,
                {
                    "type": "hello_ack",
                    "role": "browser",
                    "channelId": self.channel_id,
                    "agentBusy": self.agent_busy,
                    "pendingId": self.pending_id,
                    "deliveryOptions": 1 if self.delivery_options else 0,
                },
            )
            return "browser"
        raise ValueError("Unknown WebSocket role")

    async def control_packet(self, connection: Connection, packet: JsonObject) -> bool:
        if packet.get("type") != "control" or not isinstance(packet.get("requestId"), str):
            raise ValueError("Invalid control request")
        request_id = packet["requestId"]
        action = packet.get("action")
        result: JsonObject = {"type": "result", "requestId": request_id}
        if action == "open":
            result.update(
                status="open",
                channelId=self.channel_id,
                pairingUrl=f"/sessions/{self.session_id}/#pair={self.pair_token}",
            )
        elif action == "status":
            result.update(
                status="open",
                browserConnected=self.browser is not None,
                pendingId=self.pending_id,
                agentBusy=self.agent_busy,
            )
        elif action == "state":
            payload = packet.get("payload")
            if not isinstance(payload, dict) or not isinstance(payload.get("busy"), bool):
                raise ValueError("state action requires a boolean payload.busy flag")
            self.agent_busy = payload["busy"]
            await self.emit(self.browser, {"type": "agent_state", "busy": self.agent_busy})
            result["busy"] = self.agent_busy
        elif action == "context_result":
            identity = require_string(packet.get("id"), "context id")
            if identity not in self.context_ids:
                raise ValueError("Unknown context request")
            status = packet.get("status")
            if status not in {
                "buffered",
                "queued",
                "attached",
                "replaced",
                "cleared",
                "rejected",
                "inspected",
            }:
                raise ValueError("Invalid context status")
            details = packet.get("details", {})
            validate_payload(details)
            delivered = await self.emit(
                self.browser,
                {
                    "type": "context_result",
                    "id": identity,
                    "status": status,
                    "details": details,
                },
            )
            if status not in {"buffered", "queued"}:
                self.context_ids.discard(identity)
                self.remember(identity, status)
            result.update(status="accepted", browserDelivered=delivered)
        elif action == "admit":
            identity = require_string(packet.get("id"), "message id")
            if identity != self.pending_id:
                raise ValueError("No matching pending browser message")
            delivered = await self.emit(self.browser, {"type": "admitted", "id": identity})
            result.update(status="accepted", id=identity, browserDelivered=delivered)
        elif action == "send":
            envelope = packet.get("envelope")
            if self.pending_id is None:
                raise ValueError("No matching pending browser message")
            reply = validate_reply(envelope, self.pending_id)
            identity = self.pending_id
            delivered = await self.emit(self.browser, {"type": "reply", "envelope": reply})
            self.remember(identity, "answered")
            self.pending_id = None
            result.update(status="accepted", id=identity, browserDelivered=delivered)
        elif action == "reject":
            identity = require_string(packet.get("correlationId"), "correlation id")
            if identity != self.pending_id:
                raise ValueError("No matching pending browser message")
            message = packet.get("message", "Message was rejected by Pi")
            if not isinstance(message, str) or len(message) > 1_000:
                raise ValueError("rejection message is invalid")
            delivered = await self.emit(
                self.browser,
                {
                    "type": "rejected",
                    "id": identity,
                    "error": {"code": packet.get("code", "rejected"), "message": message},
                },
            )
            self.remember(identity, "rejected")
            self.pending_id = None
            result.update(status="accepted", id=identity, browserDelivered=delivered)
        elif action == "close":
            await self.emit(
                self.browser,
                {
                    "type": "disconnected",
                    "pendingId": self.pending_id,
                    "message": "Agent closed the bridge.",
                },
            )
            await self.emit(connection, result | {"status": "closed"})
            self.closed = True
            return False
        else:
            raise ValueError(f"Unknown control action: {action}")
        await self.emit(connection, result)
        return True

    def health(self) -> JsonObject:
        return {"status": "running", "agentConnected": self.control is not None}

    async def packet(self, connection: Connection, packet: JsonObject) -> bool:
        if connection is self.browser:
            await self.browser_packet(connection, packet)
            return True
        if connection is self.control:
            return await self.control_packet(connection, packet)
        raise ValueError("Connection is not authenticated")

    async def browser_packet(self, connection: Connection, packet: JsonObject) -> None:
        context_control = packet.get("kind") == "context_control"
        if (context_control or "delivery" in packet) and not self.delivery_options:
            raise ValueError("Connected Pi extension does not support delivery options")
        if context_control:
            identity = require_string(packet.get("id"), "context request id")
            if packet.get("v") != 1 or isinstance(packet.get("v"), bool):
                raise ValueError("Expected version 1 context control")
            if set(packet) - {"v", "id", "kind", "action", "slot"}:
                raise ValueError("Unexpected context control fields")
            if packet.get("action") not in {"inspect", "clear"}:
                raise ValueError("Invalid context control action")
            if "slot" in packet:
                require_string(packet["slot"], "context slot")
            payload = None
            delivery = {"role": "context"}
        else:
            identity, payload = validate_message(packet)
            delivery = validate_delivery(packet["delivery"]) if "delivery" in packet else {}
        if identity in self.seen or identity in self.context_ids:
            await self.emit(
                connection,
                {"type": "duplicate", "id": identity, "status": self.seen.get(identity, "pending")},
            )
            return
        if delivery.get("role") == "context":
            if self.control is None or len(self.context_ids) >= 32:
                await self.emit(
                    connection,
                    {
                        "type": "context_result",
                        "id": identity,
                        "status": "rejected",
                        "details": {"reason": "Control unavailable or context capacity reached"},
                    },
                )
                self.remember(identity, "rejected")
                return
            self.context_ids.add(identity)
            self.remember(identity, "pending")
            envelope = (
                packet
                if context_control
                else {
                    "v": 1,
                    "id": identity,
                    "kind": "message",
                    "payload": payload,
                    "delivery": delivery,
                }
            )
            if not await self.emit(self.control, {"type": "event", "envelope": envelope}):
                await self.emit(
                    connection,
                    {
                        "type": "context_result",
                        "id": identity,
                        "status": "uncertain",
                        "details": {
                            "reason": "Control delivery uncertain; do not retry automatically"
                        },
                    },
                )
            return
        busy_blocked = self.agent_busy and delivery.get("deliverAs", "immediate") == "immediate"
        if self.pending_id is not None or busy_blocked or self.control is None:
            await self.emit(
                connection,
                {
                    "type": "rejected",
                    "id": identity,
                    "error": {
                        "code": "busy",
                        "message": "Agent unavailable or a reply is still pending.",
                    },
                },
            )
            self.remember(identity, "rejected")
            return
        self.pending_id = identity
        self.remember(identity, "pending")
        event = {
            "type": "event",
            "envelope": {"v": 1, "id": identity, "kind": "message", "payload": payload},
        }
        if delivery:
            event["envelope"]["delivery"] = delivery
        if await self.emit(self.control, event):
            await self.emit(connection, {"type": "receipt", "id": identity, "status": "accepted"})
        else:
            await self.emit(
                connection,
                {
                    "type": "disconnected",
                    "pendingId": identity,
                    "message": (
                        "Delivery is uncertain; this message will not be resent automatically."
                    ),
                },
            )

    async def disconnected(self, connection: Connection) -> None:
        if self.browser is connection:
            self.browser = None
        if self.control is connection:
            self.control = None
            self.control_session_id = None
            self.delivery_options = False
            disconnected_ids = tuple(self.context_ids)
            self.context_ids.clear()
            for identity in disconnected_ids:
                await self.emit(
                    self.browser,
                    {
                        "type": "context_result",
                        "id": identity,
                        "status": "uncertain",
                        "details": {"reason": "Pi disconnected; buffer state lost or unknown"},
                    },
                )
            await self.emit(
                self.browser,
                {
                    "type": "disconnected",
                    "pendingId": self.pending_id,
                    "message": (
                        "Pi disconnected; an unresolved message will not be resent automatically."
                    ),
                },
            )
