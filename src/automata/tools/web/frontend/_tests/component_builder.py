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

from playwright.async_api import async_playwright

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
            finally:
                await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
