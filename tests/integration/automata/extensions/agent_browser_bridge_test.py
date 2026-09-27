"""Exercise the Pi bridge extension with a bounded fake WebSocket/Pi runtime."""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path

import pytest


def prepare_runtime(tmp_path: Path) -> None:
    source_root = Path(__file__).parents[4]
    extension = tmp_path / "agent-browser-bridge.ts"
    shutil.copytree(
        source_root / "src/automata/runtimes/pi/extensions/message-router",
        tmp_path / "message-router",
    )
    extension.write_text('export {default} from "./message-router/index.ts";\n')
    for relative in ("agent_browser_bridge.py", "browser/client.js", "browser/page.js"):
        destination = tmp_path / ".agents" / "tools" / "agent-browser-bridge" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("artifact\n")
    endpoint = tmp_path / ".agents" / "var" / "tools" / "agent-browser-bridge" / "endpoint.json"
    endpoint.parent.mkdir(parents=True)
    endpoint.write_text(
        json.dumps(
            {
                "wsUrl": "ws://127.0.0.1:9999/ws",
                "publicUrl": "http://127.0.0.1:9999",
                "controlToken": "secret",
            }
        )
    )

    package = tmp_path / "node_modules" / "typebox"
    package.mkdir(parents=True)
    (package / "package.json").write_text(json.dumps({"type": "module", "exports": "./index.js"}))
    (package / "index.js").write_text(
        "export const Type = new Proxy({}, { get: () => (...args) => args });\n"
    )
    pi_package = tmp_path / "node_modules" / "@earendil-works" / "pi-coding-agent"
    pi_package.mkdir(parents=True)
    (pi_package / "package.json").write_text(
        json.dumps({"type": "module", "exports": "./index.js"})
    )
    (pi_package / "index.js").write_text("export {};\n")
    tui_package = tmp_path / "node_modules" / "@earendil-works" / "pi-tui"
    tui_package.mkdir(parents=True)
    (tui_package / "package.json").write_text(
        json.dumps({"type": "module", "exports": "./index.js"})
    )
    (tui_package / "index.js").write_text(
        "export class Text { constructor(text) { this.text = text; } }\n"
    )


def test_agent_browser_bridge_extension_round_trip(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js with TypeScript stripping is required")
    prepare_runtime(tmp_path)
    result = subprocess.run(
        [
            node, "--test", str(Path(__file__).with_suffix(".mjs")),
            str(Path(__file__).with_name("message_router_compat_test.mjs")),
        ],
        env={**os.environ, "AGENT_BROWSER_BRIDGE_TEST_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_agent_browser_bridge_native_pi_lifecycle(tmp_path: Path) -> None:
    package = os.environ.get("AGENT_BROWSER_BRIDGE_NATIVE_PI_PACKAGE")
    node = shutil.which("node")
    if not package or not node:
        pytest.skip("Set AGENT_BROWSER_BRIDGE_NATIVE_PI_PACKAGE to an installed Pi package")
    source = Path(__file__).parents[4] / "src/automata/runtimes/pi/extensions/message-router"
    shutil.copytree(source, tmp_path / "message-router")
    (tmp_path / "agent-browser-bridge.ts").write_text(
        'export {default} from "./message-router/index.ts";\n'
    )
    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_name("agent_browser_bridge_native_test.mjs"))],
        env={**os.environ, "AGENT_BROWSER_BRIDGE_TEST_ROOT": str(tmp_path), "PI_OFFLINE": "1"},
        capture_output=True,
        text=True,
        timeout=40,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_two_pi_adapters_over_real_router_transport(tmp_path: Path) -> None:
    """Actual extension + socket boundary with deterministic Pi API stubs, not live agents."""
    node, uv = shutil.which("node"), shutil.which("uv")
    if not node or not uv:
        pytest.skip("Node and uv are required")
    prepare_runtime(tmp_path)
    tool = Path(__file__).parents[4] / "src/automata/tools/message-router"
    cli = [uv, "run", "--offline", "--no-project", "--script", str(tool / "message_router.py")]
    private = tmp_path / "router-state"
    config, endpoints = private / "config.json", private / "endpoints"
    setup = subprocess.run(
        [
            *cli,
            "setup",
            "--config-file",
            str(config),
            "--agent",
            "agent",
            "--agent",
            "peer",
            "--page",
            "a",
            "--page",
            "b",
            "--allow",
            "a:agent",
            "--allow",
            "b:agent",
            "--allow",
            "agent:peer",
            "--allow",
            "peer:agent",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert setup.returncode == 0, setup.stdout + setup.stderr
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with (tmp_path / "router.log").open("w+") as log:
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
            while not (endpoints / "participants/peer.json").exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    log.seek(0)
                    raise AssertionError(log.read())
                time.sleep(0.02)
            checked = subprocess.run(
                [
                    node,
                    str(Path(__file__).with_name("message_router_transport_test.mjs")),
                ],
                env={
                    **os.environ,
                    "AGENT_BROWSER_BRIDGE_TEST_ROOT": str(tmp_path),
                    "MESSAGE_ROUTER_ENDPOINTS": str(endpoints),
                    "MESSAGE_ROUTER_BROWSER": str(tool / "browser"),
                },
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert checked.returncode == 0, checked.stdout + checked.stderr
        finally:
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=10)
        log.seek(0)
        assert "Traceback" not in log.read()
