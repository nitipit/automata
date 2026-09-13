"""Exercise the Pi bridge extension with a bounded fake WebSocket/Pi runtime."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_agent_browser_bridge_extension_round_trip(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js with TypeScript stripping is required")

    source_root = Path(__file__).parents[4]
    extension = tmp_path / "agent-browser-bridge.ts"
    extension.write_text(
        (source_root / "src" / "automata" / "extensions" / "agent-browser-bridge.ts").read_text()
    )
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

    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_suffix(".mjs"))],
        env={**os.environ, "AGENT_BROWSER_BRIDGE_TEST_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
