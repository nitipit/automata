"""Build current Chat and exercise its disconnected local catalog composition.

Browser checks require cached Playwright and AUI_CHROMIUM_EXECUTABLE; no implicit
browser/package downloads or retired agent bridge assets are used.
"""

import functools
import http.server
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

SKILL = (
    Path(__file__).parents[3]
    / "src/automata/skills/bundled/automata-adaptive-ui"
)
LIBRARY = SKILL / "lib"


@pytest.fixture(scope="module")
def chat_catalog(tmp_path_factory) -> Path:
    if not (shutil.which("deno") and shutil.which("node")):
        pytest.skip("Cached Deno and Node are required")
    runtime = tmp_path_factory.mktemp("chat-catalog") / "public"
    result = subprocess.run(
        [sys.executable, str(SKILL / "scripts/build.py"),
         "--runtime-root", str(runtime), "--source-root", str(LIBRARY), "--validate"],
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    shutil.copytree(LIBRARY / "example", runtime / "catalog")
    return runtime


def test_chat_library_build_and_catalog_composition(chat_catalog: Path) -> None:
    bundle = (chat_catalog / "lib/adaptive-ui.js").read_text()
    assert "var Chat = class" in bundle
    assert "agent-message" in bundle
    assert "componentId" in bundle
    assert "WebSocket" not in bundle

    example = (chat_catalog / "catalog/index.html").read_text()
    module = (chat_catalog / "catalog/index.js").read_text()
    assert '<script type="module" src="./index.js"></script>' in example
    assert 'import { Button, Card, Chat } from "/lib/adaptive-ui.js";' in module
    assert module.index('Button.define("aui-button");') < module.index('Chat.define("aui-chat");')
    assert '<aui-chat' in example and 'id="catalog-chat"' in example
    assert "not connected to an agent" in example
    assert "createAgentBrowserBridgeClient" not in module


def test_chat_catalog_is_local_disconnected_presentation(chat_catalog: Path) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    executable = os.environ.get("AUI_CHROMIUM_EXECUTABLE")
    if not executable:
        pytest.skip("Set AUI_CHROMIUM_EXECUTABLE to cached Chrome")
    assert Path(executable).is_file(), "Configured cached Chrome must exist"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(chat_catalog))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with playwright.sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=executable, headless=True)
            try:
                page = browser.new_page()
                errors: list[str] = []
                requests: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: requests.append(request.url))
                origin = f"http://127.0.0.1:{server.server_port}"
                page.goto(origin + "/catalog/")
                page.wait_for_selector("aui-chat textarea")
                outcome = page.evaluate("""() => {
                  const chat = document.querySelector('#catalog-chat');
                  const button = chat.querySelector('aui-button');
                  const native = button.querySelector('button');
                  const composer = chat.querySelector('textarea');
                  let sends = 0;
                  chat.addEventListener('agent-message', () => sends++);
                  const initial = !chat.canSend() && button.hasAttribute('disabled') && native.disabled;
                  chat.addMessage('agent', '<b>Local sample</b>');
                  chat.addMessage('user', 'Sample visitor history');
                  composer.value = 'Unsent local draft'; composer.focus();
                  chat.setAttribute('title', 'Local preview');
                  chat.setAttribute('send-label', 'Unavailable offline');
                  const preserved = composer.value === 'Unsent local draft' &&
                    document.activeElement === composer && chat.querySelectorAll('.message').length === 2;
                  native.click();
                  chat.querySelector('form').requestSubmit();
                  const snapshot = chat.snapshot();
                  const literal = chat.querySelector('[data-role=agent] p').textContent === '<b>Local sample</b>' &&
                    !chat.querySelector('[data-role=agent] b');
                  return {initial, preserved, literal,
                    labelUpdated: native.textContent === 'Unavailable offline',
                    disconnected: !chat.canSend() && native.disabled && button.hasAttribute('disabled'),
                    noSend: sends === 0 && snapshot.pending === false,
                    localSnapshot: snapshot.messages.length === 2 && snapshot.composer === 'Unsent local draft'};
                }""")
                assert all(outcome.values()), outcome
                assert not errors, errors
                assert all(url.startswith(origin + "/") for url in requests), requests
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
