"""Real loopback and pinned ASGI bridge, fixture RPCs and synthetic browser clients."""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

pytest.importorskip("automata_web_runtime")
httpx = pytest.importorskip("httpx")
ws = pytest.importorskip("websockets.asyncio.client")

from websockets.exceptions import ConnectionClosed, InvalidStatus  # noqa: E402

from automata.tools.web.host import BrowserHost  # noqa: E402
from automata.tools.web.sessions import SessionClaim  # noqa: E402


class FixturePi:
    def __init__(self, factory, event):
        self.factory, self.event = factory, event
        self.commands = []
        self.closed = False
        self.busy = {}

    async def start(self, argv, *, cwd, env):
        self.env = env
        if "--session" in argv:
            self.path = Path(argv[argv.index("--session") + 1])
        else:
            self.path = cwd / f"N{self.factory.clients.index(self)}.jsonl"
        self.id = self.path.stem
        self.history = []
        if self.path.exists():
            lines = self.path.read_text().splitlines()
            self.id = json.loads(lines[0])["id"]
            self.history = [json.loads(line)["message"] for line in lines[1:]]
        self.id = self.factory.mismatch.get(self.id, self.id)
        if self.id in self.factory.fail_history:
            self.history = [None]

    async def command(self, kind, *, timeout=15, **data):
        self.commands.append((kind, data))
        if kind == "get_state":
            return {
                "sessionId": self.id,
                "sessionFile": str(self.path),
                "isStreaming": False,
                "isCompacting": False,
                "pendingMessageCount": 0,
                **self.busy,
            }
        if kind == "get_messages":
            return {"messages": self.history}
        if kind == "prompt":
            self.event(
                {"type": "message_end", "message": {"role": "user", "content": data["message"]}}
            )
            return {"disposition": "started"}
        if kind in {"abort", "clear_queue"}:
            return {}
        raise AssertionError(f"Unexpected RPC command {kind}")

    async def close(self):
        self.closed = True


class Factory:
    def __init__(self):
        self.clients = []
        self.mismatch = {}
        self.fail_history = set()

    def __call__(self, on_event):
        rpc = FixturePi(self, on_event)
        self.clients.append(rpc)
        return rpc


def saved(path, cwd, *, native_id=None):
    path.write_text(
        json.dumps({"type": "session", "id": native_id or path.stem, "cwd": str(cwd)})
        + "\n"
        + json.dumps({"type": "message", "message": {"role": "user", "content": "saved"}})
        + "\n"
    )
    return path


def auth(host, admission):
    return {"Origin": host.runtime.origin, "Authorization": f"Bearer {admission}"}


def socket_uri(host, path, ticket):
    return host.runtime.origin.replace("http:", "ws:") + path + "?token=" + ticket


def open_socket(host, path, ticket):
    return ws.connect(
        socket_uri(host, path, ticket),
        origin=host.runtime.origin,
        open_timeout=2,
        user_agent_header="Automata/1.0",
    )


async def rejected(host, path, ticket):
    with pytest.raises(InvalidStatus) as error:
        async with open_socket(host, path, ticket):
            pytest.fail("Unexpected WebSocket acceptance")
    assert error.value.response.status_code == 403


async def probe(host, client, id, admission):
    return await client.post(f"/sessions/{id}/chat/connection", headers=auth(host, admission))


@asynccontextmanager
async def paired(host, client, id, admission):
    response = await probe(host, client, id, admission)
    assert response.status_code == 200, response.text
    ticket = response.json()["ticket"]
    async with open_socket(host, "/ws", ticket) as bridge:
        async with open_socket(host, f"/sessions/{id}/chat", ticket) as chat:
            snapshot = json.loads(await asyncio.wait_for(chat.recv(), 2))
            assert snapshot["type"] == "snapshot" and snapshot["state"]["sessionId"] == id
            yield ticket, bridge, chat, snapshot


async def ack(socket, kind, id, **data):
    await socket.send(json.dumps({"type": kind, "id": id, **data}))
    async with asyncio.timeout(2):
        while True:
            frame = json.loads(await socket.recv())
            if frame.get("type") == "ack" and frame.get("id") == id:
                return frame


async def fresh(host, client, source, ticket, nonce):
    return await client.post(
        "/sessions",
        headers={"Origin": host.runtime.origin},
        data={
            "sourceSessionId": source.id,
            "admission": source.admission,
            "ticket": ticket,
            "nonce": nonce,
        },
    )


def identity(url):
    parts = urlsplit(url)
    assert not parts.netloc and not parts.query
    return parts.path.split("/")[2], parse_qs(parts.fragment)["admission"][0]


async def eventually(check):
    async with asyncio.timeout(2):
        while not check():
            await asyncio.sleep(0.01)


