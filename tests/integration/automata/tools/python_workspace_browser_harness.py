# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.28,<1", "playwright==1.63.0", "websocket-client>=1.9.0"]
# ///
"""Real headless browser/agent bridge against an isolated relocated installed example."""

import asyncio
import json
import sys

import httpx
import websocket
from playwright.async_api import async_playwright

ENTRY, WORKSPACE, PORT, CHROME, SCREENSHOT = sys.argv[1:]
ORIGIN = f"http://127.0.0.1:{PORT}"


async def cli(command, code=None, check=True):
    args = ["uv", "run", "--offline", "--script", ENTRY, command, "--workspace", WORKSPACE]
    if code is not None:
        args.append(code)
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), 30)
    reply = json.loads(stdout)
    if check:
        assert process.returncode == 0, stderr.decode() + stdout.decode()
    return reply


async def main():
    errors = []
    initial = (await cli("status"))["result"]
    pids = [initial["kernel_pid"]]
    async with httpx.AsyncClient(base_url=ORIGIN) as client:
        assert (
            await client.post("/execute", json={"code": "1"}, headers={"Origin": ORIGIN})
        ).status_code == 404
        assert (await client.post("/action", json={"action": "increment"})).status_code == 403
        assert (
            await client.post(
                "/action", json={"action": "increment"}, headers={"Origin": "http://evil.example"}
            )
        ).status_code == 403
        assert (await client.get("/", headers={"Host": "evil.example"})).status_code == 403
        for path in ("/server.py", "/.run/server.pid", "/runtime_import.py"):
            assert (await client.get(path)).status_code == 404
    try:
        ws = websocket.create_connection(
            f"ws://127.0.0.1:{PORT}/events", origin="http://evil.example", timeout=3
        )
    except websocket.WebSocketBadStatusException as exc:
        assert exc.status_code == 403
    else:
        ws.close()
        raise AssertionError("Foreign-origin websocket accepted")
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME, headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1000, "height": 850})
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(ORIGIN)
            await page.locator("#connection").filter(has_text="Connected").wait_for()
            identity = await page.locator("#identity").inner_text()
            assert await page.locator("output").inner_text() == "0"
            await page.get_by_role("button", name="Add one", exact=True).click()
            await page.wait_for_function("document.querySelector('output').textContent === '1'")
            first = await cli(
                "execute", "assert counter.value == 1; saved = counter; counter.value += 9"
            )
            second = await cli("execute", "assert saved is counter; counter.value += 1")
            assert first["result"]["publication"]["object_id"] == identity
            assert second["result"]["publication"]["object_id"] == identity
            await page.wait_for_function("document.querySelector('output').textContent === '11'")
            await page.get_by_label("Set value", exact=True).fill("42")
            await page.get_by_role("button", name="Apply value", exact=True).click()
            await page.wait_for_function("document.querySelector('output').textContent === '42'")
            await page.get_by_label("Set value", exact=True).fill("43")
            await page.get_by_label("Set value", exact=True).press("Enter")
            await page.wait_for_function("document.querySelector('output').textContent === '43'")
            failed = await cli(
                "execute", "counter.value += 3; raise ValueError('after mutation')", check=False
            )
            assert failed["result"]["status"] == "error"
            await page.wait_for_function("document.querySelector('output').textContent === '46'")
            # Fixed primitive projection never invokes this arbitrary repr.
            dangerous = await cli(
                "execute",
                "class Dangerous:\n"
                " def __repr__(self): raise AssertionError('repr called')\n"
                "counter.value = Dangerous()",
            )
            assert dangerous["result"]["publication"] is None
            assert "integer" in dangerous["result"]["after_error"]
            await page.wait_for_function("document.querySelector('output').textContent === '—'")
            assert "repr called" not in await page.locator("#log").inner_text()
            await cli("execute", "counter.value = 6")
            await page.wait_for_function("document.querySelector('output').textContent === '6'")
            assert "browser · state" in await page.locator("#log").inner_text()
            assert "python · state" in await page.locator("#log").inner_text()
            reset = await cli("restart")
            pids.append(reset["result"]["kernel_pid"])
            assert reset["result"]["runtime_id"] == initial["runtime_id"]
            assert reset["result"]["generation"] == initial["generation"] + 1
            await page.wait_for_function("document.querySelector('output').textContent === '0'")
            assert "no command replay" in await page.locator("#notice").inner_text()
            await page.set_viewport_size({"width": 390, "height": 844})
            assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            await page.screenshot(path=SCREENSHOT, full_page=True)
            assert not errors, errors
        finally:
            await browser.close()
    await cli("stop")
    print(
        json.dumps(
            {
                "browser_bridge": "passed",
                "runtime_id": initial["runtime_id"],
                "kernel_pids": pids,
                "screenshot": SCREENSHOT,
                "checks": [
                    "installed tool",
                    "relocated example",
                    "browser→kernel",
                    "independent CLI identity",
                    "kernel→browser",
                    "form + Enter",
                    "partial error",
                    "no repr projection",
                    "restart loss/generation",
                    "origin protections",
                    "private sources",
                    "390px layout",
                    "stop",
                ],
            }
        )
    )


asyncio.run(main())
