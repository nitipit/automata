"""Search and canonical navigation in an isolated real browser."""

import shutil

from playwright.sync_api import expect, sync_playwright

from . import test_browser

site = test_browser.site


def test_catalog_search_and_navigation(site):
    url, _, _, _ = site
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=shutil.which('google-chrome'), headless=True,
            args=['--no-sandbox', '--disable-background-networking', '--no-proxy-server'],
        )
        try:
            page = browser.new_page()
            errors, requests = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append(request.url))
            page.goto(url + '/templates/index.html')
            expect(page).to_have_url(url + '/')
            cards = page.locator('.skill-card:visible')
            expect(cards).to_have_count(38)
            assert url + '/automata-agent-evaluation/' not in requests  # No availability probes.
            search = page.get_by_role('searchbox', name='Search skills')
            search.fill('Automata Agent Evaluation')
            expect(cards).to_have_count(1)
            expect(page.get_by_role('status')).to_have_text('1 skill shown')
            expect(cards.first).to_contain_text('Automata Agent Evaluation')
            search.fill('automata-agent-evaluation')  # Directory name is searchable too.
            expect(cards).to_have_count(1)
            search.fill('subtree')  # Match description, not the title.
            expect(cards).to_have_count(1)
            expect(cards.first).to_contain_text('Automata Team Management')
            page.locator('catalog-page').evaluate('''el => {
              const parent = el.parentNode;
              el.remove(); parent.append(el);
              el.remove(); parent.append(el);
            }''')
            expect(cards).to_have_count(1)
            search.fill('no-match-unique-term')
            expect(cards).to_have_count(0)
            expect(page.get_by_text('No skills match your search.')).to_be_visible()
            expect(page.get_by_role('status')).to_have_text('0 skills shown')
            page.get_by_role('button', name='Clear search').click()
            expect(search).to_be_focused()
            expect(search).to_have_value('')
            expect(cards).to_have_count(38)
            expect(page.get_by_role('button', name='Clear search')).to_be_hidden()
            search.press('Tab')
            first_link = page.get_by_role('link', name='Automata Adaptive UI', exact=True)
            expect(first_link).to_be_focused()
            page.get_by_role('link', name='Automata Agent Evaluation', exact=True).click()
            expect(page).to_have_url(url + '/automata-agent-evaluation/')
            page.locator('nav a[href="/automata-agent-evaluation/references/scoring.html"]').click()
            expect(page).to_have_url(url + '/automata-agent-evaluation/references/scoring.html')
            page.get_by_role('link', name='AUTOMATA · SKILLS').click()
            expect(page).to_have_url(url + '/')
            search.fill('Automata Workplan')
            expect(cards).to_have_count(1)
            page.get_by_role('link', name='Automata Workplan', exact=True).click()
            expect(page).to_have_url(url + '/automata-workplan/')
            page.evaluate('history.back()')
            expect(page).to_have_url(url + '/')
            expect(cards).to_have_count(38)  # A new catalog has no stale search state.
            # Exercise fetch-and-swap when the legacy URL is reached through an internal link.
            page.locator('.brand').evaluate("el => el.href = '/templates/index.html'")
            page.locator('.brand').click()
            expect(page).to_have_url(url + '/')
            expect(cards).to_have_count(38)
            assert errors == []
            no_js = browser.new_context(java_script_enabled=False).new_page()
            no_js.goto(url + '/')
            expect(no_js.locator('.skill-card')).to_have_count(38)
            expect(no_js.get_by_role('link', name='Automata Workplan')).to_have_attribute(
                'href', '/automata-workplan/'
            )
        finally:
            browser.close()
