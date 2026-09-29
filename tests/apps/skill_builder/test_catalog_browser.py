"""Bounded catalog checks against direct source previews and network failures."""

import shutil

from playwright.sync_api import expect, sync_playwright

# Reuse the disposable two-skill fixture, not the user preview.
from . import test_browser

site = test_browser.site


def test_catalog_checks_are_local_bounded_and_disconnect_safe(site):
    url, _, _, _ = site
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=shutil.which('google-chrome'), headless=True,
            args=['--no-sandbox', '--disable-background-networking', '--no-proxy-server'],
        )
        try:
            page = browser.new_page()
            requests = []
            page.on('request', lambda request: requests.append(request.url))
            # Non-OK, network failure and redirects all get the same truthful status.
            for failure in ['http', 'network', 'redirect', 'timeout']:
                def fail(route, *, failure=failure):
                    if failure == 'timeout':
                        return  # Deliberately leave this request unanswered.
                    if failure == 'network':
                        route.abort()
                    elif failure == 'redirect':
                        route.fulfill(status=302, headers={'Location': 'https://outside.invalid/'})
                    else:
                        route.fulfill(status=503, body='unavailable')

                page.route(url + '/plan/', fail)
                start = len(requests)
                page.goto(url + '/templates/index.html')
                selected = page.get_by_role('link', name='Automata Message Router', exact=True)
                second = page.get_by_role('link', name='Automata Plan', exact=True)
                expect(selected).to_have_attribute('href', '/message-router/')
                expect(second.locator('..').get_by_role('status')).to_have_text(
                    'Unavailable', timeout=7000
                )
                assert second.evaluate('el => !el.hasAttribute("href") && el.tabIndex === -1')
                expect(second).to_have_attribute('aria-disabled', 'true')
                assert 'Unavailable' in second.locator('..').aria_snapshot()
                page.wait_for_timeout(150)
                checks = requests[start:]
                assert checks.count(url + '/message-router/') == 1
                assert checks.count(url + '/plan/') == 1
                assert all(request.startswith(url + '/') for request in checks)
                page.unroute(url + '/plan/')

            # Malformed/external maintained targets fail closed without fetching.
            for target in ['https://outside.invalid/', 'http://[invalid']:
                start = len(requests)
                page.locator('catalog-page').evaluate('''(el, target) => {
                  el.querySelectorAll('[data-catalog-href]')[1].dataset.catalogHref = target;
                  const parent = el.parentNode; el.remove(); parent.append(el);
                }''', target)
                expect(second.locator('..').get_by_role('status')).to_have_text(
                    'Unavailable'
                )
                expect(selected).to_have_attribute('href', '/message-router/')
                assert requests[start:] == [url + '/message-router/']

            # Force two connection generations and resolve old requests last.
            outcome = page.evaluate('''async () => {
              const original = fetch, pending = [];
              window.fetch = (url, options) => new Promise(resolve => {
                pending.push({resolve, signal: options.signal});
              });
              const el = document.querySelector('catalog-page'), parent = el.parentNode;
              el.querySelectorAll('[data-catalog-href]')[1].dataset.catalogHref = '/plan/';
              try {
                el.remove(); parent.append(el);
                el.remove(); parent.append(el);
                const aborted = pending.slice(0, 2).every(item => item.signal.aborted);
                for (const item of pending.slice(2)) item.resolve(new Response('', {status:503}));
                await new Promise(resolve => setTimeout(resolve, 0));
                for (const item of pending.slice(0, 2)) {
                  item.resolve(new Response('', {status:200}));
                }
                await new Promise(resolve => setTimeout(resolve, 0));
                return {aborted, count:pending.length,
                  disabled:[...el.querySelectorAll('[data-catalog-href]')]
                    .every(link => !link.hasAttribute('href') && link.ariaDisabled === 'true'),
                  statuses:[...el.querySelectorAll('[role=status]')].map(node => node.textContent)};
              } finally { window.fetch = original; }
            }''')
            assert outcome == {
                'aborted': True, 'count': 4, 'disabled': True,
                'statuses': ['Unavailable'] * 2,
            }
        finally:
            browser.close()
