"""Real-browser Form update regression; no implicit browser/package download.

Run with cached tooling, e.g.:
AUI_CHROMIUM_EXECUTABLE="$HOME/.cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell" \
  PYTHONPATH=src uv run --offline --no-project --with 'playwright==1.63.0' \
  --with 'shelfdb==3.0.2' --with 'dictify==5.0.2' --with pytest \
  python -m pytest tests/integration/automata/adaptive_ui_browser_test.py -q
When invoked in the regular suite without Playwright/a supplied cached browser, skip.
"""

import functools
import http.server
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

SKILL = (
    Path(__file__).parents[3]
    / "src/automata/skills/operations/automata-adaptive-ui"
)


def test_form_drafts_and_focus_in_light_and_shadow_dom(tmp_path: Path) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    executable = os.environ.get("AUI_CHROMIUM_EXECUTABLE")
    if not executable or not Path(executable).is_file():
        pytest.skip("Set AUI_CHROMIUM_EXECUTABLE to an existing cached Chromium executable")
    if not (shutil.which("deno") and shutil.which("node")):
        pytest.skip("Requires cached Deno and Node for the isolated UI build")

    root = tmp_path / "public"
    result = subprocess.run(
        [sys.executable, str(SKILL / "scripts/build.py"),
         "--source-root", str(SKILL / "lib"), "--runtime-root", str(root)],
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stderr
    (root / "index.html").write_text('<!doctype html><script type="module" src="/test.js"></script>')
    (root / "test.js").write_text('''
      import { Form } from "/lib/adaptive-ui.js";
      Form.define("aui-browser-form");
      window.FormUnderTest = Form;
    ''')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with playwright.sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=executable, headless=True)
            try:
                page = browser.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}/")
                page.wait_for_function("window.FormUnderTest !== undefined")
                outcome = page.evaluate('''() => {
                  const Form = window.FormUnderTest;
                  const text = { name: 'person', kind: 'text', label: 'Person', required: true };
                  const choice = { name: 'team', kind: 'choice', label: 'Team', required: true,
                    choices: [{ value: 'a', label: 'Alpha' }, { value: 'b', label: 'Beta' }] };
                  const results = {};
                  for (const mode of ['light', 'shadow']) {
                    const host = document.createElement('div');
                    document.body.append(host);
                    const parent = mode === 'shadow'
                      ? host.attachShadow({mode: 'open'}) : host;
                    const form = Form.create({data: {title: 'Start', fields: [text, choice]}});
                    parent.append(form);
                    const field = form.querySelector('[name=person]');
                    field.value = 'Alex'; field.focus(); field.setSelectionRange(1, 3);
                    form.querySelector('[value=b]').checked = true;
                    const root = form.getRootNode();
                    const before = root.activeElement === field;
                    form.setAttribute('title', 'New title');
                    const updated = form.querySelector('[name=person]');
                    const compatible = before && root.activeElement === updated &&
                      updated.value === 'Alex' && updated.selectionStart === 1 &&
                      updated.selectionEnd === 3 && form.querySelector('[value=b]').checked;
                    form.querySelector('form').reset();
                    const initialReset = form.querySelector('[name=person]').value === '' &&
                      !form.querySelector('[value=b]').checked;
                    updated.value = 'Alex';
                    form.querySelector('[value=b]').checked = true;
                    form.applyData(Form.validateData({fields: [text, {...choice,
                      choices: [{value:'a', label:'Alpha'}]}]}));
                    const removedChoice = !form.querySelector('[value=a]').checked;
                    form.applyData(Form.validateData({fields: [
                      {...choice, name:'person'}, {...text, name:'team'}]}));
                    const changedKind = form.querySelector('[name=team]').value === '' &&
                      !form.querySelector('[name=person]:checked') &&
                      root.activeElement !== form.querySelector('[name=person]');
                    const replacement = form.querySelector('[name=team]');
                    replacement.value = 'Fresh';
                    form.querySelector('form').reset();
                    results[mode] = {compatible, initialReset, removedChoice, changedKind,
                      reset: replacement.value === ''};
                  }
                  return results;
                }''')
                assert all(all(case.values()) for case in outcome.values()), outcome
                assert not errors, errors
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
