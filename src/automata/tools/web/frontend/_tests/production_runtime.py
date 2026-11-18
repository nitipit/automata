"""Actual guarded BrowserHost/runtime + built ESM graph, with inert RPC (no native Pi/model).

Run with a web/playwright-enabled interpreter and PYTHONPATH=src. --no-build allows
checking installed wheel assets from outside checkout without Node/source access.
"""

# ruff: noqa: E501 -- embedded browser JavaScript is kept in readable test sequences.
import argparse
import asyncio
import subprocess
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from playwright.async_api import async_playwright

from automata.tools.web.host import BrowserHost


class InertRpc:
    def __init__(self, project):
        self.prompts = 0
        self.session = project / "fixture.jsonl"

    async def start(self, *_args, **_kwargs):
        pass

    async def command(self, kind, **_kwargs):
        if kind == "prompt":
            self.prompts += 1
            raise AssertionError("No prompt is authorized in this fixture")
        if kind == "get_state":
            return {"sessionId": "owned-fixture-session", "sessionFile": str(self.session)}
        if kind == "get_messages":
            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": "# Runtime fixture\n\n```js\nconst identity = true;\n```",
                            }
                        ],
                    }
                ]
            }
        return {}

    async def close(self):
        pass

    async def send(self, _record):
        pass


