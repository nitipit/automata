"""Real loopback/browser bridge checks for the new-session-only browser grant."""

import asyncio
import re
import secrets

import pytest

pytest.importorskip("automata_web_runtime")
httpx = pytest.importorskip("httpx")

from automata.tools.web.host import _TRUST_COOKIE, BrowserHost  # noqa: E402
from tests.unit.automata.tools.web_multi_session_test import (  # noqa: E402
    Factory,
    auth,
    fresh,
    identity,
    paired,
)

DIRECT = {
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-User": "?1",
}
LANDING = "/chat/sessions/"
CREATE = LANDING + "trust/create"


def test_browser_trust_active_writer_dual_proof_replay_and_expiry(tmp_path):
    async def exercise():
        factory = Factory()
        host = BrowserHost(rpc_factory=factory)
        clock = [1000.0, 100_000.0]
        host._browser_trust.clock = lambda: tuple(clock)
        await host.start(cwd=tmp_path)
        try:
            session = host.initial_session
            renew_path = f"{LANDING}{session.id}/browser-trust"
            proof = secrets.token_hex(32)
            origin = {"Origin": host.runtime.origin}
            headers = auth(host, session.admission)
            async with httpx.AsyncClient(base_url=host.runtime.origin, trust_env=False) as client:

                async def intent(path=LANDING):
                    landing = await client.get(path, headers=DIRECT)
                    assert landing.status_code == 200
                    assert 'data-auto="1"' in landing.text
                    assert landing.headers["cache-control"] == "no-store"
                    assert "set-cookie" not in landing.headers
                    return re.search(r'data-intent="([^"<>]+)"', landing.text)[1]

                prefetch = await client.get(LANDING, headers={**DIRECT, "Sec-Purpose": "prefetch"})
                assert 'data-auto="0"' in prefetch.text
                assert 'data-auto="0"' in (await client.get(LANDING)).text
                assert (
                    await client.get(LANDING, headers={"Host": "unrelated.test"})
                ).status_code == 403
                assert (await client.get(CREATE)).status_code == 405
                assert not host._browser_trust.grants and not host._browser_trust.used
                assert len(factory.clients) == 1
                assert (
                    await client.post(
                        renew_path, headers=headers, json={"proof": proof, "ticket": "bogus"}
                    )
                ).status_code == 403

                async with paired(host, client, session.id, session.admission) as (ticket, *_):
                    first = await client.post(
                        renew_path, headers=headers, json={"proof": proof, "ticket": ticket}
                    )
                    assert first.status_code == 204
                    for attributes in first.headers.get_list("set-cookie"):
                        for attr in ("httponly", "secure", "samesite=strict", "max-age=1800"):
                            assert attr in attributes.lower()
                        assert "domain=" not in attributes.lower()
                    cookie = first.cookies.get(_TRUST_COOKIE, path=LANDING + "trust/")
                    assert cookie
                    assert first.cookies.get(_TRUST_COOKIE, path="/sessions/trust/") == cookie
                    trusted = {**origin, "Cookie": f"{_TRUST_COOKIE}={cookie}"}
                    challenge = await intent()
                    request = {"proof": proof, "intent": challenge}
                    assert (
                        await client.post(CREATE, headers=origin, json=request)
                    ).status_code == 403
                    assert (
                        await client.post(
                            CREATE, headers=trusted, json={**request, "proof": "0" * 64}
                        )
                    ).status_code == 403
                    assert (
                        await client.post(
                            CREATE,
                            headers={**trusted, "Origin": "http://127.0.0.1:1"},
                            json=request,
                        )
                    ).status_code == 403
                    assert (
                        await client.post(
                            CREATE, headers=trusted, json={**request, "intent": challenge[:-1]}
                        )
                    ).status_code == 400
                    assert (
                        await client.post(
                            renew_path, headers=trusted, json={"proof": proof, "ticket": ticket}
                        )
                    ).status_code == 403
                    assert (
                        await client.post(f"{LANDING}{session.id}/chat/connection", headers=trusted)
                    ).status_code == 403
                    assert not host._browser_trust.used and len(factory.clients) == 1

                    results = await asyncio.gather(
                        *(client.post(CREATE, headers=trusted, json=request) for _ in range(2))
                    )
                    assert sorted(response.status_code for response in results) == [200, 409]
                    issued = next(
                        response.json()["url"]
                        for response in results
                        if response.status_code == 200
                    )
                    child, admission = identity(issued)
                    assert child != session.id and admission != session.admission
                    assert len(factory.clients) == 2
                    async with paired(host, client, child, admission) as (child_ticket, *_):
                        clock[0] += 600
                        clock[1] += 600
                        second = await client.post(
                            f"{LANDING}{child}/browser-trust",
                            headers=auth(host, admission),
                            json={"proof": proof, "ticket": child_ticket},
                        )
                        assert second.status_code == 204
                        assert second.cookies.get(_TRUST_COOKIE, path=LANDING + "trust/") == cookie
                        valid = await intent("/sessions/")
                        legacy = await client.post(
                            "/sessions/trust/create",
                            headers=trusted,
                            json={"proof": proof, "intent": valid},
                        )
                        assert legacy.status_code == 200
                        assert identity(legacy.json()["url"])[0] not in {session.id, child}
                    clock[1] += 1800  # Suspend: wall advances while monotonic does not.
                    later = {"proof": proof, "intent": await intent()}
                    assert (
                        await client.post(CREATE, headers=trusted, json=later)
                    ).status_code == 403
                    reacquired = await client.post(
                        renew_path, headers=headers, json={"proof": proof, "ticket": ticket}
                    )
                    assert (
                        reacquired.status_code == 204
                        and reacquired.cookies.get(_TRUST_COOKIE, path=LANDING + "trust/") != cookie
                    )
                    assert (
                        await client.post(CREATE, headers=trusted, json=later)
                    ).status_code == 403
                    created = await fresh(
                        host, client, session, ticket, "old-form", path="/sessions"
                    )
                    assert created.status_code == 303
                    assert identity(created.headers["Location"])[0] != session.id
        finally:
            await host.close()
        assert all(rpc.closed for rpc in factory.clients)

    asyncio.run(exercise())
