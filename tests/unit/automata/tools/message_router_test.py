"""Routing authority and lifecycle checks without a WebSocket or Pi runtime."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[4] / "src/automata/tools/message-router"))
from automata_router.protocol import Connection  # noqa: E402
from automata_router.router import Router, validate_config  # noqa: E402


def config():
    return {
        "v": 1,
        "participants": {
            "page": {"kind": "page", "token": "p" * 32, "allow": ["other", "agent"]},
            "other": {"kind": "page", "token": "o" * 32, "allow": []},
            "agent": {"kind": "agent", "token": "a" * 32, "allow": ["page"]},
            "isolated": {"kind": "agent", "token": "i" * 32, "allow": []},
        },
    }


class Harness:
    def __init__(self):
        self.config = config()
        self.router = Router(validate_config(self.config), public_url="http://127.0.0.1:8787")
        self.messages = {}
        self.serial = 0

    async def connect(self, name):
        messages = []

        async def send(packet):
            messages.append(packet)

        connection = Connection(send)
        self.messages[id(connection)] = messages
        spec = self.config["participants"][name]
        await self.router.authenticate(
            connection,
            {
                "v": 2,
                "type": "hello",
                "participant": name,
                "token": spec["token"],
                **({"sessionId": "pi-session"} if spec["kind"] == "agent" else {}),
            },
        )
        return connection

    def received(self, connection):
        return self.messages[id(connection)]

    async def request(self, connection, action="route", **fields):
        self.serial += 1
        await self.router.packet(
            connection, {"v": 2, "type": action, "requestId": f"q{self.serial}", **fields}
        )
        return self.received(connection)[-1]


def test_direct_routes_and_connection_bound_replies():
    async def check():
        h = Harness()
        a, b, agent = await h.connect("page"), await h.connect("other"), await h.connect("agent")
        for payload in (None, False, 0, "", [], {"__proto__": {"constructor": "data"}}):
            result = await h.request(a, to="other", payload=payload)
            assert result["status"] == "forwarded"
            message = h.received(b)[-1]
            assert message["from"] == {"id": "page", "kind": "page"}
            assert message["payload"] == payload
            # No reverse grant needed for the exact request's reply capability.
            reply = await h.request(b, "respond", routeId=message["id"], payload=payload)
            assert reply["status"] == "forwarded"
            assert h.received(a)[-1]["payload"] == payload
            assert not h.router.routes
        assert len(h.received(agent)) == 1  # No page-to-page traffic reaches an agent.
        result = await h.request(agent, to="page", payload=[1, 2])
        assert h.received(a)[-1]["from"] == {
            "id": "agent",
            "kind": "agent",
            "sessionId": "pi-session",
        }
        stale_id = result["routeId"]
        await h.router.disconnected(agent)
        replacement = await h.connect("agent")
        result = await h.request(a, "respond", routeId=stale_id, payload=None)
        assert result["status"] == "rejected"
        assert len(h.received(replacement)) == 1
        # Disconnecting the old socket twice cannot remove its replacement.
        await h.router.disconnected(agent)
        assert h.router.peer(replacement).identity == "agent"

    asyncio.run(check())


def test_authorization_spoofing_duplicate_identity_and_offline():
    async def check():
        h = Harness()
        page, other, isolated = (
            await h.connect("page"),
            await h.connect("other"),
            await h.connect("isolated"),
        )
        with pytest.raises(ValueError, match="already connected"):
            await h.connect("page")
        for extra in ({"from": "agent"}, {"sessionId": "another"}, {"role": "control"}):
            assert (await h.request(page, to="other", payload=None, **extra))[
                "status"
            ] == "rejected"
        assert (await h.request(page, to="isolated", payload=None))["error"] == "forbidden"
        assert (await h.request(page, to="agent", payload=None))["error"] == "offline"
        assert (await h.request(other, to="page", payload=None))["error"] == "forbidden"
        assert (await h.request(isolated, "respond", routeId="invented", payload=None))[
            "error"
        ] == "unknown_route"
        assert len(h.received(other)) == 2  # hello and its own rejected request only
        assert (await h.request(page, "status"))["destinations"] == [
            {"id": "agent", "kind": "agent", "connected": False},
            {"id": "other", "kind": "page", "connected": True},
        ]

    asyncio.run(check())


def test_target_replacement_cannot_reply_to_old_request():
    async def check():
        h = Harness()
        a, b = await h.connect("page"), await h.connect("other")
        result = await h.request(a, to="other", payload="question")
        await h.router.disconnected(b)
        assert h.received(a)[-1]["type"] == "route_closed"
        new_b = await h.connect("other")
        assert (await h.request(new_b, "respond", routeId=result["routeId"], payload=None))[
            "error"
        ] == "unknown_route"
        assert not h.router.routes

    asyncio.run(check())


def test_streaming_receipts_final_cancel_and_capacity():
    async def check():
        h = Harness()
        a, b = await h.connect("page"), await h.connect("other")
        first = await h.request(a, to="other", payload=None)
        route_id = first["routeId"]
        assert (
            await h.request(
                b,
                "respond",
                routeId=route_id,
                payload=None,
                final=False,
                metadata={"arbitraryApplicationReceipt": "queued"},
            )
        )["status"] == "forwarded"
        assert len(h.router.routes) == 1
        assert (await h.request(b, "cancel", routeId=route_id))["error"] == "unknown_route"
        assert (await h.request(a, "cancel", routeId=route_id))["status"] == "canceled"
        assert (await h.request(b, "respond", routeId=route_id, payload=None))[
            "error"
        ] == "unknown_route"
        for _ in range(64):
            assert (await h.request(a, to="other", payload=None))["status"] == "forwarded"
        assert (await h.request(a, to="other", payload=None))["error"] == "capacity"
        # Notifications do not allocate response capabilities.
        assert (await h.request(a, to="other", payload=None, expectReply=False))[
            "status"
        ] == "forwarded"
        assert len(h.router.routes) == 64
        await h.router.disconnected(b)
        assert not h.router.routes

    asyncio.run(check())


def test_duplicate_and_failed_emission_are_never_retried():
    async def check():
        h = Harness()
        a, b = await h.connect("page"), await h.connect("other")
        packet = {"v": 2, "type": "route", "requestId": "same", "to": "other", "payload": None}
        await h.router.packet(a, packet)
        await h.router.packet(a, packet)
        assert h.received(a)[-1]["error"] == "duplicate"
        assert len(h.received(b)) == 2
        calls = []

        async def broken(value):
            calls.append(value)
            raise OSError("write may have reached peer")

        b.send = broken
        assert (await h.request(a, to="other", payload=None))["status"] == "uncertain"
        assert len(calls) == 1
        assert len(h.router.routes) == 1  # only the original successful request remains

    asyncio.run(check())


def test_disconnect_notice_does_not_confuse_another_senders_request_id():
    async def check():
        h = Harness()
        grants = config()
        grants["participants"]["agent"]["allow"].append("other")
        h.router = Router(validate_config(grants), public_url="http://127.0.0.1:8787")
        a, b, agent = await h.connect("page"), await h.connect("other"), await h.connect("agent")
        for source, target in ((a, "agent"), (agent, "other")):
            await h.router.packet(
                source,
                {"v": 2, "type": "route", "requestId": "same-id", "to": target, "payload": None},
            )
        surviving_route = h.received(b)[-1]["id"]
        await h.router.disconnected(a)
        notice = h.received(agent)[-1]
        assert notice["type"] == "route_closed"
        assert "requestId" not in notice  # This was an inbound capability, not agent's request.
        assert list(h.router.routes) == [surviving_route]
        await h.request(b, "respond", routeId=surviving_route, payload=False)
        assert h.received(agent)[-1]["requestId"] == "same-id"
        assert h.received(agent)[-1]["payload"] is False

    asyncio.run(check())


def test_disconnect_during_forwarding_cannot_rebind_to_replacement():
    async def check():
        h = Harness()
        a, b = await h.connect("page"), await h.connect("other")
        started, release = asyncio.Event(), asyncio.Event()
        original_send = b.send

        async def paused_send(value):
            started.set()
            await release.wait()
            await original_send(value)

        b.send = paused_send
        forward = asyncio.create_task(h.request(a, to="other", payload="once"))
        await started.wait()
        # Restore transport for the disconnect notification while the prior send waits.
        b.send = original_send
        await h.router.disconnected(a)
        replacement = await h.connect("page")
        release.set()
        assert (await forward)["status"] == "uncertain"
        assert not h.router.routes
        assert len(h.received(replacement)) == 1

    asyncio.run(check())


def test_invalid_payload_and_metadata_do_not_allocate_routes():
    async def check():
        h = Harness()
        a = await h.connect("page")
        await h.connect("other")
        for fields in (
            {},
            {"payload": "x" * 32768},
            {"payload": float("nan")},
            {"payload": None, "metadata": float("inf")},
            {"payload": None, "metadata": "x" * 16384},
            {"payload": None, "expectReply": 1},
        ):
            assert (await h.request(a, to="other", **fields))["status"] == "rejected"
        assert not h.router.routes

    asyncio.run(check())
