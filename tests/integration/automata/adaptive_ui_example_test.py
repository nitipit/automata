"""Installed multi-file example: real browser styles, assets and interactions.

Set AUI_CHROMIUM_EXECUTABLE to an existing cached Chromium executable and run
with cached Playwright. No browser, package or library downloads are performed.
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

from automata.install.skills import install_skills


@pytest.fixture
def installed_example(tmp_path: Path) -> tuple[Path, Path]:
    install_skills(
        target_root=tmp_path / "skills", skill_names=["automata-adaptive-ui"]
    )
    skill = tmp_path / "skills" / "automata-adaptive-ui"
    return skill, skill / "lib" / "example"


def test_example_companions_are_installed(installed_example: tuple[Path, Path]) -> None:
    _, example = installed_example
    for relative in (
        "index.html", "index.js", "index.css.js", "catalog.svg",
        "_components/example-note.js", "_components/example-note.css.js",
        "reactive-shadow.html",
    ):
        assert (example / relative).is_file(), relative


def test_example_styles_assets_and_keyboard_navigation(
    installed_example: tuple[Path, Path], tmp_path: Path,
) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    executable = os.environ.get("AUI_CHROMIUM_EXECUTABLE")
    if not executable or not Path(executable).is_file():
        pytest.skip("Set AUI_CHROMIUM_EXECUTABLE to an existing cached Chromium executable")
    if not (shutil.which("deno") and shutil.which("node")):
        pytest.skip("Requires cached Deno and Node for the isolated UI build")

    skill, example = installed_example
    root = tmp_path / "public"
    result = subprocess.run(
        [sys.executable, str(skill / "scripts/build.py"), "--runtime-root", str(root)],
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # Relocation under a page path exercises relative JS, CSS and image URLs.
    shutil.copytree(example, root / "pages" / "catalog")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with playwright.sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=executable, headless=True)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 1000})
                errors: list[str] = []
                failed_resources: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("requestfailed", lambda request: failed_resources.append(request.url))
                page.on("response", lambda response: failed_resources.append(response.url)
                        if response.status >= 400 else None)
                page.goto(f"http://127.0.0.1:{server.server_port}/pages/catalog/")
                page.wait_for_function("customElements.get('aui-chat') !== undefined")
                assert page.locator("example-note").count() == 3
                assert page.locator(".catalog-heading img").evaluate(
                    "image => image.complete && image.naturalWidth === 64"
                )

                # The page owns document layout/theme; Adapter owns note internals.
                outcome = page.evaluate("""async () => {
                  const { pageStyles } = await import('./index.css.js');
                  const style = node => getComputedStyle(node);
                  const note = document.querySelector('example-note');
                  const heading = note.querySelector('h2');
                  const before = {bodyMargin: style(document.body).margin,
                    headingSize: style(heading).fontSize};
                  const outside = document.createElement('h2');
                  outside.textContent = 'Outside component';
                  document.body.append(outside);
                  const scoped = style(outside).fontSize !== style(heading).fontSize;
                  outside.remove();
                  const adapterSheets = document.adoptedStyleSheets.filter(s => s !== pageStyles);
                  document.adoptedStyleSheets = adapterSheets;
                  const independent = style(document.body).margin === '8px' &&
                    style(heading).fontSize === before.headingSize;
                  document.adoptedStyleSheets = [...adapterSheets, pageStyles];
                  const restored = document.adoptedStyleSheets.length === adapterSheets.length + 1;
                  document.documentElement.style.setProperty('--aui-muted-text', 'rgb(10, 20, 30)');
                  const themeInherited = style(note.querySelector('p')).color === 'rgb(10, 20, 30)';
                  document.documentElement.style.removeProperty('--aui-muted-text');
                  return {before, scoped, independent, restored, themeInherited};
                }""")
                assert outcome["before"] == {"bodyMargin": "0px", "headingSize": "18px"}
                assert all(outcome[key] for key in (
                    "scoped", "independent", "restored", "themeInherited",
                )), outcome
                grid = page.locator(".catalog-content")
                columns = "el => getComputedStyle(el).gridTemplateColumns"
                background = "el => getComputedStyle(el).backgroundColor"
                assert len(grid.evaluate(columns).split()) == 2
                button = page.get_by_role("button", name="Explore reactive example")
                assert button.evaluate(background) == "rgb(36, 86, 166)"
                button.hover()
                assert button.evaluate(background) == "rgb(29, 69, 133)"
                page.mouse.move(0, 0)

                # Native keyboard focus, visible focus feedback, and labelled input.
                page.keyboard.press("Tab")
                assert button.evaluate("el => el === document.activeElement")
                assert button.evaluate("el => getComputedStyle(el).outlineStyle") == "solid"
                assert button.evaluate("el => getComputedStyle(el).outlineWidth") == "2px"
                page.keyboard.press("Tab")
                textbox = page.get_by_role("textbox", name="Your message")
                assert textbox.evaluate("el => el === document.activeElement")
                textbox.fill("A local draft")
                for width in (390, 320):
                    page.set_viewport_size({"width": width, "height": 844})
                    assert len(grid.evaluate(columns).split()) == 1
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    assert textbox.input_value() == "A local draft"

                page.keyboard.press("Shift+Tab")
                page.keyboard.press("Enter")
                page.wait_for_url("**/reactive-shadow.html")
                counter = page.get_by_role("button", name="Increment (0)")
                counter.click()
                assert page.get_by_role("button", name="Increment (1)").is_visible()
                assert not errors, errors
                assert not failed_resources, failed_resources
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