async def main(no_build=False):
    if not no_build:
        subprocess.run(
            ["npm", "run", "build:web"], cwd=Path(__file__).resolve().parents[6], check=True
        )
    temporary = TemporaryDirectory(prefix="automata-production-browser-")
    project = Path(temporary.name)
    rpc = InertRpc(project)
    host = BrowserHost(rpc_factory=lambda _handler: rpc)
    try:
        await host.start(cwd=project)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                executable_path="/usr/bin/google-chrome", headless=True
            )
            try:
                context = await browser.new_context(
                    user_agent="Automata/1.0", viewport={"width": 1280, "height": 900}
                )
                page = await context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                await page.goto(host.admission_url)
                await page.wait_for_function(
                    "window.awr?.status === 'connected' && document.querySelector('#sessions')?.disabled === false"
                )
                result = await page.evaluate("""async () => {
                  const ui = await import('/assets/ui.js');
                  const again = await import('/assets/ui.js');
                  const tick = async () => { await ui.nextTick(); await new Promise(r=>setTimeout(r,25)); };
                  const checks = {}, app = document.querySelector('automata-app');
                  checks.adapterIdentity = app instanceof ui.Adapter;
                  checks.moduleCache = ui.appTheme === again.appTheme && ui.Base === again.Base;
                  checks.markdownIdentity = document.querySelector('ui-markdown') instanceof ui.Markdown && document.querySelector('ui-codeblock') instanceof ui.CodeBlock;
                  checks.runtimeCulori = ui.culori.wcagContrast('#000','#fff') === 21 && typeof ui.culori.toGamut === 'function';
                  // Arrow1.0.6 pending-watch disposal regression: stop must not let
                  // queued effects re-subscribe null listeners or invoke disposed callbacks.
                  const queuedRef=ui.createTheme(), calls=[0,0,0,0];
                  const stops=calls.map((_,i)=>ui.bindTheme(app,()=>calls[i]++,queuedRef));
                  queuedRef.set({mode:'dark'}); stops[0](); stops[1](); await tick();
                  queuedRef.set({mode:'light'}); await tick();
                  checks.queuedWatcherDisposal=JSON.stringify(calls)==='[1,1,3,3]'; stops[2](); stops[3]();
                  const baseline = ui.themeDiagnostics();
                  class RuntimeProbe extends ui.Base {
                    themedStyle(t) { return `background:${t.roles.surface};border:2px solid ${t.roles.border};`; }
                  }
                  RuntimeProbe.css = 'display:block;padding:4px;'; RuntimeProbe.define('runtime-probe');
                  const outer = document.createElement('section'), other = document.createElement('section');
                  app.append(outer,other);
                  const shadowHost = document.createElement('div'); outer.append(shadowHost);
                  const shadow = shadowHost.attachShadow({mode:'open'});
                  const probe = new RuntimeProbe(), neighbor = new RuntimeProbe();
                  const input = document.createElement('input'); input.value='retained'; probe.append(input); shadow.append(probe); other.append(neighbor);
                  ui.appTheme.set({mode:'light',roles:{surface:'#eeeeee',border:'#123456'}});
                  const local=ui.setTheme(outer,{roles:{surface:'#aabbcc'}}); await tick();
                  const bg = e => getComputedStyle(e).backgroundColor;
                  checks.nearestShadowPartial = bg(probe)==='rgb(170, 187, 204)' && getComputedStyle(probe).borderTopColor==='rgb(18, 52, 86)';
                  checks.instanceIsolation = bg(neighbor)==='rgb(238, 238, 238)' && bg(probe)!==bg(neighbor);
                  input.focus(); let clicks=0; input.addEventListener('click',()=>clicks++);
                  ui.appTheme.set({mode:'dark',accent:'violet',roles:{surface:'#333333',border:'#654321'}}); await tick(); input.click();
                  checks.appThemeSharedWithShell = getComputedStyle(document.querySelector('.chat-panel')).backgroundColor==='rgb(51, 51, 51)' && bg(neighbor)==='rgb(51, 51, 51)';
                  checks.partialPropagates = bg(probe)==='rgb(170, 187, 204)' && getComputedStyle(probe).borderTopColor==='rgb(101, 67, 33)';
                  checks.focusDOMHandlers = shadow.activeElement===input && probe.firstChild===input && input.value==='retained' && clicks===1;
                  local.set({}); await tick(); checks.overrideRemoval=bg(probe)==='rgb(51, 51, 51)';
                  const explicit=ui.createTheme({roles:{surface:'#aaccff'}}); probe.theme=explicit; await tick();
                  checks.explicitReference=bg(probe)==='rgb(170, 204, 255)'; probe.theme=undefined;
                  ui.setTheme(other,{roles:{surface:'#abcdef'}});
                  const sheet=probe._adapter.cssStyleSheet; other.append(probe); await tick();
                  checks.reparent=bg(probe)==='rgb(171, 205, 239)' && !shadow.adoptedStyleSheets.includes(sheet) && document.adoptedStyleSheets.includes(sheet);
                  // Ordinary DOM detach bypasses Element.remove(), exercising disconnectedCallback.
                  probe.parentNode.removeChild(probe); await tick(); checks.detach=!document.adoptedStyleSheets.includes(sheet);
                  shadow.append(probe); await tick(); checks.reconnect=shadow.adoptedStyleSheets.includes(sheet) && bg(probe)==='rgb(51, 51, 51)';
                  ui.setTheme(outer,{mode:'light'}); await tick();
                  checks.modeKeepsInheritedSemanticEscape=probe.theme.value.mode==='light' && probe.theme.value.roles.surface==='#333333';
                  ui.clearTheme(outer); await tick(); checks.clearScope=probe.theme.value.mode==='dark';
                  let rejected=false; try {ui.setTheme(other,{roles:{surface:'var(--not-allowed)'}});}catch{rejected=true;}
                  checks.noCSSVars=rejected && !probe.css.includes('var(');
                  const allSheets=[...document.adoptedStyleSheets,...shadow.adoptedStyleSheets];
                  // The picker fixture uses one layout-only variable; theme colors must remain literal.
                  checks.resolvedLiteralCSS=allSheets.every(s=>[...s.cssRules].every(r=>!r.cssText.replaceAll('var(--preview-pad)', '').includes('var(')));
                  const slotHost=document.createElement('div'); app.append(slotHost);
                  const slotRoot=slotHost.attachShadow({mode:'open'});
                  const slotA=document.createElement('section'),slotB=document.createElement('section');
                  slotA.innerHTML='<slot name="one"></slot>'; slotB.innerHTML='<slot name="two"></slot>'; slotRoot.append(slotA,slotB);
                  ui.setTheme(slotA,{roles:{surface:'#112233'}}); ui.setTheme(slotB,{roles:{surface:'#445566'}});
                  const slotted=new RuntimeProbe(); slotted.slot='one'; slotHost.append(slotted); await tick();
                  const firstSlot=bg(slotted); slotted.slot='two'; await tick();
                  checks.composedSlotRebinding=firstSlot==='rgb(17, 34, 51)'&&bg(slotted)==='rgb(68, 85, 102)';
                  slotted.remove(); slotHost.remove(); ui.clearTheme(slotA); ui.clearTheme(slotB);
                  probe.remove(); neighbor.remove(); outer.remove(); other.remove(); ui.clearTheme(other); ui.appTheme.set({}); await tick();
                  const after=ui.themeDiagnostics(); checks.cleanup=after.bindings===baseline.bindings && after.observedRoots===baseline.observedRoots;
                  const responses=await Promise.all(['/assets/ui.js','/assets/third-party-LICENSES.txt','/assets/package.json','/assets/index.ts','/assets/index.js.map','/assets/build-meta.json','/assets/node_modules/culori/src/index.js'].map(async path=>[path,(await fetch(path)).status]));
                  checks.protectedRoutes=responses.slice(0,2).every(x=>x[1]===200)&&responses.slice(2).every(x=>x[1]===404);
                  return {checks,baseline,after,responses};
                }""")
                assert not errors, f"Browser page errors: {errors}"
                failures = [name for name, passed in result["checks"].items() if not passed]
                assert not failures, f"Production graph checks failed: {failures}; {result}"
                example = (
                    files("automata")
                    .joinpath("skills/automata-web-ui/SKILL.md")
                    .read_text()
                    .split("```js\n", 1)[1]
                    .split("\n```", 1)[0]
                )
                example_ok = await page.evaluate(
                    """async code => {
                  const root=document.createElement('div'); document.querySelector('automata-app').append(root);
                  try {
                    const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
                    const result=await new AsyncFunction('ui',code)({root,blockId:'synthetic-example'});
                    const button=root.querySelector('ui-button'); button.control.click();
                    return result.blockId==='synthetic-example' && root.querySelector('ui-markdown').source.includes('The existing button') && !!root.querySelector('example-accent-note');
                  } finally {root.remove();}
                }""",
                    example,
                )
                assert example_ok, (
                    "Web UI skill example must execute against actual runtime exports"
                )
                result["checks"]["authoringExample"] = example_ok
                assert rpc.prompts == 0
                async with httpx.AsyncClient(headers={"User-Agent": "Automata/1.0"}) as client:
                    for path in (
                        "/assets/ui.js",
                        "/assets/index.js",
                        "/assets/third-party-LICENSES.txt",
                    ):
                        assert (
                            await client.get(
                                host.runtime.origin + path, headers={"Host": "evil.test"}
                            )
                        ).status_code == 403
                print(
                    "PASS guarded production runtime graph (inert RPC/no model):",
                    ", ".join(result["checks"]),
                )
            finally:
                await browser.close()
    finally:
        try:
            await host.close()
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-build", action="store_true")
    asyncio.run(main(parser.parse_args().no_build))
