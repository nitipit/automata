"""Focused real Chrome proof of shared views and canonical-source SSE refresh."""

import shutil
import socket
import subprocess
import sys
import time
import urllib.request

import pytest
from playwright.sync_api import expect, sync_playwright

from automata.skills.content import SOURCE

from .browser_assertions import assert_line_numbers


@pytest.fixture
def site(tmp_path, request):
    root = tmp_path / "source"
    shutil.copytree(SOURCE, root, ignore=shutil.ignore_patterns("__pycache__"))
    selection = getattr(request, "param", None)
    if selection is not None:
        for directory in (root / "bundled").iterdir():
            if directory.name not in selection:
                shutil.rmtree(directory)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    command = [sys.executable, "-c", (
        "import sys,uvicorn; from automata.skills.server import create_app; "
        "uvicorn.run(create_app(root=sys.argv[1]), "
        "host='127.0.0.1', port=int(sys.argv[2]))"
    ), str(root), str(port)]
    with (tmp_path / "preview.log").open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=log)
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(url + "/", timeout=.5).close()
                    break
                except OSError:
                    assert process.poll() is None, "Preview exited before readiness"
                    time.sleep(.1)
            else:
                pytest.fail("Preview readiness timeout")
            yield url, root, None, "all"
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def test_catalog_sources_references_and_sse(site):
    url, root, _, _ = site
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=shutil.which("google-chrome"), headless=True,
            args=["--no-sandbox", "--disable-background-networking", "--no-proxy-server"],
        )
        try:
            page = browser.new_page()
            errors, requests = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append(request.url))
            for slug, title in [("message-router", "Automata Message Router"),
                                ("automata-storage", "Automata Storage"),
                                ("plan", "Automata Plan")]:
                page.goto(url + "/")
                assert page.locator(".skill-card").count() == 39
                link = page.get_by_role("link", name=title, exact=True)
                expect(link).to_have_attribute("href", f"/{slug}/")
                link.click()
                expect(page.locator("article h1")).to_have_text("SKILL.md")
                raw = page.locator("article code-example code")
                source_name = slug if slug.startswith("automata-") else f"automata-{slug}"
                source = (root / f"bundled/{source_name}/SKILL.md").read_text()
                expect(raw.locator(".token").first).to_be_attached()
                assert raw.text_content() == source
                assert source.startswith("---\n")
                assert_line_numbers(raw, source)
                if slug == "plan":
                    expect(page.locator("nav a")).to_have_count(1)
            # The page must reload itself: no page.reload/goto after this source edit.
            page.evaluate("window.__beforeSourceEdit = true")
            source = root / "bundled/automata-plan/SKILL.md"
            source.write_text(source.read_text() + "\nSSE-CANONICAL-EDIT-PROOF\n")
            expect(page.locator("article code-example code")).to_contain_text(
                "SSE-CANONICAL-EDIT-PROOF", timeout=15000
            )
            assert page.evaluate("window.__beforeSourceEdit === undefined")
            assert page.locator("article code-example code").text_content() == source.read_text()
            page.goto(url + "/automata-agent-evaluation/references/scoring.html")
            expect(page.locator("article h1")).to_have_count(1)
            expect(page.locator("article")).to_contain_text("scor")
            for slug, diagrams in [("configure", 1), ("connect", 1), ("discover", 1),
                                   ("send", 3), ("failures", 2)]:
                page.goto(url + f"/message-router/references/{slug}.html")
                expect(page.locator("article h1")).to_have_count(1)
                expect(page.locator("protocol-diagram svg")).to_have_count(diagrams, timeout=15000)
            assert errors == []
            assert any("/__skill_builder/events" in request for request in requests)
            assert all(request.startswith(url + "/") for request in requests)
        finally:
            browser.close()
