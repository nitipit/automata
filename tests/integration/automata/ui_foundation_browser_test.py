"""UI Foundation behavior in cached Chrome; no dependency/browser downloads."""

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).parents[3]
WEB_DEV = ROOT / "src/automata/skills/bundled/automata-web-dev"


@pytest.fixture(scope="module")
def foundation_browser(tmp_path_factory):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = os.environ.get("AUI_CHROMIUM_EXECUTABLE")
    if not executable or not Path(executable).is_file():
        pytest.skip("Set AUI_CHROMIUM_EXECUTABLE to cached Chrome")
    if not shutil.which("deno"):
        pytest.skip("Requires cached Deno dependencies")
    pytest.importorskip("uvicorn")
    pytest.importorskip("fastapi")
    project = tmp_path_factory.mktemp("ui-foundation") / "webapp with spaces"
    commands = [
        [sys.executable, str(WEB_DEV / "scripts/create.py"), "--output", str(project)],
        ["deno", "install", "--cached-only", "--allow-scripts=npm:esbuild"],
        ["deno", "task", "check"],
        ["deno", "task", "build"],
    ]
    for index, command in enumerate(commands):
        result = subprocess.run(command, cwd=project if index else ROOT,
                                capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    with (project / "server.log").open("w") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
             "--port", str(port)], cwd=project, stdout=log, stderr=log,
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    pytest.fail((project / "server.log").read_text())
                try:
                    with urlopen(url, timeout=.2) as response:
                        assert response.status == 200
                    break
                except (URLError, TimeoutError):
                    time.sleep(.05)
            else:
                pytest.fail("Owned preview did not start")
            with playwright.sync_playwright() as runtime:
                browser = runtime.chromium.launch(executable_path=executable, headless=True)
                try:
                    yield browser, url
                finally:
                    browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)


def test_button_contract_and_chat_gates(foundation_browser):
    browser, url = foundation_browser
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(url + "/design/components/")
        page.wait_for_function("customElements.get('ui-chat') !== undefined")
        assert not errors, errors
        page.wait_for_selector("ui-chat textarea")
        result = page.evaluate("""() => {
          const Button = customElements.get('ui-button');
          const Chat = customElements.get('ui-chat');
          const fixture = document.createElement('form');
          document.body.append(fixture);
          let submits = 0, clicks = 0;
          fixture.addEventListener('submit', event => { event.preventDefault(); submits++; });
          const button = Button.create({data: Button.validateData({label:'Test', type:'submit', disabled:true})});
          fixture.append(button);
          const native = button.querySelector('button');
          native.addEventListener('click', () => clicks++);
          native.click(); native.focus();
          const disabled = native.disabled && button.hasAttribute('disabled') &&
            button.getAttribute('aria-disabled') === 'true' && document.activeElement !== native &&
            submits === 0 && clicks === 0;
          button.setAttribute('label', 'Still disabled');
          button.setAttribute('disabled', 'false');
          const presence = native.disabled && native.textContent === 'Still disabled';
          button.removeAttribute('disabled');
          native.click(); native.focus();
          const enabled = !native.disabled && submits === 1 && clicks === 1 &&
            document.activeElement === native && button.getAttribute('aria-disabled') === 'false';
          button.applyData(Button.validateData({label:'Applied', disabled:true}));
          const applied = native.disabled && button.hasAttribute('disabled');
          const attributeCreated = document.createElement('ui-button');
          attributeCreated.setAttribute('label', 'Attribute-created');
          attributeCreated.setAttribute('disabled', '');
          fixture.append(attributeCreated);
          const attributes = attributeCreated.querySelector('button').disabled;

          const chat = Chat.create({data: Chat.validateData({})});
          document.body.append(chat);
          const send = chat.querySelector('aui-button');
          let sends = 0;
          chat.addEventListener('agent-message', () => sends++);
          const state = expected => send.hasAttribute('disabled') === expected &&
            send.querySelector('button').disabled === expected && chat.canSend() === !expected;
          const initial = state(true);
          chat.setConnection(true); const busy = state(true);
          chat.setAgentBusy(false); const ready = state(false);
          chat.querySelector('textarea').value = 'Hello';
          send.querySelector('button').click();
          const pending = state(true) && sends === 1;
          chat.setConnection(false); chat.setConnection(true);
          chat.querySelector('form').requestSubmit();
          const noReplay = state(true) && sends === 1;
          chat.receiveMessage({type:'text', data:'Reply'});
          const reply = state(false);
          chat.setAgentBusy(true);
          chat.querySelector('form').requestSubmit();
          const busyGate = state(true) && sends === 1;
          chat.setAgentBusy(false); chat.setConnection(false);
          const disconnected = state(true);
          chat.setConnection(true); chat.dispose();
          const disposed = state(true);
          fixture.remove(); chat.remove();
          return {disabled, presence, enabled, applied, attributes, initial, busy,
            ready, pending, noReplay, reply, busyGate, disconnected, disposed};
        }""")
        assert all(result.values()), result
        assert not errors, errors
    finally:
        page.close()


