"""Authenticated targeted routing, independent of ASGI, UI and Pi delivery policy.

A route is a bounded reply capability tied to two *connection objects*, not merely
names. Final response, cancellation or either disconnect revokes it. There is no
replay/history store. Long-lived application contexts may keep a route open until
session end; capacity is bounded rather than expiring next-prompt data by a timer.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, field
from typing import Any

from .protocol import (
    MAX_FRAME_BYTES,
    SESSION_RE,
    Connection,
    JsonObject,
    json_bytes,
    require_string,
    validate_metadata,
    validate_payload,
)

MAX_PARTICIPANTS = 128
MAX_ROUTES_PER_CONNECTION = 64
MAX_SEEN_IDS = 128


@dataclass(frozen=True)
class Grant:
    kind: str
    token: str
    allow: frozenset[str]


def validate_config(value: Any) -> dict[str, Grant]:
    if (
        not isinstance(value, dict)
        or set(value) != {"v", "participants"}
        or type(value["v"]) is not int
        or value["v"] != 1
    ):
        raise ValueError("Expected version 1 participant configuration")
    participants = value["participants"]
    if not isinstance(participants, dict) or not 1 <= len(participants) <= MAX_PARTICIPANTS:
        raise ValueError("Configure 1–128 participants")
    grants = {}
    tokens = set()
    for identity, spec in participants.items():
        if not SESSION_RE.fullmatch(identity):
            raise ValueError("Participant IDs must contain only letters, numbers, '_' or '-'")
        if not isinstance(spec, dict) or set(spec) != {"kind", "token", "allow"}:
            raise ValueError("Participant requires kind, token and allow")
        if spec["kind"] not in ("page", "agent"):
            raise ValueError("Participant kind must be page or agent")
        token = spec["token"]
        if (
            not isinstance(token, str)
            or not 32 <= len(token) <= 256
            or not token.isascii()
            or token in tokens
        ):
            raise ValueError("Each participant needs a distinct 32–256 character ASCII token")
        allowed = spec["allow"]
        if not isinstance(allowed, list) or any(
            not isinstance(item, str) or item not in participants for item in allowed
        ):
            raise ValueError("Allowed destinations must be configured participant IDs")
        tokens.add(token)
        grants[identity] = Grant(spec["kind"], token, frozenset(allowed))
    return grants


@dataclass
class Peer:
    identity: str
    grant: Grant
    connection: Connection
    session_id: str | None = None
    seen: dict[str, None] = field(default_factory=dict)

    def provenance(self) -> JsonObject:
        return {
            "id": self.identity,
            "kind": self.grant.kind,
            **({"sessionId": self.session_id} if self.session_id else {}),
        }


@dataclass
class Route:
    source: Peer
    target: Peer
    request_id: str


class Router:
    def __init__(self, grants: dict[str, Grant], *, public_url: str):
        self.grants = grants
        self.public_url = public_url.rstrip("/")
        self.peers: dict[str, Peer] = {}
        self.routes: dict[str, Route] = {}

    @staticmethod
    async def emit(connection: Connection | None, value: JsonObject) -> bool:
        if connection is None:
            return False
        try:
            if len(json_bytes(value)) > MAX_FRAME_BYTES:
                return False
            await connection.send(value)
            return True
        except Exception:
            return False  # Emission is uncertain, not proof of non-delivery.

    def peer(self, connection: Connection) -> Peer:
        for peer in self.peers.values():
            if peer.connection is connection:
                return peer
        raise ValueError("Connection is not authenticated")

    def health(self) -> JsonObject:
        return {"status": "running", "participantsConnected": len(self.peers)}

    async def authenticate(self, connection: Connection, hello: JsonObject) -> str:
        if (
            set(hello) - {"v", "type", "participant", "token", "sessionId"}
            or type(hello.get("v")) is not int
            or hello["v"] != 2
            or hello.get("type") != "hello"
        ):
            raise ValueError("Expected a version 2 participant hello")
        identity = require_string(hello.get("participant"), "participant")
        token = require_string(hello.get("token"), "token", max_length=256)
        grant = self.grants.get(identity)
        if grant is None or not secrets.compare_digest(grant.token.encode(), token.encode()):
            raise ValueError("Unauthorized participant")
        if identity in self.peers:
            raise ValueError("Participant is already connected")
        session_id = None
        if grant.kind == "agent":
            session_id = require_string(hello.get("sessionId"), "agent session id")
        elif "sessionId" in hello:
            raise ValueError("Page identity is not an agent session")
        peer = Peer(identity, grant, connection, session_id)
        self.peers[identity] = peer
        if not await self.emit(
            connection, {"v": 2, "type": "hello_ack", "participant": identity, "kind": grant.kind}
        ):
            await self.disconnected(connection)
            raise ValueError("Authentication acknowledgment delivery uncertain")
        return "peer"

    async def packet(self, connection: Connection, packet: JsonObject) -> bool:
        """Return a correlated error for validly framed requests; never redirect/retry."""
        peer = self.peer(connection)
        request_id = require_string(packet.get("requestId"), "request id")
        result: JsonObject = {"v": 2, "type": "result", "requestId": request_id}
        try:
            if type(packet.get("v")) is not int or packet["v"] != 2:
                raise ValueError("Expected version 2 request")
            if request_id in peer.seen:
                raise ValueError("duplicate")
            peer.seen[request_id] = None
            while len(peer.seen) > MAX_SEEN_IDS:
                peer.seen.pop(next(iter(peer.seen)))
            action = packet.get("type")
            if action == "route":
                result.update(await self.route(peer, packet))
            elif action == "respond":
                result.update(await self.respond(peer, packet))
            elif action == "cancel":
                self.fields(packet, {"routeId"})
                route_id = require_string(packet.get("routeId"), "route id")
                route = self.routes.get(route_id)
                if route is None or route.source is not peer:
                    raise ValueError("unknown_route")
                del self.routes[route_id]
                result["status"] = "canceled"  # Does not retract peer handling.
            elif action == "status":
                self.fields(packet, set())
                result.update(
                    status="connected",
                    participant=peer.identity,
                    destinations=[
                        {
                            "id": name,
                            "kind": self.grants[name].kind,
                            "connected": name in self.peers,
                        }
                        for name in sorted(peer.grant.allow)
                    ],
                    pending=sum(
                        route.source is peer or route.target is peer
                        for route in self.routes.values()
                    ),
                )
            else:
                raise ValueError("unknown_action")
        except ValueError as error:
            result.update(status="rejected", error=str(error))
        await self.emit(connection, result)
        return True

    @staticmethod
    def fields(packet: JsonObject, allowed: set[str]) -> None:
        if set(packet) - {"v", "type", "requestId", *allowed}:
            raise ValueError("Unexpected request fields")

    async def route(self, source: Peer, packet: JsonObject) -> JsonObject:
        self.fields(packet, {"to", "payload", "metadata", "expectReply"})
        destination = require_string(packet.get("to"), "destination")
        if destination not in source.grant.allow:
            raise ValueError("forbidden")
        target = self.peers.get(destination)
        if target is None:
            raise ValueError("offline")
        if "payload" not in packet:
            raise ValueError("payload is required; null is valid")
        validate_payload(packet["payload"])
        metadata = packet.get("metadata", {})
        validate_metadata(metadata)
        expect_reply = packet.get("expectReply", True)
        if not isinstance(expect_reply, bool):
            raise ValueError("expectReply must be boolean")
        if expect_reply:
            for peer in (source, target):
                if (
                    sum(
                        route.source is peer or route.target is peer
                        for route in self.routes.values()
                    )
                    >= MAX_ROUTES_PER_CONNECTION
                ):
                    raise ValueError("capacity")
        route_id = str(uuid.uuid4())
        # Register before await: replies may race the initial transport result.
        route = Route(source, target, packet["requestId"])
        if expect_reply:
            self.routes[route_id] = route
        event = {
            "v": 2,
            "type": "message",
            "id": route_id,
            "from": source.provenance(),
            "to": destination,
            "payload": packet["payload"],
            "metadata": metadata,
            "expectReply": expect_reply,
        }
        delivered = await self.emit(target.connection, event)
        if not delivered:
            self.routes.pop(route_id, None)
        # A disconnect during emission revokes the capability, even if send returned.
        current = (
            self.peers.get(destination) is target and self.peers.get(source.identity) is source
        )
        return {
            "status": "forwarded" if delivered and current else "uncertain",
            "routeId": route_id,
        }

    async def respond(self, target: Peer, packet: JsonObject) -> JsonObject:
        self.fields(packet, {"routeId", "payload", "metadata", "final"})
        route_id = require_string(packet.get("routeId"), "route id")
        route = self.routes.get(route_id)
        if route is None or route.target is not target:
            raise ValueError("unknown_route")
        if "payload" not in packet:
            raise ValueError("response requires payload")
        validate_payload(packet["payload"])
        metadata = packet.get("metadata", {})
        validate_metadata(metadata)
        final = packet.get("final", True)
        if not isinstance(final, bool):
            raise ValueError("final must be boolean")
        if final:
            del self.routes[route_id]  # Claim before await; no duplicate terminal response.
        delivered = await self.emit(
            route.source.connection,
            {
                "v": 2,
                "type": "response",
                "id": route_id,
                "requestId": route.request_id,
                "from": target.provenance(),
                "payload": packet["payload"],
                "metadata": metadata,
                "final": final,
            },
        )
        if not delivered:
            self.routes.pop(route_id, None)
        return {"status": "forwarded" if delivered else "uncertain"}

    async def disconnected(self, connection: Connection) -> None:
        peer = next((peer for peer in self.peers.values() if peer.connection is connection), None)
        if peer is None:
            return
        del self.peers[peer.identity]
        affected = [
            (identity, route)
            for identity, route in self.routes.items()
            if route.source is peer or route.target is peer
        ]
        # Invalidate all capabilities before notification awaits allow reauthentication.
        for identity, _ in affected:
            del self.routes[identity]
        for identity, route in affected:
            other = route.target if route.source is peer else route.source
            if self.peers.get(other.identity) is other:
                await self.emit(
                    other.connection,
                    {
                        "v": 2,
                        "type": "route_closed",
                        "id": identity,
                        **({"requestId": route.request_id} if other is route.source else {}),
                        "reason": "peer_disconnected",
                        "uncertain": True,
                    },
                )
