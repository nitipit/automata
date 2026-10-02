"""Session revocation races actual Router/ASGI coroutines, with controlled slow writes."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[4] / "src/automata/tools/message-router"))
from automata_router.auth import SessionAuth  # noqa: E402
from automata_router.auth_socket import SessionSocket  # noqa: E402
from automata_router.auth_store import AuthStore  # noqa: E402
from automata_router.protocol import Connection  # noqa: E402
from automata_router.router import Router, validate_config  # noqa: E402
from automata_router.server import RouterApp  # noqa: E402


@pytest.mark.parametrize("invalidation", ["revoke", "expiry", "fail-closed"])
@pytest.mark.parametrize("slow_peer", ["agent", "page", "notification"])
def test_session_retires_during_stalled_send_and_gates_new_outbound(
        tmp_path, invalidation, slow_peer):
    async def check():
        store = AuthStore(tmp_path / "auth", {"page"})
        auth = SessionAuth(store, "http://127.0.0.1:8787")
        backend = Router(validate_config({"v": 1, "participants": {
            "page": {"kind": "page", "token": "p" * 32, "allow": ["agent"]},
            "agent": {"kind": "agent", "token": "a" * 32, "allow": ["page"]},
        }}), public_url=auth.origin)
        token, session = store.exchange(store.pair_code("page")["code"])
        if invalidation == "expiry":
            session["expiresAt"] = time.time() + .15
        blocked, release, authenticated = asyncio.Event(), asyncio.Event(), asyncio.Event()
        agent_output, page_output = [], []
        queue = asyncio.Queue()

        async def agent_send(packet):
            agent_output.append(packet)
            if slow_peer != "page" and packet.get("type") == "message":
                blocked.set()
                await release.wait()
            if slow_peer == "notification" and packet.get("type") == "route_closed":
                await release.wait()

        async def page_send(packet):
            if packet.get("type") == "websocket.send":
                value = json.loads(packet["text"])
                if value["type"] == "hello_ack":
                    authenticated.set()
                if slow_peer == "page" and value["type"] == "message":
                    blocked.set()
                    await release.wait()
            page_output.append(packet)

        agent = Connection(agent_send)
        await backend.authenticate(agent, {"v": 2, "type": "hello", "participant": "agent",
            "token": "a" * 32, "sessionId": "synthetic-session"})
        scope = {"type": "websocket", "path": "/session/ws", "headers": [
            (b"host", auth.host.encode()), (b"origin", auth.origin.encode()),
            (b"cookie", f"automata_router_session={token}".encode())]}
        await queue.put({"type": "websocket.connect"})
        await queue.put({"type": "websocket.receive", "text": '{"v":2,"type":"hello"}'})
        serving = asyncio.create_task(RouterApp(backend, auth=auth)(scope, queue.get, page_send))
        routing = None
        try:
            await asyncio.wait_for(authenticated.wait(), 1)
            page = backend.peers["page"].connection
            route = {"v": 2, "type": "route", "requestId": "stalled", "payload": None,
                     "to": "page" if slow_peer == "page" else "agent"}
            if slow_peer != "page":
                await queue.put({"type": "websocket.receive", "text": json.dumps(route)})
            else:
                routing = asyncio.create_task(backend.packet(agent, route))
            await asyncio.wait_for(blocked.wait(), 1)
            route_id = next(iter(backend.routes))
            if invalidation == "revoke":
                assert auth.revoke(session_id=session["id"]) == 1
            elif invalidation == "fail-closed":
                auth.fail_closed()
            else:
                await asyncio.sleep(.16)
            # Even before retirement is scheduled, a new external caller cannot
            # write through this retained connection object after invalidation.
            delivered = await backend.emit(page, {"type": "response", "payload": "must-not-send"})
            assert delivered is False
            await asyncio.sleep(.02)
            assert "page" not in backend.peers and route_id not in backend.routes
            await asyncio.wait_for(serving, 2)
            if routing:
                await asyncio.wait_for(routing, 1)
            assert "page" not in backend.peers and route_id not in backend.routes
            await backend.packet(agent, {"v": 2, "type": "respond", "requestId": "late",
                "routeId": route_id, "payload": {"newAfterRevocation": True}})
            result = next(packet for packet in reversed(agent_output)
                          if packet.get("requestId") == "late")
            assert result["status"] == "rejected" and result["error"] == "unknown_route"
            assert not any(packet.get("type") == "websocket.send" and
                json.loads(packet["text"])["type"] in {"response", "message"}
                for packet in page_output)
            assert any(packet.get("type") == "websocket.close" for packet in page_output)
            assert not auth.watchers
        finally:
            release.set()
            for task in (serving, routing):
                if task and not task.done():
                    task.cancel()
            await asyncio.gather(*[task for task in (serving, routing) if task],
                                 return_exceptions=True)
            await backend.disconnected(agent)
            await auth.close()
            assert not backend.peers and not backend.routes and not auth.watchers
    asyncio.run(check())


def test_ordinary_connection_close_cancels_external_write_but_keeps_pairing(tmp_path):
    async def check():
        store = AuthStore(tmp_path / "auth", {"page"})
        auth = SessionAuth(store, "http://127.0.0.1:8787")
        token, session = store.exchange(store.pair_code("page")["code"])
        backend = Router(validate_config({"v": 1, "participants": {
            "page": {"kind": "page", "token": "p" * 32, "allow": []},
        }}), public_url=auth.origin)
        blocked, release = asyncio.Event(), asyncio.Event()
        output = []
        async def send(packet):
            if json.loads(packet["text"])["type"] == "response":
                blocked.set()
                await release.wait()
            output.append(packet)
        lifecycle = SessionSocket(auth, session, backend, send)
        await backend.authenticate(lifecycle.connection, {"v": 2, "type": "hello",
            "participant": "page", "token": "p" * 32})
        writing = asyncio.create_task(lifecycle.emit({"type": "response", "payload": "stalled"}))
        try:
            await asyncio.wait_for(blocked.wait(), 1)
            await lifecycle.close()
            with pytest.raises(ValueError, match="revoked"):
                await asyncio.wait_for(writing, 1)
            assert store.session(token) == session  # disconnect is NOT logout
            assert not backend.peers and not auth.watchers
            assert len(output) == 1  # hello only; blocked response never completes
        finally:
            release.set()
            if not writing.done():
                writing.cancel()
            await asyncio.gather(writing, return_exceptions=True)
            await auth.close()
    asyncio.run(check())
