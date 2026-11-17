"""Read-only reconnect admission checks; no Pi/model or existing host access."""
import asyncio

import pytest

pytest.importorskip("automata_web_runtime")
httpx = pytest.importorskip("httpx")
from automata.tools.web.host import BrowserHost  # noqa: E402


class InertRpc:
    async def close(self):
        pass


def test_connection_probe_preserves_auth_and_cleanup_reservation():
    async def check():
        host = BrowserHost(rpc=InertRpc())
        host.runtime._origin = "http://127.0.0.1:12345"
        headers = {
            "Origin": host.runtime.origin,
            "Authorization": f"Bearer {host.runtime.token}",
            "User-Agent": "Automata/1.0",
        }
        try:
            transport = httpx.ASGITransport(app=host.runtime.app, client=("127.0.0.1", 1234))
            async with httpx.AsyncClient(
                transport=transport, base_url=host.runtime.origin
            ) as client:
                assert (await client.post("/chat/connection")).status_code == 403
                for override in (
                    {"Authorization": "Bearer expired"},
                    {"Origin": "http://evil.test"},
                    {"Host": "evil.test"},
                ):
                    assert (await client.post(
                        "/chat/connection", headers={**headers, **override}
                    )).status_code == 403
                response = await client.post("/chat/connection", headers=headers)
                assert response.status_code == 200 and response.json() == {"ready": True}
                assert response.headers["cache-control"] == "no-store"
                host._chat = object()
                assert (await client.post(
                    "/chat/connection", headers=headers
                )).status_code == 409
                host._chat = None
                host._startup_messages = []
                assert (await client.post(
                    "/chat/connection", headers=headers
                )).status_code == 409
                host._startup_messages = None
                assert host.messages == [] and host.state == {"status": "idle"}
            remote = httpx.ASGITransport(app=host.runtime.app, client=("203.0.113.10", 1234))
            async with httpx.AsyncClient(
                transport=remote, base_url=host.runtime.origin
            ) as client:
                assert (await client.post(
                    "/chat/connection", headers=headers
                )).status_code == 403
        finally:
            host._chat = None
            await host.close()
    asyncio.run(check())
