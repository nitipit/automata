"""Admission boundary checks with isolated stub native RPC, no model or user sessions."""

import asyncio

import pytest

pytest.importorskip("automata_web_runtime")
httpx = pytest.importorskip("httpx")

from automata.tools.web import runtime_adapter  # noqa: E402
from automata.tools.web.host import BrowserHost  # noqa: E402


def test_connection_pairs_are_scoped_host_origin_and_peer_checked(tmp_path):
    class InertRpc:
        async def start(self, *args, **kwargs):
            pass

        async def command(self, kind, **data):
            if kind == "get_state":
                return {"sessionId": "native", "sessionFile": str(tmp_path / "native.jsonl")}
            return {"messages": []}

        async def close(self):
            pass

    async def check():
        host = BrowserHost(rpc_factory=lambda _: InertRpc())
        await host.start(cwd=tmp_path)
        admission = host.initial_session.admission
        headers = {
            "Origin": host.runtime.origin,
            "Authorization": f"Bearer {admission}",
            "User-Agent": "Automata/1.0",
        }
        path = "/chat/sessions/native/chat/connection"
        try:
            transport = httpx.ASGITransport(app=host.runtime.app, client=("127.0.0.1", 1234))
            async with httpx.AsyncClient(
                transport=transport, base_url=host.runtime.origin
            ) as client:
                legacy = await client.get(f"/sessions/native/#admission={admission}")
                assert legacy.status_code == 307
                assert legacy.headers["Location"] == "/chat/sessions/native/"
                shell = await client.get("/chat/sessions/native/")
                assert shell.status_code == 200 and admission not in shell.text
                assert shell.headers["Referrer-Policy"] == "same-origin"
                assert shell.headers["Cache-Control"] == "no-store"
                assert (await client.post(path)).status_code == 403
                assert (
                    await client.post(path.replace("native", "%6eative"), headers=headers)
                ).status_code == 403
                assert (
                    await client.post(path.replace("native", "unknown"), headers=headers)
                ).status_code == 403
                for override in (
                    {"Authorization": "Bearer expired"},
                    {"Origin": "http://evil.test"},
                    {"Origin": "null"},
                    {"Host": "evil.test"},
                ):
                    assert (
                        await client.post(path, headers={**headers, **override})
                    ).status_code == 403
                response = await client.post("/sessions/native/chat/connection", headers=headers)
                assert response.status_code == 200 and response.json()["ticket"] != admission
                assert response.headers["Cache-Control"] == "no-store"
                competing = await client.post(path, headers=headers)
                assert competing.status_code == 409 and competing.json()["code"] == "pair_reserved"
                assert host.initial_session.connector.session is None
                # The empty canonical shell, not the route alone, proves no new worker.
                assert (await client.get("/chat/sessions/unknown/")).status_code == 200
                assert len(host._owned) == 1
            remote = httpx.ASGITransport(app=host.runtime.app, client=("203.0.113.10", 1234))
            async with httpx.AsyncClient(transport=remote, base_url=host.runtime.origin) as client:
                assert (await client.post(path, headers=headers)).status_code == 403
        finally:
            await host.close()

    asyncio.run(check())


def test_runtime_upgrade_metadata_fails_closed(monkeypatch):
    class DifferentRevision:
        version = "0.1.0"

        def read_text(self, name):
            return '{"vcs_info":{"commit_id":"unreviewed"}}'

    monkeypatch.setattr(runtime_adapter, "distribution", lambda _: DifferentRevision())
    with pytest.raises(RuntimeError, match="Incompatible Automata Web Runtime"):
        BrowserHost()
