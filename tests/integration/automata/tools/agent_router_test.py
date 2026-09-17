"""Installed standalone CLI and real loopback WebSocket routing, without Pi/model calls."""

from __future__ import annotations

import json
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from automata.install.tools import install_tools


def port_available():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_browser_client_contracts():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required")
    result = subprocess.run(
        [
            node,
            "--test",
            str(Path(__file__).with_name("agent_router_client_test.mjs")),
            str(Path(__file__).with_name("agent_browser_bridge_client_test.mjs")),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_installed_router_without_ui_and_private_static_boundaries(tmp_path):
    websocket = pytest.importorskip("websocket")
    uv = shutil.which("uv")
    if not uv:
        pytest.skip("uv is required")
    tool_root = tmp_path / "tools"
    install_tools(target_root=tool_root, tool_names=["agent-router"])
    entry = tool_root / "agent-router/agent_router.py"
    cli = [uv, "run", "--offline", "--no-project", "--script", str(entry)]
    private = tmp_path / "private"
    config = private / "config.json"
    endpoints = private / "endpoints"
    result = subprocess.run(
        [
            *cli,
            "setup",
            "--config-file",
            str(config),
            "--page",
            "a",
            "--page",
            "b",
            "--agent",
            "agent",
            "--allow",
            "a:b",
            "--allow",
            "a:agent",
            "--allow",
            "agent:a",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert config.stat().st_mode & 0o777 == 0o600
    assert not (tmp_path / "lib").exists()
    assert not (tmp_path / "sessions").exists()
    # Setup refuses silent credential rotation/overwriting configuration.
    again = subprocess.run(
        [*cli, "setup", "--config-file", str(config)], capture_output=True, text=True, timeout=30
    )
    assert again.returncode != 0
    public = tmp_path / "site"
    public.mkdir()
    (public / "index.html").write_text("<p>standalone</p>")
    (public / "secret-link").symlink_to(config)
    (public / ".hidden").write_text("private")
    port = port_available()
    base = f"http://127.0.0.1:{port}"
    command = [
        *cli,
        "serve",
        "--config-file",
        str(config),
        "--endpoint-dir",
        str(endpoints),
        "--port",
        str(port),
        "--public-root",
        str(public),
    ]
    with (tmp_path / "server.log").open("w+") as log:
        process = subprocess.Popen(command, stdout=log, stderr=log)
        connections = []
        try:
            deadline = time.monotonic() + 10
            while not (endpoints / "participants/agent.json").exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    log.seek(0)
                    raise AssertionError(log.read())
                time.sleep(0.03)
            assert urllib.request.urlopen(base + "/").read() == b"<p>standalone</p>"
            for path in (
                "/secret-link",
                "/.hidden",
                "/../private/config.json",
                "/private/config.json",
            ):
                with pytest.raises(urllib.error.HTTPError) as missing:
                    urllib.request.urlopen(base + path)
                assert missing.value.code == 404
            with pytest.raises(websocket.WebSocketBadStatusException):
                websocket.create_connection(
                    f"ws://127.0.0.1:{port}/ws", origin="http://evil.invalid", timeout=2
                )
            with pytest.raises(websocket.WebSocketBadStatusException):
                websocket.create_connection(f"ws://127.0.0.1:{port}/other", origin=base, timeout=2)

            def connect(name):
                record_path = endpoints / "participants" / f"{name}.json"
                record = json.loads(record_path.read_text())
                assert record_path.stat().st_mode & 0o777 == 0o600
                conn = websocket.create_connection(record["wsUrl"], origin=base, timeout=2)
                connections.append(conn)
                conn.send(
                    json.dumps(
                        {
                            "v": 2,
                            "type": "hello",
                            "participant": name,
                            "token": record["token"],
                            **({"sessionId": "pi-1"} if name == "agent" else {}),
                        }
                    )
                )
                assert json.loads(conn.recv())["type"] == "hello_ack"
                return conn

            a, b, agent = connect("a"), connect("b"), connect("agent")
            a.send(
                json.dumps(
                    {"v": 2, "type": "route", "requestId": "one", "to": "b", "payload": None}
                )
            )
            routed = json.loads(b.recv())
            assert routed["from"] == {"id": "a", "kind": "page"}
            assert routed["payload"] is None
            assert json.loads(a.recv())["status"] == "forwarded"
            b.send(
                json.dumps(
                    {
                        "v": 2,
                        "type": "respond",
                        "requestId": "reply",
                        "routeId": routed["id"],
                        "payload": {"ok": True},
                    }
                )
            )
            assert json.loads(a.recv())["payload"] == {"ok": True}
            assert json.loads(b.recv())["status"] == "forwarded"
            # Agent socket received nothing for the page-to-page exchange.
            agent.settimeout(0.05)
            with pytest.raises(websocket.WebSocketTimeoutException):
                agent.recv()
            agent.settimeout(2)
            a.send(
                json.dumps(
                    {"v": 2, "type": "route", "requestId": "two", "to": "agent", "payload": [False]}
                )
            )
            routed = json.loads(agent.recv())
            assert json.loads(a.recv())["status"] == "forwarded"
            agent.close()
            assert json.loads(a.recv())["type"] == "route_closed"
            agent = connect("agent")
            agent.send(
                json.dumps(
                    {
                        "v": 2,
                        "type": "respond",
                        "requestId": "late",
                        "routeId": routed["id"],
                        "payload": "stale",
                    }
                )
            )
            assert json.loads(agent.recv())["error"] == "unknown_route"
            for record in endpoints.rglob("*.json"):
                assert record.stat().st_mode & 0o777 == 0o600
            for connection in connections:
                connection.close()
            deadline = time.monotonic() + 3
            while json.load(urllib.request.urlopen(base + "/health"))["participantsConnected"]:
                assert time.monotonic() < deadline
                time.sleep(0.02)
            node = shutil.which("node")
            if node:
                result = subprocess.run(
                    [
                        node,
                        str(Path(__file__).with_name("agent_router_native_client.mjs")),
                        str(tool_root / "agent-router/browser/client.js"),
                        str(endpoints),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                assert result.returncode == 0, result.stdout + result.stderr
        finally:
            for connection in connections:
                connection.close()
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=10)
            assert not list(endpoints.rglob("*.json"))
            assert config.is_file()  # shutdown never removes persistent grants
        log.seek(0)
        assert "Traceback" not in log.read()
    # Router can start without any public root, library or session directory.
    port = port_available()
    with (tmp_path / "headless.log").open("w+") as log:
        process = subprocess.Popen(
            [
                *cli,
                "serve",
                "--config-file",
                str(config),
                "--endpoint-dir",
                str(endpoints),
                "--port",
                str(port),
            ],
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 10
            while not (endpoints / "participants/agent.json").exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    log.seek(0)
                    raise AssertionError(log.read())
                time.sleep(0.03)
            assert (
                json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/health"))[
                    "participantsConnected"
                ]
                == 0
            )
            with pytest.raises(urllib.error.HTTPError):
                urllib.request.urlopen(f"http://127.0.0.1:{port}/")
        finally:
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=10)
            assert not list(endpoints.rglob("*.json"))
