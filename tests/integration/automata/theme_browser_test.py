"""One bounded real-Chrome small Theme smoke; reuse task-owned build/server setup."""

import importlib.util
import json
from pathlib import Path

REFERENCE = json.loads((Path(__file__).parents[3] /
    "src/automata/skills/bundled/automata-adaptive-ui/lib/src/ui/_tokens/primitives/color.reference.json").read_text())

def rgb(key):
    hex_value = REFERENCE["entries"][key]["hex"]
    return "rgb(" + ", ".join(str(int(hex_value[i:i + 2], 16)) for i in (1, 3, 5)) + ")"

# Explicit sibling loading also works under pytest's importlib collection mode.
spec = importlib.util.spec_from_file_location(
    "ui_foundation_browser_fixture", Path(__file__).with_name("ui_foundation_browser_test.py"),
)
assert spec and spec.loader
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
foundation_browser = setup.foundation_browser


def test_small_theme_scoping_state_and_typography(foundation_browser):
    browser, url = foundation_browser
    page = browser.new_page(viewport={"width": 900, "height": 800})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(url + "/design/components/")
        page.wait_for_function("customElements.get('ui-theme') !== undefined")
        assert not errors, errors
        initial = page.evaluate(r"""() => {
          const theme = document.querySelector('#application-theme');
          const card = document.querySelector('#theme-card-probe');
          const button = document.querySelector('#primary-button');
          const input = document.querySelector('#theme-input');
          const outside = document.createElement('ui-button');
          outside.setAttribute('label','Outside scope'); document.body.append(outside);
          input.value = 'Local draft'; input.focus(); input.setSelectionRange(1,4);
          const sheet = document.adoptedStyleSheets.find(s => [...s.cssRules].some(r =>
            r.selectorText?.startsWith('[data-aui-theme-scope=')));
          const text = () => [...sheet.cssRules].map(r => r.cssText).join('\n');
          window.probe = {theme, card, button, native:button.querySelector('button'), input,
            outside, sheet, lightText:text(), sheetCount:document.adoptedStyleSheets.length};
          return {outside:getComputedStyle(outside.querySelector('button')).backgroundColor,
            concrete:!text().includes('var(') && !/--[a-z-]+\s*:/.test(text())};
        }""")
        assert initial == {"outside": rgb("blue.4"), "concrete": True}
        observations = []
        for expected_mode in ("light", "dark", "light"):
            if expected_mode != "light" or observations:
                page.evaluate("document.querySelector('#theme-toggle button').click()")
            observed = page.evaluate("""() => {
              const p = window.probe;
              const style = e => getComputedStyle(e);
              return {mode:p.theme.mode, page:style(p.theme).backgroundColor,
                button:style(p.native).backgroundColor, buttonText:style(p.native).color,
                card:style(p.card).backgroundColor, cardText:style(p.card).color,
                outside:style(p.outside.querySelector('button')).backgroundColor,
                sameNodes:p.theme===document.querySelector('#application-theme') &&
                  p.card===document.querySelector('#theme-card-probe') &&
                  p.native===document.querySelector('#primary-button button') &&
                  p.input===document.querySelector('#theme-input'),
                state:p.input.value==='Local draft' && p.input.selectionStart===1 &&
                  p.input.selectionEnd===4 && document.activeElement===p.input,
                sameSheet:document.adoptedStyleSheets.includes(p.sheet) &&
                  document.adoptedStyleSheets.length===p.sheetCount,
                concrete:![...p.sheet.cssRules].some(r => r.cssText.includes('var('))};
            }""")
            assert observed["mode"] == expected_mode
            assert all(observed[key] for key in ("sameNodes", "state", "sameSheet", "concrete")), observed
            assert observed["outside"] == initial["outside"]
            if expected_mode == "light":
                assert [observed[k] for k in ("page", "button", "buttonText", "card", "cardText")] == [
                    rgb("light.2"), rgb("blue.4"), rgb("light.1"), rgb("light.1"), rgb("dark.4")]
            else:
                assert [observed[k] for k in ("page", "button", "buttonText", "card", "cardText")] == [
                    rgb("dark.4"), rgb("blue.1"), rgb("dark.4"), rgb("dark.3"), rgb("light.2")]
            observations.append(observed)
        for width, body, heading in ((400, 16, 28), (600, 16, 28),
                                     (900, 17, 34), (1200, 18, 40), (1400, 18, 40)):
            page.set_viewport_size({"width": width, "height": 800})
            actual = page.evaluate("""() => [
              parseFloat(getComputedStyle(document.querySelector('ui-theme')).fontSize),
              parseFloat(getComputedStyle(document.querySelector('.shell > h1')).fontSize)]""")
            assert abs(actual[0] - body) < .01 and abs(actual[1] - heading) < .01, (width, actual)
        page.goto(url + "/design/tokens/")
        page.wait_for_selector("#theme-tokens .theme-resolved")
        assert page.locator("#palette-source").get_attribute("href") == REFERENCE["source"]
        rows = page.locator("#palette-tokens .token-row").evaluate_all("""rows => rows.map(row => ({
          key:row.dataset.palette, name:row.querySelector('strong').textContent,
          hex:row.querySelector('code').textContent,
          resolved:getComputedStyle(row.querySelector('.swatch')).backgroundColor,
          visible:row.getClientRects().length>0 && !row.closest('details:not([open])')
        }))""")
        assert len(rows) == 45 and {r['key'] for r in rows} == set(REFERENCE['entries'])
        for row in rows:
            expected = REFERENCE['entries'][row['key']]
            assert row['visible'] and row['hex'] == expected['hex']
            assert row['name'] == expected['name'] + ' · ' + row['key']
            assert row['resolved'] == rgb(row['key'])
        assert page.locator('#palette-tokens').evaluate("e => e.getBoundingClientRect().bottom") < page.locator('#theme-tokens').evaluate("e => e.getBoundingClientRect().top")
        action = page.locator('#theme-tokens [data-theme-role="action"]')
        assert "Palette blue.4 → Theme.action" in action.inner_text()
        assert action.locator(".theme-resolved").inner_text() == "Resolved: " + rgb("blue.4")
        page.get_by_role("button", name="Use dark theme", exact=True).click()
        assert action.locator(".theme-resolved").inner_text() == "Resolved: " + rgb("blue.1")
        assert "Palette blue.1 → Theme.action" in action.inner_text()
        page.get_by_role("button", name="Use light theme", exact=True).click()
        assert action.locator(".theme-resolved").inner_text() == "Resolved: " + rgb("blue.4")
        assert not errors, errors
    finally:
        page.close()
