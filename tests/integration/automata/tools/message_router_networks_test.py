"""Installed CLI/configured generic nodes and native JS clients over actual loopback WS."""

from __future__ import annotations

import json
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path

import pytest

from automata.install.tools import install_tools


def test_installed_generic_network_nodes(tmp_path):
    uv, node = shutil.which("uv"), shutil.which("node")
    if not uv or not node:
        pytest.skip("Cached uv script dependencies and native Node WebSocket are required")
    tools = tmp_path / "tools"
    install_tools(target_root=tools, tool_names=["message-router"])
    tool = tools / "message-router"
    cli = [uv, "run", "--offline", "--no-project", "--script", str(tool / "message_router.py")]
    config = tmp_path / "private/config.json"
    endpoints = tmp_path / "private/endpoints"

    def run(*arguments):
        return subprocess.run([*cli, *arguments], capture_output=True, text=True, timeout=30)

    for command in ("setup", "serve"):
        result = run(command, "--help")
        assert result.returncode == 0, result.stdout + result.stderr
    default = tmp_path / "default.json"
    assert run("setup", "--config-file", str(default)).returncode == 0
    default_value = json.loads(default.read_text())
    assert default_value["v"] == 2
    assert list(default_value["nodes"]) == ["node"]
    result = run("setup", "--config-file", str(config),
                 "--node", "desk", "--node", "viewer", "--node", "worker", "--node", "blocked",
                 "--network", "worker:work", "--allow", "desk:worker",
                 "--allow", "desk:blocked", "--block", "desk:blocked")
    assert result.returncode == 0, result.stdout + result.stderr
    value = json.loads(config.read_text())
    assert value["v"] == 2
    assert value["nodes"]["worker"]["network"] == "work"
    assert value["allow"] == ["desk:worker", "desk:blocked"]
    assert value["block"] == ["desk:blocked"]
    assert config.stat().st_mode & 0o777 == 0o600
    original = config.read_bytes()
    assert run("setup", "--config-file", str(config)).returncode != 0
    assert config.read_bytes() == original
    invalid = tmp_path / "invalid.json"
    rejected = run("setup", "--config-file", str(invalid), "--node", "one",
                   "--allow", "one:unknown")
    assert rejected.returncode != 0
    assert not invalid.exists()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with (tmp_path / "router.log").open("w+") as log:
        process = subprocess.Popen([
            *cli, "serve", "--config-file", str(config), "--endpoint-dir", str(endpoints),
            "--port", str(port),
        ], stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 10
            while not (endpoints / "participants/worker.json").exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    log.seek(0)
                    raise AssertionError(log.read())
                time.sleep(0.02)
            for identity in value["nodes"]:
                path = endpoints / "participants" / f"{identity}.json"
                record = json.loads(path.read_text())
                assert record["kind"] == "node"
                assert record["network"] == value["nodes"][identity].get("network", "default")
                assert path.stat().st_mode & 0o777 == 0o600
            checked = subprocess.run([
                node, str(Path(__file__).with_name("message_router_networks_client.mjs")),
                str(tool / "browser/client.js"), str(endpoints),
            ], capture_output=True, text=True, timeout=20)
            assert checked.returncode == 0, checked.stdout + checked.stderr
            health = run("status", "--endpoint-file", str(endpoints / "server.json"))
            assert health.returncode == 0
            assert json.loads(health.stdout)["status"] == "running"
        finally:
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=10)
        assert not list(endpoints.rglob("*.json"))
        assert config.read_bytes() == original
        log.seek(0)
        assert "Traceback" not in log.read()
