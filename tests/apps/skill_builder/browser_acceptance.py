"""Real isolated Chrome against an installed-style, prefixed static reference."""
import functools
import http.server
import json
import os
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from automata.install.skills import install_skills

ROOT = Path(__file__).resolve().parents[3]
WEBREF = ROOT / "src/automata/runtimes/pi/skills/automata-message-router/webref"
PAGES = {"index": 2, "configure": 1, "connect": 1, "discover": 1, "send": 3, "failures": 2}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main():
    evidence = Path(os.environ["WEBREF_EVIDENCE"])
    evidence.mkdir(parents=True, exist_ok=False)
    errors, requests, sockets = [], [], []
    with tempfile.TemporaryDirectory(prefix="automata-webref-static-") as temporary:
        public = Path(temporary)
        prefix = "installed/skills/automata-message-router/webref"
        install_skills(
            target_root=public / "installed/skills",
            skill_names=["automata-message-router"],
        )
        handler = functools.partial(QuietHandler, directory=public)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_port}"
        url = f"{origin}/{prefix}/"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    executable_path="/usr/bin/google-chrome", headless=True,
                )
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("request", lambda request: requests.append(
                        (request.method, request.url)
                    ))
                    page.on("websocket", lambda socket: sockets.append(socket.url))
                    for mobile in (False, True):
                        page.set_viewport_size({"width": 390, "height": 844} if mobile
                                               else {"width": 1440, "height": 1000})
                        for slug, count in PAGES.items():
                            page.goto(url + slug + ".html", wait_until="networkidle")
                            expect(page.locator("protocol-diagram svg")).to_have_count(count)
                            expect(page.locator("message-router-page")).to_have_count(1)
                            expect(page.locator("head > style")).to_have_count(0)
                            assert page.evaluate("""() => {
                              const wrapper = document.querySelector('message-router-page');
                              const sheet = wrapper.constructor.adapter.cssStyleSheet;
                              return document.adoptedStyleSheets.includes(sheet)
                                && sheet.cssRules.length > 0
                                && getComputedStyle(wrapper).display === 'block';
                            }""")
                            expect(page.locator("protocol-diagram foreignObject")).to_have_count(0)
                            expect(page.locator('nav a[aria-current="page"]')).to_have_count(1)
                            assert "{%" not in page.content() and "{{" not in page.content()
                            assert page.evaluate(
                                "document.documentElement.scrollWidth <= innerWidth"
                            ), slug
                            mode = "mobile" if mobile else "desktop"
                            if slug == "index":
                                instructions = page.locator('[aria-labelledby="skill-heading"]')
                                instructions.locator("summary").click()
                                expect(instructions).to_contain_text("Connect or reuse")
                                assert "automata-tools:" not in instructions.inner_text()
                                assert "metadata:" not in instructions.inner_text()
                                link = instructions.get_by_role(
                                    "link", name="connection", exact=True,
                                )
                                expect(link).to_have_attribute("href", "./connect.html")
                                instructions.locator("pre").first.focus()
                                expect(instructions.locator("pre").first).to_be_focused()
                                page.screenshot(
                                    path=str(evidence / f"skill-instructions-{mode}.png"),
                                    full_page=True,
                                )
                                instructions.locator("summary").click()
                            page.screenshot(
                                path=str(evidence / f"{slug}-{mode}.png"), full_page=True,
                            )
                            if mobile and slug == "send":
                                stage = page.locator(".diagram-stage").first
                                stage.focus()
                                stage.press("ArrowRight")
                                page.wait_for_timeout(200)
                                assert stage.evaluate("node => node.scrollLeft > 0")
                    page.goto(url + "index.html", wait_until="networkidle")
                    page.keyboard.press("Tab")
                    expect(page.locator(".skip-link")).to_be_focused()
                    page.keyboard.press("Enter")
                    expect(page.locator("#content")).to_be_focused()
                    for theme in ("dark", "light", "system"):
                        page.locator("#theme").select_option(theme)
                        expect(page.locator("#theme")).to_have_value(theme)
                        expect(page.locator("protocol-diagram svg")).to_have_count(2)
                        if theme != "system":
                            expect(page.locator("message-router-page")).to_have_attribute(
                                "data-theme", theme,
                            )
                    page.locator("#theme").select_option("dark")
                    page.get_by_role("link", name="Send", exact=True).first.click()
                    expect(page.locator("#theme")).to_have_value("dark")
                    expect(page.locator("protocol-diagram svg")).to_have_count(3)
                    page.screenshot(path=str(evidence / "send-dark-mobile.png"), full_page=True)
                    assert not errors, errors
                    assert not sockets, sockets
                    assert all(method == "GET" and target.startswith(url)
                               for method, target in requests), requests
                    (evidence / "results.json").write_text(json.dumps({
                        "pages": list(PAGES), "prefix": prefix, "errors": errors,
                        "sockets": sockets, "requests": requests,
                        "checks": ["desktop/mobile", "keyboard skip and diagram scroll",
                                   "local diagrams", "theme persistence", "relative prefix",
                                   "canonical skill body without frontmatter",
                                   "rebased skill links and focusable code",
                                   "Adapter page wrapper, adopted stylesheets, scoped themes"],
                    }, indent=2))
                    print(f"Verified six static pages under /{prefix}/; evidence: {evidence}")
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()
