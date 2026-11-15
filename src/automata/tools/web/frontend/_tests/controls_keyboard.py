"""Focused isolated Chromium keyboard/native form test; no host, model or profile.

Run from repository root:
  .venv/bin/python src/automata/tools/web/frontend/_tests/controls_keyboard.py
"""
import asyncio
import subprocess
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[6]
FRONTEND = ROOT / "src/automata/tools/web/frontend"


async def main():
    with tempfile.TemporaryDirectory(prefix="automata-controls-") as tmp:
        bundle = Path(tmp) / "controls.js"
        # Import actual source classes, not mocks; this is not a production graph test.
        # stdin avoids a maintained/generated entry file and keeps shared sources untouched.
        source = """import './_components/button'; import './_components/card'; import './_components/field';"""
        subprocess.run(
            [str(ROOT / "node_modules/.bin/esbuild"), "--bundle", "--format=iife", "--platform=browser", "--target=es2022", f"--outfile={bundle}", "--resolve-extensions=.ts,.js"],
            input=source, text=True, check=True, cwd=FRONTEND,
        )
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
            try:
                page = await browser.new_page(viewport={"width": 390, "height": 844})
                await page.set_content("<main><form><ui-card><h2>Details</h2><ui-field label='Name' help='Your name' name='name' required></ui-field><ui-button type='submit'>Save</ui-button></ui-card></form></main>")
                await page.add_script_tag(path=str(bundle))
                await page.evaluate("""() => {
                  window.submissions = 0;
                  document.querySelector('form').addEventListener('submit', e => {e.preventDefault(); window.submissions++});
                }""")
                textbox = page.get_by_role("textbox", name="Name")
                button = page.get_by_role("button", name="Save")
                assert await textbox.count() == 1 and await button.count() == 1
                await page.keyboard.press("Tab")
                assert await textbox.evaluate("el => document.activeElement === el")
                await page.keyboard.type("Ada")
                await page.keyboard.press("Tab")
                assert await button.evaluate("el => document.activeElement === el")
                await page.keyboard.press("Enter")
                assert await page.evaluate("window.submissions") == 1
                await page.keyboard.press("Space")
                assert await page.evaluate("window.submissions") == 2
                await page.locator("ui-button").evaluate("el => el.disabled = true")
                await button.click(force=True, timeout=1000)
                assert await page.evaluate("window.submissions") == 2
                assert await textbox.evaluate("el => el.labels.length === 1 && el.getAttribute('aria-describedby') !== null")
                assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                print("PASS: isolated Chromium native accessible names, Tab/Enter/Space, form submit, disabled, 390px layout")
            finally:
                await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
