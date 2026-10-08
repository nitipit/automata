"""Owned Chrome, synthetic monitor API, external guide navigation fixture."""

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from browser_fixture import snapshot
from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("ANATOMY_URL", "http://127.0.0.1:8766/").rstrip("/")
EVIDENCE = Path(os.environ["ANATOMY_EVIDENCE"])
GUIDE = "http://127.0.0.1:8788/"


def main():
    assert urlparse(URL).hostname == "127.0.0.1"
    EVIDENCE.mkdir(parents=True, exist_ok=False)
    errors, requests, sockets, results = [], [], [], []
    api_count, outage = 0, False

    def api(route):
        nonlocal api_count
        api_count += 1
        if outage:
            route.fulfill(status=503, json={"detail": "Synthetic outage"})
        elif "timezone=invalid" in route.request.url:
            route.fulfill(status=422, json={"detail": "Invalid timezone"})
        else:
            route.fulfill(json=snapshot(route.request.url))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="/usr/bin/google-chrome", headless=True
        )
        try:
            context = browser.new_context(
                viewport={"width": 1440, "height": 1000}, reduced_motion="reduce"
            )
            context.route("**/api/anatomy*", api)
            # Skill-site rendering has its own native/browser tests. This isolates
            # monitor teardown and URL restoration across the external link.
            context.route(
                GUIDE,
                lambda route: route.fulfill(
                    content_type="text/html", body="<h1>Separate skill site fixture</h1>"
                ),
            )
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append((request.method, request.url)))
            page.on("websocket", lambda socket: sockets.append(socket.url))
            page.goto(URL + "/", wait_until="networkidle")
            expect(page.locator("#status")).to_contain_text("updated")
            page.locator("#auto").uncheck()
            page.locator("#tab-capabilities").click()
            page.locator("#capability-filter").fill("design")
            page.locator("#setup-filter").select_option("installed")
            page.locator(".capability-select").first.click()
            selected = page.locator("#capability-detail h3").inner_text()
            page.locator("#tab-statistics").click()
            page.locator("#timezone").fill("UTC")
            page.locator("#timezone").press("Tab")
            page.locator("#chart-limit").select_option("all")
            page.locator("#skill").select_option("automata-agent-design")
            page.locator("#range").select_option("custom")
            page.locator("#start").fill("2026-09-01")
            page.locator("#end").fill("2026-09-20")
            page.locator("#end").press("Tab")
            page.wait_for_function("document.querySelectorAll('#statistics canvas').length === 2")
            expect(page.locator("#auto")).not_to_be_checked()
            assert "paused=1" in page.url and "tab=statistics" in page.url
            monitor_url = page.url
            page.screenshot(path=str(EVIDENCE / "monitor-desktop.png"), full_page=True)
            page.get_by_role("link", name="Skill catalog", exact=True).click()
            expect(page).to_have_url(GUIDE)
            before = api_count
            page.wait_for_timeout(5600)
            assert api_count == before
            assert page.locator("#dashboard-automata").count() == 0
            page.go_back(wait_until="networkidle")
            expect(page).to_have_url(monitor_url)
            page.go_forward(wait_until="networkidle")
            expect(page).to_have_url(GUIDE)
            page.goto(monitor_url, wait_until="networkidle")
            expect(page.locator("#statistics")).to_be_visible()
            for key, value in {
                "range": "custom",
                "timezone": "UTC",
                "start": "2026-09-01",
                "end": "2026-09-20",
                "chart-limit": "all",
                "skill": "automata-agent-design",
            }.items():
                expect(page.locator("#" + key)).to_have_value(value)
            expect(page.locator("#auto")).not_to_be_checked()
            before = api_count
            page.wait_for_timeout(5600)
            assert api_count == before
            page.locator("#tab-capabilities").click()
            expect(page.locator("#capability-filter")).to_have_value("design")
            expect(page.locator("#setup-filter")).to_have_value("installed")
            expect(page.locator("#capability-detail h3")).to_have_text(selected)
            page.locator("#tab-capabilities").focus()
            page.keyboard.press("End")
            expect(page.locator("#tab-statistics")).to_be_focused()
            page.keyboard.press("Home")
            expect(page.locator("#tab-identity")).to_be_focused()
            results.append(
                "External guide unload stops polling; "
                "history and URL restore filters, dates and pause"
            )
            outage = True
            page.locator("#refresh").click()
            expect(page.locator("#status")).to_contain_text("Synthetic outage")
            expect(page.locator("#identity-body")).to_contain_text("Synthetic identity")
            outage = False
            page.locator("#refresh").click()
            expect(page.locator("#status")).not_to_contain_text("Synthetic outage")
            page.locator("#tab-statistics").click()
            page.locator("#timezone").fill("invalid")
            page.locator("#timezone").press("Tab")
            expect(page.locator("#status")).to_contain_text("Invalid timezone")
            expect(page.locator("#window")).to_contain_text("UTC")
            page.locator("#timezone").fill("UTC")
            page.locator("#timezone").press("Tab")
            expect(page.locator("#status")).not_to_contain_text("Invalid timezone")
            page.locator("#auto").check()
            before = api_count
            page.wait_for_timeout(5600)
            assert api_count > before
            page.locator("#auto").uncheck()
            results.append("5s polling, manual refresh, validation and last-good outage recovery")
            for theme in ["dark", "light", "system"]:
                page.locator("#theme").select_option(theme)
                expect(page.locator("#theme")).to_have_value(theme)
                assert page.locator("#statistics canvas").count() == 2
            page.locator("#theme").select_option("dark")
            page.screenshot(path=str(EVIDENCE / "monitor-dark.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(monitor_url, wait_until="networkidle")
            expect(page.locator("#auto")).not_to_be_checked()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(EVIDENCE / "monitor-mobile.png"), full_page=True)
            assert not errors, errors
            assert not sockets, sockets
            assert all(
                method == "GET" and (url.startswith(URL + "/") or url == GUIDE)
                for method, url in requests
            )
            results.append(
                "Desktop/mobile/themes/keyboard; "
                "no page errors, WebSockets or unauthorized requests"
            )
            (EVIDENCE / "results.json").write_text(
                json.dumps(
                    {
                        "results": results,
                        "errors": errors,
                        "sockets": sockets,
                        "requests": requests,
                        "apiFixtureRequests": api_count,
                    },
                    indent=2,
                )
            )
            print(json.dumps(results, indent=2))
        finally:
            browser.close()


if __name__ == "__main__":
    main()
