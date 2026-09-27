"""HTTP launch surface accepts an action and fixed identity, never execution input."""
import asyncio
import importlib
import json
from types import SimpleNamespace

import pytest
from starlette.requests import Request


@pytest.fixture
def surface(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_RUNTIME_ROOT", str(tmp_path / "runtime"))
    endpoint = tmp_path / "page.json"
    endpoint.write_text(json.dumps({"kind": "page", "wsUrl": "ws://127.0.0.1:8792/ws",
                                    "participant": "workspace-page", "token": "page-only"}))
    monkeypatch.setenv("WORKSPACE_PAGE_ENDPOINT", str(endpoint))
    monkeypatch.setenv("WORKSPACE_AGENT_ID", "agent-automata")
    monkeypatch.setenv("WORKSPACE_AGENT_PARTICIPANT", "workspace-agent")
    server = importlib.import_module("automata.apps.workspace.server")
    calls = []
    manager = SimpleNamespace(
        config=SimpleNamespace(agent_id="agent-automata", participant="workspace-agent"),
        launch=lambda action: calls.append(action) or {"phase": "starting"},
        status=lambda: {"configured": True, "phase": "offline", "action": "start"},
    )
    monkeypatch.setattr(server.app.state, "lifecycle", manager, raising=False)
    return server, calls


def request(site="same-origin"):
    return Request({"type": "http", "headers": [(b"sec-fetch-site", site.encode())]})


@pytest.mark.parametrize("extra", [
    {"command": "anything"}, {"sessionId": "coordinator"}, {"cwd": "/tmp"},
    {"endpoint": "/private/other"}, {"model": "other"}, {"agentId": "other-agent"},
])
def test_no_browser_control_of_execution_configuration(surface, extra):
    server, calls = surface
    result = server.launch_agent("start", {"agentId": "agent-automata", **extra}, request())
    assert result.status_code == 422
    assert calls == []


def test_only_same_origin_browser_can_launch(surface):
    server, calls = surface
    for site in ("cross-site", "none", ""):
        result = server.launch_agent("start", {"agentId": "agent-automata"}, request(site))
        assert result.status_code == 403
    assert not calls
    assert server.launch_agent("start", {"agentId": "agent-automata"}, request()) == {
        "phase": "starting"}
    assert calls == ["start"]
    assert "token" not in json.dumps(server.agent_lifecycle(request()))


def test_invalid_private_config_does_not_disable_workspace(surface, monkeypatch):
    server, _ = surface
    monkeypatch.setenv("WORKSPACE_AGENT_CONFIG", "/missing/private/configuration.json")

    async def check():
        async with server.lifespan(server.app):
            state = server.agent_lifecycle(request())
            assert state["phase"] == "failed" and state["action"] is None
            assert "/missing/private" not in json.dumps(state)
    asyncio.run(check())