def test_one_port_two_writers_bridge_routing_stop_reconnect_and_shutdown(tmp_path):
    async def test():
        factory = Factory()
        host = BrowserHost(rpc_factory=factory)
        await host.start(cwd=tmp_path)
        try:
            a = host.initial_session
            async with httpx.AsyncClient(
                base_url=host.runtime.origin, headers={"User-Agent": "Automata/1.0"}
            ) as client:
                async with paired(host, client, a.id, a.admission) as (ta, ba, ca, _):
                    child = await fresh(host, client, a, ta, "unique")
                    assert child.status_code == 303
                    assert (await fresh(host, client, a, ta, "unique")).status_code == 409
                    bid, badm = identity(child.headers["location"])
                    assert bid != a.id and len(factory.clients) == 2
                    b = host._entries[bid].chat
                    assert a.connector_token != b.connector_token
                    assert (await probe(host, client, bid, a.admission)).status_code == 403
                    async with paired(host, client, bid, badm) as (tb, bb, cb, _):
                        assert (await probe(host, client, a.id, a.admission)).json()[
                            "code"
                        ] == "writer_active"
                        await rejected(host, "/ws", tb)
                        await rejected(host, f"/sessions/{a.id}/chat", tb)
                        await rejected(host, f"/sessions/{bid}/chat", tb)
                        results = await asyncio.gather(
                            ack(ca, "prompt", "same-id", sessionId=a.id, message="A request"),
                            ack(cb, "prompt", "same-id", sessionId=b.id, message="B request"),
                        )
                        assert all(result["success"] for result in results)
                        assert [m["content"] for m in a.messages] == ["A request"]
                        assert [m["content"] for m in b.messages] == ["B request"]
                        assert (await ack(cb, "stop", "stop", sessionId=b.id))["success"]
                        assert [kind for kind, _ in b.rpc.commands][-2:] == ["clear_queue", "abort"]
                        assert a.state["status"] == "running" and a.rpc.commands[-1][0] == "prompt"

                        async def connector(chat, action, **body):
                            response = await client.post(
                                "/connector/" + action,
                                json=body,
                                headers={"Authorization": f"Bearer {chat.connector_token}"},
                            )
                            return response.json()

                        ao, bo = await asyncio.gather(
                            *(connector(chat, "subscribe", name="same") for chat in (a, b))
                        )
                        assert (await connector(b, "wait", subscriptionId=ao["subscriptionId"]))[
                            "error"
                        ]["code"] == "subscription_unavailable"
                        aw = asyncio.create_task(
                            connector(
                                a, "wait", subscriptionId=ao["subscriptionId"], timeoutMs=2500
                            )
                        )
                        bw = asyncio.create_task(
                            connector(
                                b, "wait", subscriptionId=bo["subscriptionId"], timeoutMs=2500
                            )
                        )
                        for ctx, bridge, mark in ((a, ba, "A"), (b, bb, "B")):
                            call = asyncio.create_task(
                                connector(ctx, "execute", code=f"return '{mark}'")
                            )
                            execution = json.loads(await asyncio.wait_for(bridge.recv(), 2))
                            assert execution["code"] == f"return '{mark}'"
                            await bridge.send(
                                json.dumps(
                                    {
                                        "type": "result",
                                        "id": execution["id"],
                                        "ok": True,
                                        "value": mark,
                                    }
                                )
                            )
                            assert (await call)["value"] == mark
                        await bb.send(json.dumps({"type": "event", "name": "same", "data": "B"}))
                        assert (await bw)["event"] == "B" and not aw.done()
                        await ba.send(json.dumps({"type": "event", "name": "same", "data": "A"}))
                        assert (await aw)["event"] == "A"
                    await eventually(lambda: host._entries[bid].pair is None)
                    assert a.connector.session.is_connected and not b.connector.subscriptions
                    async with paired(host, client, bid, badm) as (new_ticket, bb, cb, resumed):
                        assert (
                            new_ticket != tb
                            and resumed["messages"] == b.messages
                            and len(factory.clients) == 2
                        )
                        await host.close()
                        for socket in (ba, bb, ca, cb):
                            with pytest.raises(ConnectionClosed):
                                await asyncio.wait_for(socket.recv(), 2)
            assert all(rpc.closed for rpc in factory.clients) and not host._owned
            for rpc in factory.clients:
                SessionClaim(rpc.path).close()
        finally:
            await host.close()

    asyncio.run(asyncio.wait_for(test(), 12))


