"""Guarded flat ESM routes; no browser/provider/native Pi is started."""

import asyncio

import pytest

pytest.importorskip("automata_web_runtime")
httpx = pytest.importorskip("httpx")
from automata.tools.web import host as host_module  # noqa: E402


class InertRpc:
    async def close(self):
        pass


def test_flat_esm_allowlist_retains_local_boundary(tmp_path, monkeypatch):
    async def check():
        public = tmp_path / "public"
        public.mkdir()
        allowed = [
            "index.js",
            "connection-bootstrap.js",
            "ui.js",
            "chunk-ABCDEFGH.js",
            "adapter-LICENSE.txt",
            "third-party-LICENSES.txt",
        ]
        denied = [
            "source.ts",
            "index.js.map",
            "package.json",
            "chunk-invalid.js",
            "ui.js.bak",
            "build-meta.json",
        ]
        for name in allowed + denied:
            (public / name).write_text(name)
        outside = tmp_path / "secret.js"
        outside.write_text("private")
        (public / "chunk-ZZZZZZZZ.js").symlink_to(outside)
        monkeypatch.setattr(host_module, "PACKAGE", tmp_path)
        host = host_module.BrowserHost(rpc=InertRpc())
        host.runtime._origin = "http://127.0.0.1:12345"
        try:
            transport = httpx.ASGITransport(app=host.runtime.app, client=("127.0.0.1", 1234))
            async with httpx.AsyncClient(
                transport=transport,
                base_url=host.runtime.origin,
                headers={"User-Agent": "Automata/1.0"},
            ) as client:
                for name in allowed:
                    response = await client.get(f"/assets/{name}")
                    assert response.status_code == 200, name
                    assert response.text == name
                    assert response.headers["cache-control"] == "no-store"
                    assert (
                        await client.get(f"/assets/{name}", headers={"Host": "evil.test"})
                    ).status_code == 403
                for name in denied + [
                    "chunk-ZZZZZZZZ.js",
                    "chunk-00000000.js",
                    "../frontend/index.ts",
                    "%2e%2e%2ffrontend%2findex.ts",
                    "node_modules/culori/src/index.js",
                ]:
                    assert (await client.get(f"/assets/{name}")).status_code == 404, name
            remote = httpx.ASGITransport(app=host.runtime.app, client=("203.0.113.10", 1234))
            async with httpx.AsyncClient(
                transport=remote,
                base_url=host.runtime.origin,
                headers={"User-Agent": "Automata/1.0"},
            ) as client:
                assert (await client.get("/assets/ui.js")).status_code == 403
        finally:
            await host.close()

    asyncio.run(check())
