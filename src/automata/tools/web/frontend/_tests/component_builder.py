"""Isolated Chromium descriptor test; no host, model or real browser profile.

Run from the repository root with Playwright and Chrome/Chromium installed:
  .venv/bin/python src/automata/tools/web/frontend/_tests/component_builder.py
"""

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[6]
FRONTEND = ROOT / "src/automata/tools/web/frontend"


async def main():
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        raise RuntimeError("Chrome/Chromium not found")
    with tempfile.TemporaryDirectory(prefix="automata-builder-") as tmp:
        assets = Path(tmp)
        subprocess.run(
            [
                str(ROOT / "node_modules/.bin/esbuild"),
                "ui=ui.ts",
                "component-builder-test=_tests/component-builder-test.js",
                "--bundle",
                "--splitting",
                "--format=esm",
                "--platform=browser",
                "--target=es2022",
                "--external:/assets/ui.js",
                f"--outdir={assets}",
            ],
            check=True,
            cwd=FRONTEND,
        )
        files = {f"/assets/{file.name}": file for file in assets.glob("*.js")}
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path=chrome, headless=True)
            try:
                page = await browser.new_page()

                async def route_asset(route):
                    url = urlsplit(route.request.url)
                    if url.netloc != "127.0.0.1":
                        await route.abort()
                    elif url.path == "/":
                        await route.fulfill(
                            content_type="text/html", body="<!doctype html><main></main>"
                        )
                    elif url.path in files:
                        await route.fulfill(path=files[url.path], content_type="text/javascript")
                    else:
                        await route.abort()

                await page.route("**/*", route_asset)
                await page.goto("http://127.0.0.1/")
                await page.evaluate(
                    "async () => (await import('/assets/component-builder-test.js')).run()"
                )
                print("PASS: builder parity, recursive order, safe data and registry isolation")
                await page.evaluate("""async () => {
                    const { createComponent, setTheme } = await import('/assets/ui.js');
                    const descriptor = JSON.parse(`{"_class":"ui-select","_data":{
                        "label":"Delivery speed","name":"speed","value":"standard","options":[
                            {"value":"standard","label":"Standard"},
                            {"value":"overnight","label":"Overnight","disabled":true},
                            {"value":"express","label":"Express"}
                        ]
                    }}`);
                    const form = document.createElement('form');
                    const widget = createComponent(descriptor);
                    window.fixtureChanges = [];
                    widget.addEventListener('change', event => window.fixtureChanges.push([
                        event.isTrusted, event.target === widget.control, widget.value,
                    ]));
                    form.append(widget);
                    document.querySelector('main').append(form);
                    setTheme(form, { roles: { surface: '#112233' } });
                }""")
                select = page.get_by_role("combobox", name="Delivery speed", exact=True)
                await expect(select).to_have_css("background-color", "rgb(17, 34, 51)")
                await page.keyboard.press("Tab")
                await expect(select).to_be_focused()
                await page.keyboard.press("ArrowDown")
                await expect(select).to_have_value("express")
                assert await page.evaluate("window.fixtureChanges") == [[True, True, "express"]]
                assert (
                    await page.evaluate("new FormData(document.querySelector('form')).get('speed')")
                    == "express"
                )
                print("PASS: standalone JSON select, accessible name, theme and native form input")
            finally:
                await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
