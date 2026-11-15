"""Independent synthetic rendered text QA with disposable Chromium, no model.

Run: .venv/bin/python src/automata/tools/web/frontend/_tests/text_rendered.py
"""
import asyncio
import subprocess
import tempfile
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[6]
FRONTEND = ROOT / "src/automata/tools/web/frontend"


async def main():
    with tempfile.TemporaryDirectory(prefix="automata-text-qa-") as tmp:
        bundle = Path(tmp) / "text.js"
        source = "import './_components/codeblock'; import './_components/markdown';"
        subprocess.run([str(ROOT / "node_modules/.bin/esbuild"), "--bundle", "--format=iife", "--platform=browser", "--target=es2022", f"--outfile={bundle}"], input=source, text=True, check=True, cwd=FRONTEND)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
            try:
                page = await browser.new_page(viewport={"width": 390, "height": 844})
                await page.set_content("<main style='width:300px'><ui-markdown></ui-markdown><ui-codeblock></ui-codeblock></main>")
                await page.add_script_tag(path=str(bundle))
                result = await page.evaluate("""async () => {
                  const md = document.querySelector('ui-markdown'), block = document.querySelector('ui-codeblock');
                  const check = {};
                  md.source = '# Title\\n\\n<script>window.pwned=1</script>\\n\\n[bad](javascript:alert(1)) [safe](https://example.org)';
                  check.markdownSafety = !!md.querySelector('h1') && !md.querySelector('script') && !window.pwned && md.textContent.includes('<script>') && md.querySelectorAll('a').length === 1 && md.querySelector('a').href === 'https://example.org/';
                  const source = '<img src=x onerror=alert(1)>\\n' + 'long-line-'.repeat(50);
                  block.setCode(source, 'unknown');
                  const code = block.querySelector('code'), button = block.querySelector('button');
                  check.plaintext = code.textContent === source && !block.querySelector('img');
                  const pre = block.querySelector('pre');
                  check.scroll = pre.scrollWidth > pre.clientWidth && ['auto','scroll'].includes(getComputedStyle(pre).overflowX);
                  let copied;
                  Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText:async value => { copied=value; }}});
                  button.click(); await new Promise(r => setTimeout(r,0));
                  check.copy = copied === source && block.textContent.includes('Copied');
                  Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText:async () => { throw Error('denied'); }}});
                  button.click(); await new Promise(r => setTimeout(r,0));
                  check.copyFailure = block.textContent.includes('Copy failed') && !button.disabled;
                  block.setCode('const n = 42;', 'javascript');
                  check.highlight = !!block.querySelector('.hljs-keyword') && code.textContent === 'const n = 42;';
                  md.source = '```js\\nconst n =';
                  const fence = md.querySelector('ui-codeblock'), copy = fence.querySelector('button'); copy.focus();
                  md.source += ' 42;\\n'; md.source += '```\\n\\nDone';
                  check.streaming = md.querySelector('ui-codeblock') === fence && fence.querySelector('button') === copy && document.activeElement === copy && fence.source === 'const n = 42;\\n';
                  return check;
                }""")
                failures = [name for name, passed in result.items() if not passed]
                assert not failures, f"rendered text failures: {failures}, {result}"
                print("PASS isolated Chromium rendered text:", ", ".join(result))
            finally:
                await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
