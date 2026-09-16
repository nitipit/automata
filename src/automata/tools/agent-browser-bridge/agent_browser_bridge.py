#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["cyclopts>=3.0.0", "uvicorn>=0.30.0", "websockets>=12.0"]
# ///
"""Loopback WebSocket bridge between a browser page and one Pi session.

The server is deliberately opt-in: importing this module or running ``setup`` does
not start a listener.  ``serve`` publishes a short-lived private endpoint record and
mounts only the selected library and session roots.
"""

from __future__ import annotations

import asyncio
import json
import math
import mimetypes
import os
import re
import secrets
import signal
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import unquote

import uvicorn
from cyclopts import App, Parameter

MAX_FRAME_BYTES = 64 * 1024
MAX_PAYLOAD_BYTES = 32 * 1024
MAX_JSON_DEPTH = 32
MAX_ID_LENGTH = 128
MAX_SAFE_INTEGER = 2**53 - 1
SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

DEFAULT_STATE_ROOT = Path(
    os.environ.get("AUTOMATA_AGENT_BROWSER_BRIDGE_STATE", ".agents/var/tools/agent-browser-bridge")
).expanduser()
DEFAULT_RUNTIME_ROOT = Path(
    os.environ.get(
        "AUTOMATA_AGENT_BROWSER_BRIDGE_RUNTIME", ".agents/var/skills/automata-adaptive-ui"
    )
).expanduser()

JsonObject = dict[str, Any]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode(
        "utf-8", errors="backslashreplace"
    )


