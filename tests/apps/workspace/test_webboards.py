"""Fixed public board filesystem boundary and all-route API metadata guards."""
import asyncio
import importlib

import pytest
from fastapi.responses import Response
from starlette.requests import Request

from automata.apps.workspace.webboards import (
    ASSETS,
    BOARD_CSP,
    PUBLIC_PATH,
    public_asset,
    read_asset,
)


@pytest.fixture
def runtime(tmp_path):
    web = tmp_path / "northstar/main/web"
    web.mkdir(parents=True)
    (web / "index.html").write_text("<h1>Board</h1>")
    (web / "board.js").write_text("// board")
    (web / "board.css").write_text("body { margin:0 }")
    return tmp_path


def test_explicit_mapping_and_csp(runtime):
    response = public_asset(runtime, "index.html")
    assert response.status_code == 200 and response.body == b"<h1>Board</h1>"
    assert response.headers["content-security-policy"] == BOARD_CSP
    assert "sandbox allow-scripts" in BOARD_CSP and "allow-same-origin" not in BOARD_CSP
    assert "connect-src 'none'" in BOARD_CSP and "form-action 'none'" in BOARD_CSP
    for name in ASSETS:
        assert public_asset(runtime, name).status_code == 200
        for invalid in ("../" + name, "web/" + name, "/" + name, name + "/",
                        "%2e%2e%2f" + name, "..\\" + name):
            assert public_asset(runtime, invalid).status_code == 404
    assert public_asset(runtime, "secret.json").status_code == 404


@pytest.mark.parametrize("name", list(ASSETS))
@pytest.mark.parametrize("part", ["northstar", "main", "web", "asset"])
def test_no_symlinks_in_public_path(runtime, part, name):
    path = runtime / "northstar/main/web" / name
    if part != "asset":
        path = next(parent for parent in path.parents if parent.name == part)
    moved = path.with_name(path.name + "-private")
    path.rename(moved)
    path.symlink_to(moved, target_is_directory=moved.is_dir())
    assert public_asset(runtime, name).status_code == 404


def test_regular_bounded_assets_only(runtime):
    (runtime / "northstar/main/web/board.js").write_bytes(b"x" * 256_001)
    assert public_asset(runtime, "board.js").status_code == 404
    with pytest.raises(ValueError):
        read_asset(runtime, "private.json")


@pytest.mark.parametrize("path", ["/api/state", "/api/conversation-posts",
                                  "/api/agent-binding", "/api/agent-lifecycle",
                                  "/api/agent-lifecycle/start",
                                  "/api/conversations/conversation-aster/messages"])
@pytest.mark.parametrize("headers", [{"origin": "null"}, {"sec-fetch-site": "cross-site"},
                                      {"sec-fetch-dest": "iframe"},
                                      {"sec-fetch-dest": "script"},
                                      {"sec-fetch-dest": "document"}])
def test_all_api_routes_reject_sandbox_access(tmp_path, monkeypatch, path, headers):
    monkeypatch.setenv("WORKSPACE_RUNTIME_ROOT", str(tmp_path))
    server = importlib.import_module("automata.apps.workspace.server")
    headers = {"host": f"127.0.0.1:{server.app.state.port}", **headers}
    request = Request({"type": "http", "path": path, "scheme": "http",
                       "headers": [(key.encode(), value.encode())
                                   for key, value in headers.items()]})
    reached = []

    async def next_handler(request):
        reached.append(request)
        return Response("secret")

    response = asyncio.run(server.local_only(request, next_handler))
    assert response.status_code == 403 and not reached


def test_opaque_requests_only_reach_public_board(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_RUNTIME_ROOT", str(tmp_path))
    server = importlib.import_module("automata.apps.workspace.server")
    request = Request({"type": "http", "path": PUBLIC_PATH + "board.js", "scheme": "http",
                       "headers": [(b"host", f"127.0.0.1:{server.app.state.port}".encode()),
                                   (b"origin", b"null"), (b"sec-fetch-site", b"cross-site")]})

    async def next_handler(request):
        return Response("public")

    response = asyncio.run(server.local_only(request, next_handler))
    assert response.status_code == 200 and response.headers["content-security-policy"] == BOARD_CSP


@pytest.mark.parametrize("headers", [{}, {"sec-fetch-site": "same-origin",
                                          "sec-fetch-dest": "empty"}])
def test_existing_local_api_consumers_are_preserved(tmp_path, monkeypatch, headers):
    monkeypatch.setenv("WORKSPACE_RUNTIME_ROOT", str(tmp_path))
    server = importlib.import_module("automata.apps.workspace.server")
    monkeypatch.setattr(server, "read_binding", lambda: None)
    headers = {"host": f"127.0.0.1:{server.app.state.port}", **headers}
    request = Request({"type": "http", "path": "/api/state", "scheme": "http",
                       "headers": [(key.encode(), value.encode())
                                   for key, value in headers.items()]})

    async def next_handler(request):
        return Response("existing local API")

    response = asyncio.run(server.local_only(request, next_handler))
    assert response.status_code == 200 and response.body == b"existing local API"
