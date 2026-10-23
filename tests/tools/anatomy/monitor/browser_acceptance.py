"""Owned Chrome, synthetic aggregate API and real flat Anatomy navigation.

ANATOMY_URL targets an owned prepared server; optional ANATOMY_CDP attaches to an
already-authorized isolated Chrome using a fresh context (never closes that browser).
"""

import json
import os
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from browser_fixture import snapshot
from playwright.sync_api import expect, sync_playwright

from automata.tools.anatomy.content import SKILLS, discover

URL = os.environ.get("ANATOMY_URL", "http://127.0.0.1:8766/").rstrip("/")
EVIDENCE = Path(os.environ["ANATOMY_EVIDENCE"])


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
        cdp = os.environ.get("ANATOMY_CDP")
        browser = (
            playwright.chromium.connect_over_cdp(cdp)
            if cdp
            else playwright.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000}, reduced_motion="reduce"
        )
        context.route("**/api/anatomy*", api)
        try:
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append((request.method, request.url)))
            page.on("websocket", lambda socket: sockets.append(socket.url))
            nav = page.get_by_role("navigation", name="Anatomy", exact=True)
            page.goto(URL + "/?paused=1", wait_until="domcontentloaded")
            expect(page.locator("#status")).to_contain_text("updated")
            expect(nav.locator('[aria-current="page"]')).to_have_text("Overview")
            expect(page.locator("#identity-body")).to_contain_text("Synthetic identity")
            page.screenshot(path=str(EVIDENCE / "overview-desktop.png"), full_page=True)
            outage = True
            page.locator("#refresh").click()
            expect(page.locator("#status")).to_contain_text("Synthetic outage")
            expect(page.locator("#identity-body")).to_contain_text("Synthetic identity")
            outage = False
            page.locator("#refresh").click()
            expect(page.locator("#status")).not_to_contain_text("Synthetic outage")
            results.append("Overview identity/setup summary, manual refresh and last-good recovery")

            nav.get_by_role("link", name="Skills", exact=True).click()
            expect(page.locator('catalog-page[data-ready="true"]')).to_be_attached()
            canonical_count = sum(p.document == "SKILL.md" for p in discover(SKILLS, None, True))
            assert page.locator(".skill-card a.skill-link").count() == canonical_count
            page.locator("#skill-search").fill("workplan")
            expect(page.locator(".skill-card:visible")).to_have_count(1)
            skills_url = page.url
            page.get_by_role("link", name="Automata Workplan", exact=True).click()
            expect(page).to_have_url(URL + "/skills/automata-workplan/")
            expect(nav.locator('[aria-current="page"]')).to_have_text("Skills")
            expect(page.get_by_role("navigation", name="Breadcrumb")).to_contain_text("Skills")
            raw = page.locator("article code-example code")
            expect(raw.locator(".token").first).to_be_attached()
            assert raw.text_content() == (SKILLS / "automata-workplan/SKILL.md").read_text()
            page.go_back()
            expect(page).to_have_url(skills_url)
            expect(page.locator("#skill-search")).to_have_value("workplan")
            expect(page.locator(".skill-card:visible")).to_have_count(1)
            page.go_forward()
            expect(page).to_have_url(URL + "/skills/automata-workplan/")
            nav.get_by_role("link", name="Skills", exact=True).click()
            expect(page).to_have_url(skills_url)
            expect(page.locator(".skill-card:visible")).to_have_count(1)
            page.get_by_role("button", name="Clear search").click()
            page.locator("#setup-filter").select_option("installed")
            for status in page.locator(".skill-card:visible").evaluate_all(
                "cards => cards.map(card => card.dataset.setup)"
            ):
                assert status == "installed"
            page.locator("#setup-filter").select_option("all")
            page.screenshot(path=str(EVIDENCE / "skills-desktop.png"), full_page=True)
            page.goto(URL + "/automata-agent-evaluation/references/scoring.html")
            expect(page.locator("article h1")).to_have_count(1)
            expect(nav.locator('[aria-current="page"]')).to_have_text("Skills")
            assert (
                context.request.get(URL + "/skills/automata-workplan/SKILL.md").body()
                == (SKILLS / "automata-workplan/SKILL.md").read_bytes()
            )
            results.append(
                "Skill source/reference/raw rendering, active section, breadcrumb, "
                "URL search/setup and Back/Forward"
            )

            nav.get_by_role("link", name="Tools", exact=True).click()
            expect(page.locator('#tool-search[data-ready="true"]')).to_be_attached()
            expect(page.locator("#tool-count")).to_contain_text("shown")
            first = page.locator("[data-tool] a").first
            tool_name, tool_href = first.inner_text(), first.get_attribute("href")
            page.locator("#tool-search").fill(tool_name)
            expect(page).to_have_url(URL + "/tools/?query=" + quote_plus(tool_name.lower()))
            tools_url = page.url
            page.locator(f'a[href="{tool_href}"]').click()
            expect(page.get_by_role("navigation", name="Breadcrumb")).to_contain_text(tool_name)
            expect(nav.locator('[aria-current="page"]')).to_have_text("Tools")
            expect(page.locator("#content")).to_contain_text("Runtime readiness: not checked")
            nav.get_by_role("link", name="Tools", exact=True).click()
            expect(page).to_have_url(tools_url)
            expect(page.locator("#tool-search")).to_have_value(tool_name)
            page.go_back()
            expect(page).to_have_url(URL + tool_href)
            page.go_forward()
            expect(page).to_have_url(tools_url)
            page.locator("#tool-search").fill("no-match-unique-term")
            expect(page.locator("#tools-empty")).to_be_visible()
            page.locator("#tool-search").fill("")
            page.screenshot(path=str(EVIDENCE / "tools-desktop.png"), full_page=True)
            before = api_count
            page.wait_for_timeout(5600)
            assert api_count == before
            results.append(
                "Tool inventory/detail identity, provenance, breadcrumb, "
                "search/history and no monitor polling"
            )

            page.goto(URL + "/activity/?range=7d&timezone=UTC&paused=1")
            expect(page.locator("#status")).to_contain_text("updated")
            expect(nav.locator('[aria-current="page"]')).to_have_text("Activity")
            page.locator("#chart-limit").select_option("all")
            page.locator("#skill").select_option("automata-agent-design")
            page.locator("#range").select_option("custom")
            page.locator("#start").fill("2026-09-01")
            page.locator("#end").fill("2026-09-20")
            page.locator("#end").press("Tab")
            page.wait_for_function(
                "() => document.querySelectorAll('#statistics canvas').length === 2"
            )
            activity_url = page.url
            expect(page.locator("#auto")).not_to_be_checked()
            page.locator("#theme").select_option("dark")
            nav.get_by_role("link", name="Tools", exact=True).click()
            expect(page.locator("#theme")).to_have_value("dark")
            page.locator("#theme").select_option("light")
            nav.get_by_role("link", name="Activity", exact=True).click()
            expect(page).to_have_url(activity_url)
            expect(page.locator("#theme")).to_have_value("light")
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
            for theme in ["dark", "light", "system"]:
                page.locator("#theme").select_option(theme)
                expect(page.locator("#theme")).to_have_value(theme)
                assert page.locator("#statistics canvas").count() == 2
            page.screenshot(path=str(EVIDENCE / "activity-desktop.png"), full_page=True)
            results.append(
                "Activity dates/timezone/skill/limit, charts, remembered pause, "
                "5s polling and validation recovery"
            )

            # Resize the loaded charts without navigation: a fresh mobile load
            # does not expose an intrinsic grid track retaining a desktop canvas.
            chart_library = page.evaluate_handle("() => import('/lib/echarts.js')")
            for width in (790, 390, 1440):
                page.set_viewport_size({"width": width, "height": 1000})
                page.wait_for_function("""library => {
                  const charts = [...document.querySelectorAll(
                    'skill-loads-chart, skill-timeline-chart')];
                  if (charts.length !== 2) return false;
                  return charts.every(chart => {
                    const canvas = chart.querySelector('canvas');
                    const instance = library.getInstanceByDom(chart);
                    if (!canvas || !instance || Math.abs(
                      canvas.getBoundingClientRect().width - chart.clientWidth) > 2)
                      return false;
                    if (chart.localName === 'skill-loads-chart' &&
                        instance.getOption().yAxis[0].axisLabel.width !==
                          (chart.clientWidth < 600 ? 125 : 270)) return false;
                    return true;
                  }) && document.documentElement.scrollWidth <= innerWidth;
                }""", arg=chart_library)
                page.screenshot(path=str(EVIDENCE / f"activity-resized-{width}.png"))
            chart_library.dispose()
            results.append("Loaded Activity charts shrink/grow without overflow; labels adapt")

            for source, destination in [
                ("/automata/index.html?tab=identity", "/"),
                ("/automata/index.html?tab=capabilities", "/skills/"),
                ("/automata/index.html?tab=statistics", "/activity/"),
                ("/automata-workplan/", "/skills/automata-workplan/"),
            ]:
                page.goto(URL + source)
                assert urlparse(page.url).path == destination
            for path in [
                "/skills/not-found/",
                "/tools/not-found/",
                "/templates/base.html",
                "/api/state",
            ]:
                assert context.request.get(URL + path).status == 404
            page.set_viewport_size({"width": 390, "height": 844})
            for label, path in [
                ("Overview", "/?paused=1"),
                ("Skills", "/skills/"),
                ("Tools", "/tools/"),
                ("Activity", "/activity/?paused=1"),
                ("Skills", "/skills/automata-workplan/"),
                ("Tools", tool_href),
            ]:
                page.goto(URL + path)
                expect(nav.locator('[aria-current="page"]')).to_have_text(label)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), path
                for link in nav.get_by_role("link").all():
                    expect(link).to_be_visible()
                slug = path.split("?")[0].strip("/").replace("/", "-") or "overview"
                page.screenshot(path=str(EVIDENCE / f"mobile-{slug}.png"))
            results.append(
                "Direct approved pages, legacy destinations, not-found/private boundaries, "
                "narrow-screen wrapping and shared theme"
            )
            assert not errors, errors
            assert not sockets, sockets
            assert all(method == "GET" and url.startswith(URL + "/") for method, url in requests)
            (EVIDENCE / "results.json").write_text(
                json.dumps(
                    {
                        "results": results,
                        "errors": errors,
                        "sockets": sockets,
                        "requests": requests,
                        "apiFixtureRequests": api_count,
                        "browser": "authorized isolated CDP fresh context"
                        if cdp
                        else "owned headless Chrome",
                        "limitations": (
                            "Aggregate responses synthetic; real routing/catalog/inventory/assets. "
                            "Not runtime-readiness proof."
                        ),
                    },
                    indent=2,
                )
            )
            print(json.dumps(results, indent=2))
        finally:
            context.close()
            if not cdp:
                browser.close()


if __name__ == "__main__":
    main()
