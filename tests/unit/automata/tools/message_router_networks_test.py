"""Configured generic nodes, central network policy and unchanged reply capabilities."""

from __future__ import annotations

import asyncio
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[4] / "src/automata/tools/message-router"))
from automata_router.config import validate_config  # noqa: E402
from automata_router.protocol import Connection  # noqa: E402
from automata_router.router import Router  # noqa: E402


def config():
    return {
        "v": 2,
        "nodes": {
            "desk": {"token": "d" * 32},
            "viewer": {"token": "v" * 32},
            "blocked": {"token": "b" * 32},
            "worker": {"token": "w" * 32, "network": "work"},
            "reviewer": {"token": "r" * 32, "network": "work"},
        },
        "allow": ["desk:worker", "desk:blocked"],
        "block": ["desk:blocked", "worker:reviewer"],
    }


def test_network_policy_is_central_directed_and_block_wins():
    grants = validate_config(config())
    assert grants["desk"].network == "default"
    assert grants["desk"].kind == "node"
    assert grants["desk"].allow == {"viewer", "worker"}
    assert grants["viewer"].allow == {"desk", "blocked"}
    assert grants["worker"].allow == set()
    assert grants["reviewer"].allow == {"worker"}
    assert "desk" not in grants["worker"].allow  # No reverse cross-network grant.


@pytest.mark.parametrize("change", [
    {"v": True}, {"v": 3}, {"extra": 1}, {"nodes": {}},
    {"allow": ["desk:unknown"]}, {"block": ["unknown:desk"]},
    {"allow": [["desk", "viewer"]]}, {"block": "desk:viewer"},
])
def test_invalid_config_is_rejected(change):
    value = config()
    value.update(change)
    with pytest.raises(ValueError):
        validate_config(value)


@pytest.mark.parametrize("spec", [
    {"token": "short"}, {"token": "x" * 32, "network": "two:networks"},
    {"token": "x" * 32, "network": ["a", "b"]},
    {"token": "x" * 32, "kind": "unknown"},
    {"token": "x" * 32, "allow": ["viewer"]},
    {"token": "v" * 32},  # Duplicate configured credential.
])
def test_invalid_node_is_rejected(spec):
    value = config()
    value["nodes"]["desk"] = spec
    with pytest.raises(ValueError):
        validate_config(value)


def test_v1_remains_explicit_only_and_does_not_gain_network_defaults():
    value = {"v": 1, "participants": {
        "a": {"kind": "page", "token": "a" * 32, "allow": ["b"]},
        "b": {"kind": "page", "token": "b" * 32, "allow": []},
    }}
    grants = validate_config(value)
    assert grants["a"].allow == {"b"}
    assert not grants["b"].allow
    assert grants["a"].network is None
    value["participants"]["a"]["network"] = "default"
    with pytest.raises(ValueError):
        validate_config(value)  # No accidental hybrid contract.


def test_generic_admission_status_routing_reply_and_disconnect():
    async def check():
        value = config()
        router = Router(validate_config(value), public_url="http://127.0.0.1:8787")
        received, connections = {}, {}
        serial = 0

        async def connect(identity, *, token=None, session=None):
            messages = []

            async def emit(packet):
                messages.append(packet)

            conn = Connection(emit)
            hello = {"v": 2, "type": "hello", "participant": identity,
                     "token": token or value["nodes"].get(identity, {}).get("token", "u" * 32)}
            if session is not None:
                hello["sessionId"] = session
            await router.authenticate(conn, hello)
            received[identity], connections[identity] = messages, conn
            return conn

        async def request(identity, action="route", **fields):
            nonlocal serial
            serial += 1
            await router.packet(connections[identity], {
                "v": 2, "type": action, "requestId": f"q{serial}", **fields,
            })
            return received[identity][-1]

        for identity, token in (("unknown", None), ("desk", "wrong" * 8)):
            with pytest.raises(ValueError, match="Unauthorized"):
                await connect(identity, token=token)
        desk = await connect("desk")
        viewer = await connect("viewer")
        worker = await connect("worker", session="real-session")
        await connect("blocked")
        with pytest.raises(ValueError, match="already connected"):
            await connect("desk")
        assert received["desk"][0] == {
            "v": 2, "type": "hello_ack", "participant": "desk", "kind": "node",
            "network": "default",
        }
        status = await request("desk", "status")
        assert status["network"] == "default"
        assert status["destinations"] == [
            {"id": "viewer", "kind": "node", "network": "default", "connected": True},
            {"id": "worker", "kind": "node", "network": "work", "connected": True},
        ]
        assert (await request("desk", to="blocked", payload=None))["error"] == "forbidden"
        assert (await request("viewer", to="worker", payload=None))["error"] == "forbidden"
        assert (await request("desk", to="reviewer", payload=None))["error"] == "forbidden"
        same = await request("desk", to="viewer", payload={"same": True})
        assert same["status"] == "forwarded"
        assert received["viewer"][-1]["from"] == {
            "id": "desk", "kind": "node", "network": "default",
        }
        assert (await request("viewer", "respond", routeId=same["routeId"],
                              payload={"ok": True}))["status"] == "forwarded"
        assert received["desk"][-1]["requestId"] == same["requestId"]
        cross = await request("desk", to="worker", payload=None)
        assert cross["status"] == "forwarded"
        assert (await request("worker", to="desk", payload=None))["error"] == "forbidden"
        # Return capability needs no reverse initiation permission.
        assert (await request("worker", "respond", routeId=cross["routeId"],
                              payload=False, final=False))["status"] == "forwarded"
        assert received["desk"][-1]["from"] == {
            "id": "worker", "kind": "node", "network": "work", "sessionId": "real-session",
        }
        await router.disconnected(worker)
        assert received["desk"][-1]["type"] == "route_closed"
        assert not router.routes
        await connect("worker", session="replacement")
        assert (await request("worker", "respond", routeId=cross["routeId"],
                              payload="late"))["error"] == "unknown_route"
        await router.disconnected(worker)  # Cannot disconnect the replacement.
        assert "worker" in router.peers
        await router.disconnected(viewer)
        assert (await request("desk", to="viewer", payload=None))["error"] == "offline"
        assert (await request("desk", "status"))["destinations"][0]["connected"] is False
        await router.disconnected(desk)

    asyncio.run(check())


def test_config_defaults_do_not_mutate_input():
    value = config()
    original = copy.deepcopy(value)
    validate_config(value)
    assert value == original
