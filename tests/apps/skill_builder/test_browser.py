"""Real Chrome against the unmodified Engrave CLI and disposable source fixtures."""

import http.client
import os
import shutil
import socket
import time
import urllib.request
from pathlib import Path

import mistune
import pytest
from playwright.sync_api import expect, sync_playwright

from automata.apps.skill_builder.content import SOURCE
from automata.apps.skill_builder.server import preview

from .browser_assertions import (
    FIXTURE_MARKDOWN,
    assert_centered,
    assert_highlighting,
    assert_line_numbers,
    assert_token_contrast,
)


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(params=["single", "all"])
def site(tmp_path, request):
    root = tmp_path / "source"
    shutil.copytree(SOURCE, root, ignore=shutil.ignore_patterns("__pycache__"))
    extra = root / "skills/second"
    extra.mkdir()
    (extra / "SKILL.md").write_text("---\nname: second\n---\n# Second synthetic skill\n")
    (root / "second").mkdir()
    (root / "second/index.html").write_text(
        '{% extends "templates/skill.html" %}{% set skill = "second" %}'
        '{% set title = "Second synthetic skill" %}{% set document = "SKILL.md" %}'
        '{% set navigation = [("", title)] %}'
    )
    (root / "templates/index.html").write_text(
        '{% extends "templates/catalog.html" %}{% set landings = ['
        '{"url":"/message-router/", "title":"Automata Message Router"},'
        '{"url":"/second/", "title":"Second synthetic skill"}] %}'
    )
    landing = root / "skills/message-router/SKILL.md"
    landing.write_text(
        landing.read_text() + '\n```jinja\n{{ literal_jinja }} {% literal_tag %}\n```\n'
        + '\n```html\n<script>window.__snippetExecuted=true</script>\n```\n'
    )
    reference = root / "skills/message-router/references/connect.md"
    reference.write_text(
        reference.read_text() + FIXTURE_MARKDOWN + "\n[Synthetic source link](../SKILL.md)\n"
    )
    number = port()
    url = f"http://127.0.0.1:{number}"
    with preview("message-router" if request.param == "single" else None,
                 request.param == "all", number, root) as (process, output):
        for _ in range(100):
            try:
                urllib.request.urlopen(url + "/message-router/", timeout=.5).close()
                break
            except Exception as error:
                if process.poll() is not None:
                    raise AssertionError("Native CLI exited before readiness") from error
                time.sleep(.1)
        else:
            raise AssertionError("Native CLI readiness timeout")
        yield url, root, output, request.param
    assert process.poll() is not None
    assert not output.exists()