def test_saved_open_receipt_resume_conflicts_and_failed_start_preserve_source(tmp_path):
    async def test():
        factory = Factory()
        path = saved(tmp_path / "Saved.jsonl", tmp_path)
        saved(tmp_path / "Bad.jsonl", tmp_path)
        factory.mismatch["Bad"] = "wrong-native-id"
        host = BrowserHost(rpc_factory=factory)
        await host.start(cwd=tmp_path)
        try:
            a = host.initial_session
            async with httpx.AsyncClient(base_url=host.runtime.origin) as client:
                async with paired(host, client, a.id, a.admission) as (ticket, _, socket, _):

                    async def listing(id):
                        return (await ack(socket, "list_sessions", id))["data"]["receipt"]

                    async def opened(target, receipt, nonce):
                        return await client.post(
                            f"/sessions/{a.id}/open",
                            headers=auth(host, a.admission),
                            json={
                                "sessionId": target,
                                "receipt": receipt,
                                "inactiveConfirmed": True,
                                "nonce": nonce,
                                "ticket": ticket,
                            },
                        )

                    receipt = await listing("list-one")
                    a.rpc.busy = {"isCompacting": True}
                    assert (await opened("Saved", receipt, "busy")).json()["code"] == "source_busy"
                    a.rpc.busy.clear()
                    claim = SessionClaim(path)
                    try:
                        assert (await opened("Saved", receipt, "locked")).json()[
                            "code"
                        ] == "target_unavailable"
                    finally:
                        claim.close()
                    receipt = await listing("list-stale")
                    path.write_text(path.read_text() + "\n")
                    assert (await opened("Saved", receipt, "stale")).json()[
                        "code"
                    ] == "stale_receipt"
                    saved(path, tmp_path)
                    receipt = await listing("list-duplicate")
                    alias = saved(tmp_path / "duplicate.jsonl", tmp_path, native_id="Saved")
                    assert (await opened("Saved", receipt, "duplicate")).json()[
                        "code"
                    ] == "target_unavailable"
                    alias.unlink()
                    receipt = await listing("list-bad")
                    assert (await opened("Bad", receipt, "bad")).status_code == 503
                    assert factory.clients[-1].closed and a.id == "N0" and not a.rpc.closed
                    assert a.messages == [] and a.state["status"] == "idle"
                    receipt = await listing("list-final")
                    response = await opened("Saved", receipt, "success")
                    assert response.status_code == 200, response.text
                    bid, badm = identity(response.json()["url"])
                    assert response.json()["sessionId"] == bid == "Saved"
                    assert (await opened("Saved", receipt, "success")).json()[
                        "code"
                    ] == "replayed_request"
                    assert a.id == "N0" and a.messages == [] and a.connector.session.is_connected
                    async with paired(host, client, bid, badm) as (_, _, _, snapshot):
                        assert snapshot["messages"] == [{"role": "user", "content": "saved"}]
                    await eventually(lambda: host._entries[bid].pair is None)
                    count = len(factory.clients)
                    again = await opened("Saved", await listing("list-reuse"), "reuse")
                    assert again.status_code == 200 and len(factory.clients) == count
                    _, replacement = identity(again.json()["url"])
                    assert replacement != badm
                    assert (await probe(host, client, bid, badm)).status_code == 403
                    assert all(kind != "switch_session" for kind, _ in a.rpc.commands)
        finally:
            await host.close()

    asyncio.run(asyncio.wait_for(test(), 12))


def test_pair_deadline_and_provisional_fresh_worker_capacity_release(tmp_path):
    async def test():
        factory = Factory()
        host = BrowserHost(rpc_factory=factory, max_sessions=2, pair_seconds=0.2, idle_seconds=0.65)
        await host.start(cwd=tmp_path)
        try:
            a = host.initial_session
            async with httpx.AsyncClient(base_url=host.runtime.origin) as client:
                async with paired(host, client, a.id, a.admission) as (ticket, _, _, _):
                    response = await fresh(host, client, a, ticket, "fresh")
                    assert response.status_code == 303
                    assert (await fresh(host, client, a, ticket, "cap")).status_code == 409
                    assert len(factory.clients) == 2
                    bid, badm = identity(response.headers["location"])
                    b = host._entries[bid].chat
                    denied = await probe(host, client, bid, badm + "bad")
                    assert denied.status_code == 403
                    pending = (await probe(host, client, bid, badm)).json()["ticket"]
                    await rejected(host, f"/sessions/{bid}/chat", pending)
                    async with open_socket(host, "/ws", pending) as half:
                        assert (await probe(host, client, bid, badm)).json()[
                            "code"
                        ] == "pair_reserved"
                        assert b.connector.session is None
                        await asyncio.wait_for(half.wait_closed(), 1)
                    await eventually(lambda: host._entries[bid].pair is None)
                    await rejected(host, "/ws", pending)
                    await eventually(lambda: b.rpc.closed and bid not in host._entries)
                    assert (await probe(host, client, bid, badm)).status_code == 403
                    assert a.connector.session.is_connected
                    assert (await fresh(host, client, a, ticket, "slot")).status_code == 303
        finally:
            await host.close()

    asyncio.run(asyncio.wait_for(test(), 8))