def test_design_routes_theme_sizing_and_local_interactions(foundation_browser):
    browser, url = foundation_browser
    page = browser.new_page(viewport={"width": 1000, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(url + "/design/tokens/")
        page.wait_for_selector("#semantic-tokens .resolved")
        assert page.locator("#semantic-tokens .token-row").count() == 16
        action = page.locator('#semantic-tokens [data-role="action"]')
        assert action.get_attribute("data-palette") == "blue.4"
        assert action.get_attribute("data-variable") == "--aui-action"
        assert "Palette blue.4 → semantic action" in action.inner_text()
        assert "App override: blue.4 (#1c71d8)" in action.inner_text()
        assert page.locator('#palette-tokens [data-palette="blue.4"]').is_visible()
        page.get_by_text("Component color relationships", exact=True).click()
        background = page.locator('#component-tokens [data-component="Button"][data-semantic="action"]')
        assert "Palette blue.4 → semantic action → Button.background" in background.inner_text()
        assert background.locator(".resolved").inner_text() == "Resolved: rgb(28, 113, 216)"
        assert page.locator('[data-role="action"] .resolved').inner_text() == "Resolved: rgb(28, 113, 216)"
        assert "none (library fallback)" in page.locator('[data-role="messageAgentSurface"]').inner_text()
        assert page.locator("#app-overrides").inner_text().find("--app-background") >= 0
        page.get_by_role("link", name="Components", exact=True).click()
        page.wait_for_function("customElements.get('ui-chat') !== undefined")
        assert not errors, errors
        page.wait_for_selector("ui-chat .message")
        page.get_by_role("button", name="Primary", exact=True).click()
        assert page.locator("#button-result").inner_text() == "Primary clicked."
        assert page.get_by_role("button", name="Disabled", exact=True).is_disabled()
        page.get_by_role("button", name="Toggle disabled", exact=True).click()
        page.get_by_role("button", name="Enabled", exact=True).click()
        assert page.locator("#button-result").inner_text() == "Enabled button clicked."
        page.get_by_label("Name", exact=True).fill("Alex")
        page.get_by_label("Compact", exact=True).check()
        page.get_by_role("button", name="Update form title", exact=True).click()
        assert page.get_by_label("Name", exact=True).input_value() == "Alex"
        assert page.get_by_label("Compact", exact=True).is_checked()
        page.get_by_role("button", name="Show values locally", exact=True).click()
        assert '"name": "Alex"' in page.locator("#form-result").inner_text()
        assert '"density": "compact"' in page.locator("#form-result").inner_text()
        page.get_by_role("button", name="Reset drafts", exact=True).click()
        assert page.get_by_label("Name", exact=True).input_value() == ""
        assert not page.get_by_label("Compact", exact=True).is_checked()
        assert page.locator("ui-chat aui-button button").is_disabled()
        before = page.locator('ui-chat [data-role="agent"]').evaluate("e => getComputedStyle(e).backgroundColor")
        assert before == "rgb(246, 245, 244)"
        page.get_by_role("button", name="Toggle message theme", exact=True).click()
        themed = page.locator("ui-chat").evaluate("""chat => {
          const agent = getComputedStyle(chat.querySelector('[data-role=agent]'));
          const user = getComputedStyle(chat.querySelector('[data-role=user]'));
          const style = getComputedStyle(chat);
          return [agent.backgroundColor, agent.color, user.backgroundColor, user.color,
            style.height, style.minHeight, style.fontSize, chat.getBoundingClientRect().width];
        }""")
        assert themed[:7] == ["rgb(143, 240, 164)", "rgb(36, 31, 49)",
                              "rgb(220, 138, 221)", "rgb(36, 31, 49)", "544px", "320px", "16px"]
        assert themed[7] == 592
        page.set_viewport_size({"width": 375, "height": 812})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.get_by_role("button", name="Add one", exact=True).click()
        assert page.locator("demo-counter output").inner_text() == "1"
        page.get_by_role("navigation", name="Main navigation").get_by_role("link", name="How it works", exact=True).click()
        assert page.locator("h1").count() == 1
        assert page.request.get(url + "/app/templates/base.ts").status == 404
        assert not errors, errors
    finally:
        page.close()