def test_native_http_boundary_and_documented_limits(site):
    url, root, output, mode = site
    connection = http.client.HTTPConnection(url.removeprefix("http://"))

    def get(path, headers=None):
        connection.close()  # Native generic500 can close the previous keep-alive connection.
        connection.request("GET", path, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read().decode()

    try:
        for path in [
            "/", "/index.html", "/server.py", "/templates/base.html",
            "/templates/catalog.html", "/templates/skill.html", "/message-router/_layout.html",
            "/%2e%2e/private.txt", "/templates/../../server.py",
            "/message-router/references/%2e%2e/%2e%2e/server.py",
            "/assets/secret", "/skills/second/SKILL.md" if mode == "single" else "/private.md",
        ]:
            status, _, text = get(path)
            # Engrave3.2.6's excluded-route HTTPException has a set-valued detail;
            # native FastAPI serialization returns generic500, not intended404.
            assert status == 500 and text == "Internal Server Error", (path, status, text)
        assert get('/templates/index.html')[0] == 200
        assert not (root / 'index.html').exists()
        assert not (output / 'index.html').exists()
        if mode == 'single':
            assert get('/second/')[0] == 500
        else:
            assert get('/second/')[0] == 200
        assert get("/skills/message-router/SKILL.md")[2] == (
            root / "skills/message-router/SKILL.md"
        ).read_text()
        # Native local-preview behavior: not the former custom middleware contract.
        status, headers, _ = get("/message-router/", {"Host": "other.invalid",
                                                     "Origin": "https://other.invalid"})
        assert status == 200
        assert not any(key.lower() == "content-security-policy" for key in headers)
        assert get("/docs")[0] == 200
        assert get("/openapi.json")[0] == 200
        (root / "message-router/index.html").write_text("{{ invalid.missing }}")
        status, _, text = get("/message-router/")
        assert status == 500 and "Traceback" in text
    finally:
        connection.close()


def assert_code_text(page, source):
    ast = mistune.create_markdown(renderer="ast")(source.read_text())
    expected = [node["raw"] for node in ast if node["type"] == "block_code"
                and node.get("attrs", {}).get("info") != "mermaid"]
    actual = page.locator("code-example code").all_text_contents()
    assert actual == expected


def test_native_browser_refresh_and_ui(site):
    url, root, output, mode = site
    evidence = (
        Path(os.environ["SKILL_SITE_EVIDENCE"]) if os.environ.get("SKILL_SITE_EVIDENCE") else None
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=shutil.which("google-chrome"), headless=True,
            args=["--no-sandbox", "--disable-background-networking", "--no-proxy-server"],
        )
        try:
            page = browser.new_page(viewport={"width": 1360, "height": 980})
            requests, errors = [], []
            page.on("request", lambda request: requests.append(request.url))
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url + '/templates/index.html', wait_until='domcontentloaded')
            selected = page.get_by_role('link', name='Automata Message Router', exact=True)
            second = page.get_by_role('link', name='Second synthetic skill', exact=True)
            expect(selected).to_have_attribute('href', '/message-router/')
            if mode == 'single':
                expect(second).to_have_attribute('aria-disabled', 'true')
                expect(second).not_to_have_attribute('href', '/second/')
                expect(second.locator('..').get_by_role('status')).to_have_text(
                    'Unavailable in this preview.'
                )
                assert second.evaluate('el => !el.hasAttribute("href") && el.tabIndex === -1')
            else:
                expect(second).to_have_attribute('href', '/second/')
                expect(second).not_to_have_attribute('aria-disabled', 'true')
                second.click()
                expect(page.locator('raw-skill code')).to_contain_text('# Second synthetic skill')
                page.locator('.brand').click()
                expect(selected).to_have_attribute('href', '/message-router/')
            if evidence:
                evidence.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(evidence / f'{mode}-catalog.png'))
            selected.focus()
            page.keyboard.press('Enter')
            expect(page).to_have_url(url + '/message-router/')
            expect(page.locator('article h1')).to_have_text('SKILL.md')
            expect(page.locator('nav').get_by_role('link', name='Automata Message Router',
                                                exact=True)).to_be_visible()
            page.locator('.brand').click()
            expect(page).to_have_url(url + '/templates/index.html')
            page.get_by_role('link', name='Automata Message Router', exact=True).click()
            landing = root / "skills/message-router/SKILL.md"
            raw = page.locator("raw-skill code")
            expect(raw).to_contain_text("{{ literal_jinja }} {% literal_tag %}")
            assert raw.text_content() == landing.read_text()
            assert_line_numbers(raw, landing.read_text())
            expect(raw.locator('.token').first).to_be_attached()
            assert "automata-tools:" in raw.text_content()
            expect(page.locator("protocol-diagram")).to_have_count(0)
            assert page.locator("raw-skill script, raw-skill img").count() == 0
            assert page.evaluate("window.__snippetExecuted === undefined")
            assert_centered(page)
            for theme in ['dark', 'light']:
                page.locator('#theme').select_option(theme)
                assert_token_contrast(page)
                if evidence:
                    evidence.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(evidence / f'{mode}-source-{theme}.png'))
            if evidence:
                evidence.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(evidence / f"{mode}-landing-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert_centered(page)
            raw.locator('..').focus()
            page.keyboard.press('ArrowRight')
            expect(raw.locator('..')).to_be_focused()
            page.wait_for_timeout(150)
            assert raw.locator('..').evaluate('el => el.scrollLeft > 0')
            raw.locator('..').evaluate('el => { el.scrollLeft = 0; el.blur(); }')
            if evidence:
                page.screenshot(path=str(evidence / f"{mode}-landing-mobile.png"), full_page=True)
            page.set_viewport_size({"width": 1360, "height": 980})
            time.sleep(.4)
            landing.write_text(landing.read_text() + "\nLANDING-EDIT-PROOF\n")
            expect(raw).to_contain_text("LANDING-EDIT-PROOF", timeout=15000)
            assert raw.text_content() == landing.read_text()
            assert_line_numbers(raw, landing.read_text())
            assert (output / "skills/message-router/SKILL.md").read_bytes() == landing.read_bytes()
            page.locator("nav").get_by_role("link", name="Connect", exact=True).click()
            expect(page).to_have_url(url + "/message-router/references/connect.html")
            expect(page.locator("protocol-diagram svg")).to_have_count(1, timeout=15000)
            assert_centered(page)
            assert_code_text(page, root / "skills/message-router/references/connect.md")
            expect(page.get_by_role("link", name="Synthetic source link")).to_have_attribute(
                "href", "/message-router/index.html"
            )
            assert page.locator('article a[href$=".md"]').count() == 0
            assert_highlighting(page)
            assert page.locator('protocol-diagram .line-numbers-rows').count() == 0
            page.locator('.brand').click()
            expect(page).to_have_url(url + '/templates/index.html')
            page.go_back()
            expect(page.locator('protocol-diagram svg')).to_have_count(1, timeout=15000)
            inline_backgrounds = []
            for theme in ["dark", "light"]:
                page.locator("#theme").select_option(theme)
                expect(page.locator("skill-page")).to_have_attribute("data-theme", theme)
                assert_token_contrast(page)
                inline_style = page.locator('article :not(pre) > code').first.evaluate(
                    '''el => {
                        const style = getComputedStyle(el);
                        return {background: style.backgroundColor,
                                padding: parseFloat(style.paddingLeft),
                                radius: parseFloat(style.borderRadius)};
                    }'''
                )
                assert inline_style['padding'] > 0 and inline_style['radius'] > 0
                assert inline_style['background'] != 'rgba(0, 0, 0, 0)'
                inline_backgrounds.append(inline_style['background'])
                assert page.locator('code-example pre > code').first.evaluate(
                    'el => parseFloat(getComputedStyle(el).paddingLeft)'
                ) == 0
                expect(page.locator("protocol-diagram svg")).to_have_count(1, timeout=15000)
            assert inline_backgrounds[0] != inline_backgrounds[1]
            reference = root / "skills/message-router/references/connect.md"
            reference.write_text(reference.read_text() + "\nREFERENCE-EDIT-PROOF\n")
            expect(page.locator("article")).to_contain_text("REFERENCE-EDIT-PROOF", timeout=15000)
            rendered = output / "message-router/references/connect.html"
            assert "REFERENCE-EDIT-PROOF" in rendered.read_text()
            expect(page.locator("protocol-diagram svg")).to_have_count(1, timeout=15000)
            assert_highlighting(page)
            page.locator("protocol-diagram").evaluate(
                "el => { const parent = el.parentNode; el.remove(); parent.append(el); }"
            )
            expect(page.locator("protocol-diagram svg")).to_have_count(1, timeout=15000)
            page.locator('pre[tabindex="0"]').first.focus()
            page.keyboard.press("ArrowRight")
            assert page.locator('pre[tabindex="0"]').first.evaluate(
                "el => document.activeElement === el"
            )
            assert page.evaluate("document.adoptedStyleSheets.length") > 0
            assert page.locator("head style").count() == 0
            if evidence:
                page.screenshot(path=str(evidence / f"{mode}-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(url + "/message-router/references/send.html", wait_until="domcontentloaded")
            expect(page.locator("protocol-diagram svg")).to_have_count(3, timeout=15000)
            assert_centered(page)
            assert_code_text(page, root / "skills/message-router/references/send.md")
            page.locator(".diagram-stage").first.focus()
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(200)
            assert page.locator(".diagram-stage").first.evaluate("el => el.scrollLeft > 0")
            if evidence:
                page.screenshot(path=str(evidence / f"{mode}-mobile.png"), full_page=True)
            for slug, count in [("configure", 1), ("discover", 1), ("failures", 2)]:
                page.goto(url + "/message-router/references/" + slug + ".html")
                expect(page.locator("protocol-diagram svg")).to_have_count(count, timeout=15000)
                expect(page.locator("protocol-diagram foreignObject")).to_have_count(0)
                assert page.locator("article h1").count() == 1
                assert_code_text(page, root / f"skills/message-router/references/{slug}.md")
            page.locator(".skip-link").focus()
            page.keyboard.press("Enter")
            expect(page.locator("#content")).to_be_focused()
            raw_url = url + "/skills/message-router/SKILL.md"
            page.route(raw_url, lambda route: route.fulfill(status=404, body="missing"))
            page.goto(url + "/message-router/")
            expect(page.locator("raw-skill [role=status]")).to_have_text(
                "Skill source unavailable. Reload to retry."
            )
            assert page.locator("raw-skill code").text_content() == ""
            page.unroute(raw_url)
            page.reload()
            expect(page.locator("raw-skill code")).to_contain_text("LANDING-EDIT-PROOF")
            page.locator("raw-skill").evaluate(
                "el => { const parent = el.parentNode; el.remove(); parent.append(el); }"
            )
            expect(page.locator("raw-skill code")).to_contain_text("LANDING-EDIT-PROOF")
            assert page.locator("raw-skill code").text_content() == landing.read_text()
            assert_line_numbers(page.locator('raw-skill code'), landing.read_text())
            # Preserve exact nonbreaking spaces too: Prism's encode normalizes them.
            unusual = 'const spaces = "a\u00a0b";\n\t// trailing  \n\n'
            raw.evaluate('''(code, text) => {
              code.className = 'language-javascript'; code.textContent = text;
              code.closest('code-example').highlight();
            }''', unusual)
            assert raw.text_content() == unusual
            assert_line_numbers(raw, unusual)
            # Out-of-order source responses cannot overwrite a newer attachment.
            outcome = page.evaluate('''async () => {
              const original = window.fetch, pending = [];
              window.fetch = () => new Promise(resolve => pending.push(resolve));
              const el = document.querySelector('raw-skill'), parent = el.parentNode;
              try {
                el.remove(); parent.append(el);
                el.remove(); parent.append(el);
                pending[1]({ok:true, text:async () => 'new source\\n'});
                await new Promise(resolve => setTimeout(resolve, 0));
                pending[0]({ok:true, text:async () => 'stale source\\n'});
                await new Promise(resolve => setTimeout(resolve, 0));
                return el.querySelector('code').textContent;
              } finally { window.fetch = original; }
            }''')
            assert outcome == 'new source\n'
            assert_line_numbers(raw, outcome)
            assert page.locator('protocol-diagram .line-numbers-rows').count() == 0
            assert errors == []
            assert all(request.startswith(url + "/") for request in requests), requests
            assert any("/__engrave/watch" in request for request in requests)
            assert not any("/ws" in request or "/api/" in request for request in requests)
        finally:
            browser.close()
