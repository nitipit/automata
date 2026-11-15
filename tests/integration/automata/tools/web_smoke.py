"""Opt-in actual host/Pi/browser smoke; no provider calls or human-input claim.

Run after npm run build:web with web extra + Playwright and existing Chrome:
  python tests/integration/automata/tools/web_smoke.py
No browser driver downloads, credential logs, screenshots, persistent services.
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

from automata.tools.web.host import BrowserHost


async def main():
    fixture = Path(__file__).with_suffix(".ts").resolve()
    host = BrowserHost()
    browser = None
    notifications = []
    errors = []
    original = host.rpc.on_event

    def event(record):
        original(record)
        if record.get("type") == "extension_ui_request" and record.get("method") == "notify":
            notifications.append(record.get("message", ""))

    host.rpc.on_event = event
    try:
        await host.start(extra_args=("-e", str(fixture)))
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path="/usr/bin/google-chrome")
            page = await browser.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            # Intentionally not logged: private admission URL.
            await page.goto(host.runtime.url)
            await page.wait_for_function("window.awr?.status === 'connected'")
            await page.wait_for_function("!document.querySelector('#send').disabled")
            assert await page.evaluate("location.hash") == ""
            await host.runtime.wait_for_browser()
            for _ in range(100):
                if host.connector.session:
                    break
                await asyncio.sleep(0.01)
            subscription = host.connector.subscribe(
                {"name": "smoke-choice", "correlationId": "probe"}
            )
            await host.connector.execute(
                {
                    "code": """
                const button = document.createElement('button');
                button.id = 'probe-control'; button.textContent = 'Synthetic test choice';
                button.addEventListener('click', () => {
                    button.disabled = true;
                    bridge.emit('smoke-choice', {correlationId:'probe', value:'A'});
                }, {once:true});
                document.querySelector('#generated-ui').replaceChildren(button);
                return button.id;
            """
                }
            )
            await page.locator("#probe-control").click()
            result = await host.connector.wait({"subscriptionId": subscription["subscriptionId"]})
            assert result["event"] == {"correlationId": "probe", "value": "A"}
            host.connector.unsubscribe(subscription)
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
            await page.wait_for_function("!document.querySelector('#send').disabled")
            assert json.loads(notifications[-1]) == {
                "confirmed": True,
                "selected": "B",
                "input": "synthetic input",
                "edited": "synthetic edit\nline two",
            }
            assert not host.dialogs
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
            await page.wait_for_function("!document.querySelector('#send').disabled")
            assert host.state["status"] == "idle"
            assert host.rpc.process.returncode is None
            assert not host.dialogs
            assert await page.locator("native-rpc-dialog dialog[open]").count() == 0
            assert not errors, "Browser had JavaScript errors (details withheld)"
            await browser.close()
            browser = None
        print(
            json.dumps(
                {
                    "real_host_pi_browser": "pass",
                    "real_upstream_bridge": "pass",
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
    assert host.rpc.process.returncode == 0
    print("Owned browser, Pi and runtime cleanup: pass")


if __name__ == "__main__":
    asyncio.run(main())