def valid_json_value(value: Any, depth: int = 0) -> bool:
    """Check the JSON subset shared by Python and JavaScript without projection."""
    if depth > MAX_JSON_DEPTH:
        return False
    if value is None or isinstance(value, (str, bool)):
        return True
    if isinstance(value, int) and not isinstance(value, bool):
        return abs(value) <= MAX_SAFE_INTEGER
    if isinstance(value, float):
        return math.isfinite(value) and (not value.is_integer() or abs(value) <= MAX_SAFE_INTEGER)
    if isinstance(value, list):
        return all(valid_json_value(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and valid_json_value(item, depth + 1)
            for key, item in value.items()
        )
    return False


def validate_payload(value: Any) -> bytes:
    if not valid_json_value(value):
        raise ValueError("payload must contain only finite, interoperable JSON values")
    try:
        encoded = json_bytes(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("payload is not serializable JSON") from error
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise ValueError("payload exceeds 32 KiB")
    return encoded


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-JSON number {value} is not supported")


def strict_object_pairs(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def parse_frame(raw: Any) -> JsonObject:
    if not isinstance(raw, str):
        raise ValueError("WebSocket messages must be text")
    if len(raw.encode("utf-8")) > MAX_FRAME_BYTES:
        raise ValueError("WebSocket frame exceeds 64 KiB")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=strict_object_pairs,
            parse_constant=reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError, RecursionError) as error:
        raise ValueError("WebSocket message is not valid JSON") from error
    if not isinstance(value, dict):
        raise ValueError("WebSocket message must be an object")
    # Allow routing wrappers above the independently bounded component payload.
    if not valid_json_value(value, depth=-4):
        raise ValueError("WebSocket frame contains invalid or excessively nested JSON")
    return value


def require_string(value: Any, name: str, *, max_length: int = MAX_ID_LENGTH) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise ValueError(f"{name} must be a bounded non-empty string")
    return value


def validate_message(value: JsonObject) -> tuple[str, Any]:
    if isinstance(value.get("v"), bool) or value.get("v") != 1 or value.get("kind") != "message":
        raise ValueError("Expected a version 1 message envelope")
    identity = require_string(value.get("id"), "message id")
    if "payload" not in value:
        raise ValueError("message envelope requires payload")
    payload = value["payload"]
    validate_payload(payload)
    return identity, payload


def validate_delivery(value: Any) -> JsonObject:
    """Delivery policy is transport metadata, never inferred from component payloads."""
    if not isinstance(value, dict) or set(value) - {"role", "deliverAs", "slot", "triggerTurn"}:
        raise ValueError("Invalid delivery options")
    role, mode = value.get("role", "user"), value.get("deliverAs", "immediate")
    if role not in ("user", "context") or mode not in (
        "immediate",
        "steer",
        "followUp",
        "nextTurn",
    ):
        raise ValueError("Invalid role or deliverAs")
    if role == "user" and (mode == "nextTurn" or "triggerTurn" in value):
        raise ValueError("User messages always trigger a turn and cannot use nextTurn")
    if "triggerTurn" in value and not isinstance(value["triggerTurn"], bool):
        raise ValueError("triggerTurn must be boolean")
    if mode == "nextTurn" and value.get("triggerTurn"):
        raise ValueError("nextTurn cannot trigger a turn")
    if "slot" in value:
        require_string(value["slot"], "context slot")
        if role != "context" or mode != "nextTurn":
            raise ValueError("Slots require context nextTurn delivery")
    return {"role": role, "deliverAs": mode, **value}


def validate_reply(value: Any, pending_id: str) -> Any:
    if not isinstance(value, dict):
        raise ValueError("reply envelope must be an object")
    if isinstance(value.get("v"), bool) or value.get("v") != 1 or value.get("kind") != "reply":
        raise ValueError("Expected a version 1 reply envelope")
    reply_id = require_string(value.get("id"), "reply id")
    correlation_id = value.get("correlationId")
    if correlation_id != pending_id:
        raise ValueError("Reply does not correlate to the pending browser message")
    if "payload" not in value:
        raise ValueError("reply envelope requires payload")
    validate_payload(value["payload"])
    # Return the original object: payload keys, including constructor and __proto__,
    # are component data and are never merged into broker configuration.
    value["id"] = reply_id
    return value


@dataclass
class Connection:
    send: Any


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


class BridgeApp:
    def __init__(
        self,
        broker: Broker,
        library_root: Path,
        sessions_root: Path,
        private_paths: tuple[Path, ...] = (),
    ):
        self.broker = broker
        self.library_root = library_root.resolve()
        self.sessions_root = sessions_root.resolve()
        self.private_paths = {path.resolve() for path in private_paths}
        self.asset_root = Path(__file__).resolve().parent / "browser"

    async def __call__(self, scope: JsonObject, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            await self.http(scope, receive, send)
        elif scope["type"] == "websocket":
            await self.websocket(scope, receive, send)
        else:
            raise RuntimeError(f"Unsupported ASGI scope: {scope['type']}")

    async def http(self, scope: JsonObject, _receive: Any, send: Any) -> None:
        method = scope.get("method", "GET")
        path = unquote(scope.get("path", "/"))
        if method not in {"GET", "HEAD"}:
            await self.respond(
                send,
                405,
                b"Method not allowed\n",
                "text/plain; charset=utf-8",
                {"allow": "GET, HEAD"},
            )
            return
        if path == "/health":
            body = (
                json_bytes({"status": "running", "agentConnected": self.broker.control is not None})
                + b"\n"
            )
            await self.respond(
                send, 200, body, "application/json; charset=utf-8", head=method == "HEAD"
            )
            return
        file_path = self.public_path(path)
        if file_path is None or not file_path.is_file():
            await self.respond(
                send, 404, b"Not found\n", "text/plain; charset=utf-8", head=method == "HEAD"
            )
            return
        body = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        await self.respond(send, 200, body, content_type, head=method == "HEAD")

    def public_path(self, path: str) -> Path | None:
        if path.startswith("/assets/"):
            return self.public_file(self.safe_child(self.asset_root, path.removeprefix("/assets/")))
        if path == "/lib" or path.startswith("/lib/"):
            relative = path.removeprefix("/lib/")
            return self.public_file(self.safe_child(self.library_root, relative))
        match = re.fullmatch(r"/sessions/([A-Za-z0-9_-]{1,128})(?:/(.*))?", path)
        if match is None:
            return None
        session_id, relative = match.group(1), match.group(2) or ""
        root = (self.sessions_root / session_id).resolve()
        try:
            root.relative_to(self.sessions_root)
        except ValueError:
            return None
        if not relative:
            relative = "index.html"
        return self.public_file(self.safe_child(root, relative))

    def public_file(self, candidate: Path | None) -> Path | None:
        if candidate is None or candidate in self.private_paths:
            return None
        return candidate

    @staticmethod
    def safe_child(root: Path, relative: str) -> Path | None:
        if not relative or any(
            part in {"", ".", "..", "endpoint.json"} for part in relative.split("/")
        ):
            return None
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            return None
        if candidate.name == "endpoint.json":
            return None
        return candidate

    @staticmethod
    async def respond(
        send: Any,
        status: int,
        body: bytes,
        content_type: str,
        headers: dict[str, str] | None = None,
        *,
        head: bool = False,
    ) -> None:
        response_headers = [
            (b"content-type", content_type.encode()),
            (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"),
        ]
        for key, value in (headers or {}).items():
            response_headers.append((key.lower().encode(), value.encode()))
        await send({"type": "http.response.start", "status": status, "headers": response_headers})
        await send({"type": "http.response.body", "body": b"" if head else body})

    async def websocket(self, scope: JsonObject, receive: Any, send: Any) -> None:
        origin = next(
            (value.decode() for key, value in scope.get("headers", []) if key == b"origin"), None
        )
        if origin and origin != self.broker.public_url:
            await send({"type": "websocket.close", "code": 1008, "reason": "Forbidden origin"})
            return
        role: str | None = None
        connection: Connection | None = None
        try:
            connected = await receive()
            if connected.get("type") != "websocket.connect":
                raise ValueError("Expected a WebSocket connection")
            await send({"type": "websocket.accept"})
            connection = Connection(
                lambda value: send(
                    {"type": "websocket.send", "text": json_bytes(value).decode("utf-8")}
                )
            )
            first = await asyncio.wait_for(receive(), timeout=5)
            if first.get("type") != "websocket.receive" or first.get("text") is None:
                raise ValueError("Expected an authentication hello")
            role = await self.broker.authenticate(connection, parse_frame(first["text"]))
            while True:
                message = await receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("type") != "websocket.receive" or message.get("text") is None:
                    raise ValueError("WebSocket messages must be text")
                packet = parse_frame(message["text"])
                if role == "browser":
                    await self.broker.browser_packet(connection, packet)
                elif not await self.broker.control_packet(connection, packet):
                    break
        except Exception as error:  # close after returning a bounded protocol error
            await self.broker.emit(
                connection, {"type": "error", "code": "protocol", "message": str(error)}
            )
            await send({"type": "websocket.close", "code": 1008, "reason": str(error)[:120]})
        finally:
            if connection is not None:
                await self.broker.disconnected(connection)


class EndpointOwner:
    def __init__(self, path: Path, endpoint: JsonObject):
        self.path = path
        self.endpoint = endpoint
        self.owned = False

    def create(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.path.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(self.endpoint, indent=2) + "\n")
        except FileExistsError as error:
            raise RuntimeError(
                f"Refusing to replace an existing endpoint record: {self.path}"
            ) from error
        self.path.chmod(0o600)
        self.owned = True

    def cleanup(self) -> None:
        if not self.owned or not self.path.exists():
            return
        try:
            current = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if current.get("controlToken") == self.endpoint.get("controlToken") and current.get(
            "pid"
        ) == self.endpoint.get("pid"):
            self.path.unlink(missing_ok=True)


class GracefulServer(uvicorn.Server):
    """Allow endpoint publication after bind and cleanup on SIGINT/SIGTERM."""

    def __init__(self, config: uvicorn.Config, endpoint_owner: EndpointOwner):
        super().__init__(config)
        self.endpoint_owner = endpoint_owner

    def install_signal_handlers(self) -> None:
        # The command owns signal handlers so the private record is cleaned up.
        return

    async def startup(self, sockets: Any = None) -> None:
        await super().startup(sockets=sockets)
        self.endpoint_owner.create()


def runtime_paths(runtime_root: Path) -> tuple[Path, Path]:
    return runtime_root / "lib", runtime_root / "sessions"


def setup(
    *,
    runtime_root: Path = DEFAULT_RUNTIME_ROOT,
    endpoint_file: Path = DEFAULT_STATE_ROOT / "endpoint.json",
) -> None:
    library, sessions = runtime_paths(runtime_root)
    library.mkdir(parents=True, exist_ok=True)
    sessions.mkdir(parents=True, exist_ok=True)
    endpoint_file.parent.mkdir(parents=True, exist_ok=True)
    bundle = library / "adaptive-ui.js"
    state = (
        "present"
        if bundle.is_file()
        else "missing (build/install the Adaptive UI library before serving)"
    )
    print(f"runtime library: {library} ({state})")
    print(f"runtime sessions: {sessions}")
    print(f"private endpoint: {endpoint_file}")
    print("setup complete; no server or Pi process was started")


def status(*, endpoint_file: Path = DEFAULT_STATE_ROOT / "endpoint.json") -> None:
    if not endpoint_file.is_file():
        print(json.dumps({"status": "stopped", "endpoint": str(endpoint_file)}))
        return
    try:
        endpoint = json.loads(endpoint_file.read_text(encoding="utf-8"))
        with urllib.request.urlopen(f"{endpoint['publicUrl']}/health", timeout=2) as response:
            health = json.loads(response.read())
    except (OSError, KeyError, TypeError, json.JSONDecodeError, urllib.error.URLError) as error:
        print(
            json.dumps(
                {"status": "unreachable", "endpoint": str(endpoint_file), "error": str(error)}
            )
        )
        return
    print(
        json.dumps({"status": "running", "endpoint": str(endpoint_file), **health}, sort_keys=True)
    )


def serve(
    *,
    port: Annotated[int, Parameter(help="Loopback TCP port.")] = 8787,
    runtime_root: Annotated[
        Path, Parameter(help="Root containing lib/ and sessions/<session-id>/.")
    ] = DEFAULT_RUNTIME_ROOT,
    session_id: Annotated[
        str, Parameter(help="Static session directory name and pairing route.")
    ] = "default",
    endpoint_file: Annotated[
        Path, Parameter(help="Private endpoint record path.")
    ] = DEFAULT_STATE_ROOT / "endpoint.json",
) -> None:
    if not 1 <= port <= 65_535:
        raise ValueError("--port must be between 1 and 65535")
    if not SESSION_RE.fullmatch(session_id):
        raise ValueError("--session-id must contain only letters, numbers, '_' or '-'")
    library, sessions = runtime_paths(runtime_root)
    library = library.resolve()
    sessions = sessions.resolve()
    if not library.is_dir() or not sessions.is_dir():
        raise ValueError(f"runtime is not initialized; run setup first for {runtime_root}")
    public_url = f"http://127.0.0.1:{port}"
    broker = Broker(public_url=public_url, session_id=session_id)
    endpoint_owner = EndpointOwner(endpoint_file, broker.endpoint(port=port, pid=os.getpid()))
    server = GracefulServer(
        uvicorn.Config(
            BridgeApp(broker, library, sessions, (endpoint_file.resolve(),)),
            host="127.0.0.1",
            port=port,
            log_level="warning",
        ),
        endpoint_owner,
    )
    previous_handlers = {
        signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)
    }

    def stop(_signum: int, _frame: Any) -> None:
        server.should_exit = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        server.run()
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        endpoint_owner.cleanup()


app = App(name="agent-browser-bridge", help="Serve and inspect the reusable browser-to-Pi bridge.")
app.command(setup)
app.command(status)
app.command(serve)


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except (RuntimeError, ValueError) as error:
        print(f"error: {error}")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
