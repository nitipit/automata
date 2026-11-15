"""Synthetic isolated browser shell theme and native-dialog lifecycle test.

Run: .venv/bin/python src/automata/tools/web/frontend/_tests/shell_theme.py
"""
import asyncio
import subprocess
import tempfile
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[6]
FRONTEND = ROOT / "src/automata/tools/web/frontend"


async def main():
    with tempfile.TemporaryDirectory(prefix="automata-shell-theme-") as tmp:
        bundle = Path(tmp) / "shell.js"
        source = """import './_components/status-badge'; import './_components/native-dialog';
import {appTheme,setTheme,clearTheme,themeDiagnostics} from './_theme/index';
window.qa={appTheme,setTheme,clearTheme,themeDiagnostics};"""
        subprocess.run([str(ROOT / "node_modules/.bin/esbuild"), "--bundle", "--format=iife", "--platform=browser", "--target=es2022", f"--outfile={bundle}"], input=source, text=True, check=True, cwd=FRONTEND)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
            try:
                page = await browser.new_page(viewport={"width": 390, "height": 844})
                await page.set_content("<main></main>")
                await page.add_script_tag(path=str(bundle))
                result = await page.evaluate("""async () => {
                  const {appTheme,setTheme,clearTheme,themeDiagnostics} = window.qa;
                  const tick = () => new Promise(r => setTimeout(r,30));
                  const baseline = themeDiagnostics();
                  const mount=document.querySelector('main');
                  const badge=document.createElement('status-badge'); badge.textContent='Error'; badge.dataset.state='error';
                  const dialog=document.createElement('native-rpc-dialog'); mount.append(badge, dialog); await tick();
                  appTheme.set({mode:'light',roles:{errorSurface:'#ffdddd',errorBorder:'#aa0000',surface:'#eeeeee',text:'#111111',accent:'#005500'}}); await tick();
                  const checks={};
                  checks.badgeLight=getComputedStyle(badge).backgroundColor==='rgb(255, 221, 221)' && getComputedStyle(badge).borderTopColor==='rgb(170, 0, 0)';
                  let stops=0; dialog.addEventListener('stop-request',()=>stops++);
                  const result=dialog.ask({kind:'input',title:'Name',value:'initial'});
                  const native=dialog.querySelector('dialog'), input=dialog.querySelector('input'), stop=[...dialog.querySelectorAll('button')].find(x=>x.textContent==='Stop');
                  input.value='edited'; input.focus();
                  appTheme.set({mode:'dark',roles:{errorSurface:'#440000',errorBorder:'#ff8888',surface:'#222222',text:'#eeeeee',accent:'#00aa00'}}); await tick();
                  checks.badgeDark=getComputedStyle(badge).backgroundColor==='rgb(68, 0, 0)' && getComputedStyle(badge).borderTopColor==='rgb(255, 136, 136)';
                  checks.dialogTheme=getComputedStyle(native).backgroundColor==='rgb(34, 34, 34)' && getComputedStyle(input).color==='rgb(238, 238, 238)';
                  checks.stable=native.open && dialog.querySelector('input')===input && document.activeElement===input && input.value==='edited';
                  stop.click(); checks.stop=stops===1 && stop.disabled;
                  dialog.querySelector('button[type=submit]').click();
                  checks.submit=(await result)==='edited';
                  const cancelled=dialog.ask({kind:'confirm',title:'Confirm'}); dialog.cancel(); checks.cancel=(await cancelled)===undefined;
                  const empty=dialog.ask({kind:'select',title:'Select',options:[]}); checks.emptyDisabled=dialog.querySelector('button[type=submit]').disabled; dialog.cancel(); await empty;
                  const waiting=dialog.ask({kind:'confirm',title:'Disconnect'}); dialog.remove(); checks.detachCancel=(await waiting)===undefined;
                  const shadowHost=document.createElement('div'); mount.append(shadowHost); const shadow=shadowHost.attachShadow({mode:'open'});
                  shadow.append(dialog); setTheme(shadowHost,{roles:{surface:'#abcdef',errorSurface:'#123456'}}); shadow.append(badge); await tick();
                  const reconnect=dialog.ask({kind:'confirm',title:'Reconnect'}); await tick();
                  checks.shadow=getComputedStyle(dialog.querySelector('dialog')).backgroundColor==='rgb(171, 205, 239)' && getComputedStyle(badge).backgroundColor==='rgb(18, 52, 86)';
                  dialog.cancel(); await reconnect; dialog.remove(); badge.remove(); shadowHost.remove(); clearTheme(shadowHost); appTheme.set({}); await tick();
                  const after=themeDiagnostics(); checks.cleanup=baseline.bindings===after.bindings && baseline.observedRoots===after.observedRoots;
                  return checks;
                }""")
                failures = [name for name, passed in result.items() if not passed]
                assert not failures, f"shell theme failures: {failures}, {result}"
                print("PASS isolated Chromium shell theme:", ", ".join(result))
            finally:
                await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
