"""Independent synthetic rendered foundation QA; actual source, disposable Chrome.

Run: .venv/bin/python src/automata/tools/web/frontend/_tests/foundation_rendered.py
"""
import asyncio
import subprocess
import tempfile
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[6]
FRONTEND = ROOT / "src/automata/tools/web/frontend"


async def main():
    with tempfile.TemporaryDirectory(prefix="automata-foundation-qa-") as tmp:
        bundle = Path(tmp) / "foundation.js"
        source = """
import { Base } from './_components/base';
import { appTheme, setTheme, clearTheme, themeDiagnostics } from './_theme/index';
class QaProbe extends Base { themedStyle(t) { return `background:${t.roles.surface};border:2px solid ${t.roles.border};`; } }
QaProbe.css = 'display:block; padding:4px;'; QaProbe.define('qa-probe');
window.qa = { appTheme, setTheme, clearTheme, themeDiagnostics };
"""
        subprocess.run([str(ROOT / "node_modules/.bin/esbuild"), "--bundle", "--format=iife", "--platform=browser", "--target=es2022", f"--outfile={bundle}"], input=source, text=True, check=True, cwd=FRONTEND)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
            try:
                page = await browser.new_page(viewport={"width": 390, "height": 844})
                await page.set_content("<main><div id='a'></div><div id='b'></div></main>")
                await page.add_script_tag(path=str(bundle))
                result = await page.evaluate("""async () => {
                  const tick = () => new Promise(r => setTimeout(r, 30));
                  const {appTheme,setTheme,clearTheme,themeDiagnostics} = window.qa;
                  const baseline = themeDiagnostics();
                  const a = document.querySelector('#a'), b = document.querySelector('#b');
                  appTheme.set({mode:'light', roles:{surface:'#eeeeee', border:'#123456'}});
                  setTheme(a, {roles:{surface:'#aabbcc'}});
                  const host = document.createElement('div'); a.append(host);
                  const shadow = host.attachShadow({mode:'open'});
                  const probe = document.createElement('qa-probe');
                  const input = document.createElement('input'); input.value = 'kept';
                  probe.append(input); shadow.append(probe); await tick();
                  const colors = () => [getComputedStyle(probe).backgroundColor, getComputedStyle(probe).borderTopColor];
                  const eq = (a,b) => JSON.stringify(a) === JSON.stringify(b);
                  const checks = {};
                  checks.shadowPartial = eq(colors(), ['rgb(170, 187, 204)','rgb(18, 52, 86)']);
                  input.focus(); let clicks=0; input.addEventListener('click',()=>clicks++);
                  appTheme.set({mode:'dark', roles:{surface:'#333333',border:'#654321'}}); await tick();
                  input.click();
                  checks.globalPropagates = eq(colors(), ['rgb(170, 187, 204)','rgb(101, 67, 33)']);
                  checks.domFocusHandlers = probe.firstChild === input && shadow.activeElement === input && input.value === 'kept' && clicks === 1;
                  clearTheme(a); await tick();
                  checks.overrideRemoval = eq(colors(), ['rgb(51, 51, 51)','rgb(101, 67, 33)']);
                  setTheme(b,{roles:{surface:'#abcdef'}});
                  const sheet = probe._adapter.cssStyleSheet;
                  b.append(probe); await tick();
                  checks.reparent = colors()[0] === 'rgb(171, 205, 239)' && !shadow.adoptedStyleSheets.includes(sheet) && document.adoptedStyleSheets.includes(sheet);
                  probe.remove(); await tick();
                  checks.detach = !document.adoptedStyleSheets.includes(sheet);
                  shadow.append(probe); await tick();
                  checks.reconnect = shadow.adoptedStyleSheets.includes(sheet) && colors()[0] === 'rgb(51, 51, 51)';
                  probe.remove(); host.remove(); clearTheme(b); appTheme.set({}); await tick();
                  const after = themeDiagnostics();
                  checks.cleanup = after.bindings === baseline.bindings && after.observedRoots === baseline.observedRoots;
                  return {checks, baseline, after};
                }""")
                failures = [name for name, passed in result["checks"].items() if not passed]
                assert not failures, f"rendered foundation failures: {failures}, {result}"
                print("PASS isolated Chromium foundation:", ", ".join(result["checks"]))
            finally:
                await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
