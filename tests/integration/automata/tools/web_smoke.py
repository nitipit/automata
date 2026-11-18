"""Opt-in actual host/Pi/browser smoke; no provider calls or human-input claim.

Run after npm run build:web with web extra + Playwright and existing Chrome.
Set PI_TEST_PACKAGE_ROOT to the installed Pi package directory, then run:
  python tests/integration/automata/tools/web_smoke.py
Persisted history is seeded through native SessionManager. Current inline execution
uses clearly synthetic live assistant events injected only by this test, not a
model response or production hook. No browser downloads, credentials or services.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from playwright.async_api import async_playwright

from automata.tools.web.host import BrowserHost
from automata.tools.web.rpc import PiRpc


async def main():
    with tempfile.TemporaryDirectory(prefix="automata-web-smoke-") as temporary:
        directory = Path(temporary)
        home, agent = directory / "home", directory / "agent"
        home.mkdir()
        agent.mkdir()
        with patch.dict(os.environ, {"HOME": str(home), "PI_CODING_AGENT_DIR": str(agent)}):
            os.environ.pop("PI_SESSION_FILE", None)
            await exercise(directory)


async def exercise(directory):
    fixture = Path(__file__).with_suffix(".ts").resolve()
    options = (
        "--offline", "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes"
    )
    project = directory / "project"
    project.mkdir()
    sessions = directory / "sessions"
    sessions.mkdir()
    other = directory / "other"
    other.mkdir()
    browser = None
    notifications = []
    errors = []

    def rpc_factory(forward):
        def event(record):
            forward(record)
            if record.get("type") == "extension_ui_request" and record.get("method") == "notify":
                notifications.append(record.get("message", ""))

        return PiRpc(event)

    host = BrowserHost(rpc_factory=rpc_factory)
    try:
        # Native new-session default: no latest-session lookup or provider prompt.
        await host.start(cwd=project, extra_args=(*options, "--session-dir", str(sessions)))
        chat = host.initial_session
        fresh = await chat.rpc.command("get_state")
        assert fresh["sessionId"] and Path(fresh["sessionFile"]).parent == sessions
        assert chat.messages == []
        await host.close()
        assert chat.rpc.process.returncode == 0
        # Seed through native SessionManager with the owner stopped, not a host DB.
        process = await asyncio.create_subprocess_exec(
            "node",
            str(Path(__file__).with_name("web_smoke_seed.mjs").resolve()),
            str(project),
            str(sessions),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        output, _ = await process.communicate()
        assert process.returncode == 0, "Native fixture setup failed (diagnostics withheld)"
        seeded = json.loads(output)
        host = BrowserHost(rpc_factory=rpc_factory)
        await host.start(
            cwd=other,
            session=Path(seeded["sessionFile"]),
            session_inactive=True,
            extra_args=(*options, "-e", str(fixture)),
        )
        chat = host.initial_session
        connector = chat.connector
        assert chat.id == seeded["sessionId"] != fresh["sessionId"]
        assert chat.messages[-2]["details"]["retained"] == [1, 2]
        await chat.handle_command(
            {"type": "prompt", "id": "context-check", "message": "/web-smoke-context"}
        )
        assert json.loads(notifications[-1])["cwd"] == str(project)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path="/usr/bin/google-chrome")
            page = await browser.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            # Intentionally not logged: private admission URL.
            await page.goto(host.admission_url)
            await page.wait_for_function("window.awr?.status === 'connected'")
            await page.wait_for_function("!document.querySelector('#sessions').disabled")
            assert await page.evaluate("location.hash") == ""
            await page.locator('.inactive-ui[data-block-id="smoke-history"]').wait_for()
            assert not await page.evaluate("Boolean(window.__historicalJavaScriptReplayed)")
            assert await page.locator("#generated-ui").count() == 0
            assert connector.session is not None
            # A restored native toolCall is history, not a live execution owner.
            historical = await connector.execute(
                {
                    "toolCallId": "smoke-plain-history",
                    "timeoutMs": 1000,
                    "code": "window.__historicalBodyRan=true; ui.root;",
                }
            )
            assert historical["ok"] is False
            assert historical["error"]["code"] == "ui_unavailable"
            assert historical["error"]["uncertain"] is False
            assert not await page.evaluate("Boolean(window.__historicalBodyRan)")
            # SYNTHETIC LIVE ASSISTANT boundary: no provider, fake human prompt,
            # native-session file mutation, or production test hook. Inject normal
            # live host events, then exercise the real connector/bridge/browser.
            synthetic_owner = {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Synthetic live assistant fixture (no model)"},
                    {
                        "type": "toolCall",
                        "id": "smoke-synthetic-live",
                        "name": "web_ui_execute",
                        "arguments": {},
                    },
                ],
            }
            chat.on_event({"type": "message_start", "message": synthetic_owner})
            chat.on_event({"type": "message_end", "message": synthetic_owner})
            subscription = connector.subscribe({"name": "smoke-choice", "correlationId": "probe"})
            executed = await connector.execute(
                {
                    "toolCallId": "smoke-synthetic-live",
                    "code": """
                const button = document.createElement('button');
                button.id = 'probe-control'; button.textContent = 'Synthetic test choice';
                button.addEventListener('click', () => {
                    button.disabled = true;
                    bridge.emit('smoke-choice', {
                        blockId:ui.blockId, correlationId:'probe', value:'A'
                    });
                }, {once:true});
                ui.root.replaceChildren(button);
                return button.id;
            """,
                }
            )
            assert executed == {
                "ok": True,
                "value": "probe-control",
                "ui": {"blockId": "smoke-synthetic-live", "toolCallId": "smoke-synthetic-live"},
            }
            assert await page.locator("article.assistant #probe-control").count() == 1
            await page.locator("#probe-control").click()
            result = await connector.wait({"subscriptionId": subscription["subscriptionId"]})
            assert result["event"] == {
                "blockId": "smoke-synthetic-live",
                "correlationId": "probe",
                "value": "A",
            }
            connector.unsubscribe(subscription)
            # Leave the page and wait for its old pair to clean up before re-admission.
            await page.goto("about:blank")
            entry = host._entries[chat.id]
            async with asyncio.timeout(5):
                while entry.pair is not None:
                    await asyncio.sleep(0.01)
            await page.goto(host.admission_url)
            await page.wait_for_function("window.awr?.status === 'connected'")
            await page.wait_for_function("!document.querySelector('#sessions').disabled")
            await page.locator('.inactive-ui[data-block-id="smoke-history"]').wait_for()
            assert await page.locator("#probe-control").count() == 0
            assert not await page.evaluate("Boolean(window.__historicalJavaScriptReplayed)")
            # Actual browser -> host -> Pi command -> native RPC dialog -> browser.
            # /web-smoke is handled by a test extension, so it never invokes a model.
            await page.locator("#prompt").fill("/web-smoke")
            await page.locator("#send").click()
            await page.get_by_role("heading", name="Smoke confirm").wait_for()
            await page.get_by_role("button", name="Yes", exact=True).click()
            await page.get_by_role("heading", name="Smoke select").wait_for()
            await page.get_by_role("combobox", name="Smoke select").select_option("B")
            await page.get_by_role("button", name="OK", exact=True).click()
            await page.get_by_role("textbox", name="Smoke input").fill("synthetic input")
            await page.get_by_role("button", name="OK", exact=True).click()
            await page.get_by_role("textbox", name="Smoke editor").fill("synthetic edit\nline two")
            await page.get_by_role("button", name="OK", exact=True).click()
            await page.wait_for_function("!document.querySelector('#sessions').disabled")
            assert json.loads(notifications[-1]) == {
                "confirmed": True,
                "selected": "B",
                "input": "synthetic input",
                "edited": "synthetic edit\nline two",
            }
            assert not chat.dialogs
            # Sequential extension-command dialogs must not deadlock Stop behind
            # their prompt's control lock. Every later native request fails closed.
            await page.locator("#prompt").fill("/web-smoke")
            await page.locator("#send").click()
            await page.get_by_role("heading", name="Smoke confirm").wait_for()
            await (
                page.locator("native-rpc-dialog")
                .get_by_role("button", name="Stop", exact=True)
                .click()
            )
            await page.wait_for_function("!document.querySelector('#sessions').disabled")
            assert chat.state["status"] == "idle"
            assert chat.rpc.process.returncode is None
            assert not chat.dialogs
            assert await page.locator("native-rpc-dialog dialog[open]").count() == 0
            assert not errors, "Browser had JavaScript errors (details withheld)"
            await browser.close()
            browser = None
        print(
            json.dumps(
                {
                    "real_host_pi_browser": "pass",
                    "real_upstream_bridge": "pass",
                    "native_persistent_default_and_explicit_resume": "pass",
                    "native_tool_identity_and_details": "pass",
                    "inline_owner_and_inactive_history_no_replay": "pass",
                    "live_assistant_owner": "synthetic host event injection; no model",
                    "historical_owner_body_blocked": "pass",
                    "native_dialogs": 4,
                    "normal_modal_stop_sequential_dialogs": "pass",
                    "correlated_synthetic_input": "pass",
                    "provider_calls": 0,
                    "human_input": False,
                }
            )
        )
    finally:
        if browser is not None:
            await browser.close()
        await host.close()
    assert chat.rpc.process.returncode == 0
    print("Owned browser, Pi and runtime cleanup: pass")


if __name__ == "__main__":
    asyncio.run(main())
