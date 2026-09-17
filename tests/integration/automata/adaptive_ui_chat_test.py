"""Build and exercise the promoted Adaptive UI Chat component in isolation."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SOURCE = (
    Path(__file__).parents[3]
    / "src"
    / "automata"
    / "skills"
    / "operations"
    / "automata-adaptive-ui"
)
LIBRARY = SOURCE / "lib"
requires_runtime = pytest.mark.skipif(
    shutil.which("deno") is None or shutil.which("node") is None,
    reason="cached Deno and Node are required",
)


@requires_runtime
def test_chat_library_build_and_catalog_example(tmp_path: Path) -> None:
    runtime = tmp_path / "website"
    result = subprocess.run(
        [
            sys.executable,
            str(SOURCE / "scripts" / "build.py"),
            "--runtime-root",
            str(runtime),
            "--source-root",
            str(LIBRARY),
            "--validate",
        ],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    bundle = (runtime / "lib" / "adaptive-ui.js").read_text()
    assert "var Chat = class" in bundle
    assert "agent-message" in bundle
    assert "componentId" in bundle
    assert "WebSocket" not in bundle

    example = (LIBRARY / "example" / "index.html").read_text()
    assert 'import { Base, Button, Card, Chat } from "/lib/adaptive-ui.js";' in example
    button_registration = example.index('Button.define("aui-button");')
    chat_registration = example.index('Chat.define("aui-chat");')
    assert button_registration < chat_registration
    assert "register it before Chat" in example
    assert '<aui-chat' in example


def test_chat_example_uses_only_public_bridge_callbacks() -> None:
    example = (LIBRARY / "example" / "chat-with-agent.html").read_text()
    assert 'from "/lib/adaptive-ui.js"' in example
    assert 'from "/assets/client.js"' in example
    assert "createAgentBrowserBridgeClient" in example
    assert "document.addEventListener(\"agent-message\"" in example
    assert "client.sendMessage(event.detail)" in example
    assert "onMessage(message)" in example
    for status in (
        'case "connecting":',
        'case "connected":',
        'case "sending":',
        'case "accepted":',
        'case "admitted":',
        'case "replied":',
        'case "rejected":',
        'case "disconnected":',
        'case "error":',
    ):
        assert status in example
    assert "WebSocket" not in example
    assert "kind !== \"reply\"" in example
    assert "chat.receiveMessage(message.payload)" in example
