"""Exercise the built frontend against an in-process synthetic browser transport.

Run from the repository root after npm ci: python src/automata/tools/web/frontend/_tests/browser_mock.py
Requires Google Chrome. No model, host server, external network, or human interaction.
"""

# ruff: noqa: E501 -- embedded HTML and JavaScript fixtures are kept together.
import functools
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))
from automata.tools.web.connector import inline_execution
from automata.tools.web.runtime_adapter import _memory_bridge_source

TESTS = Path("src/automata/tools/web/frontend/_tests")
SETUP = "<script>" + (TESTS / "mock-setup.js").read_text() + "</script>"
TEST = "<script type='module'>" + (TESTS / "browser-test.js").read_text() + "</script>"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/chat/sessions/browser-fixture/":
            self.path = "/index.html"
        super().do_GET()

    def log_message(self, *args):
        pass


def main():
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        raise RuntimeError("Chrome/Chromium not found")
    template = Path("src/automata/tools/web/frontend/index.html").read_text()
    content = template.split("{% block content %}", 1)[1].split("{% endblock %}", 1)[0]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        subprocess.run(["npm", "run", "build:web", "--", str(root)], check=True)
        for module in ("text-test.js", "controls-test.js", "session-status-test.js"):
            shutil.copyfile(TESTS / module, root / module)
        (root / "index.html").write_text(
            "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'></head><body>"
            + SETUP
            + "<script>window.inlineFixtureCode="
            + json.dumps(inline_execution('ui.root.textContent="wrapper UI"; return {id:ui.blockId};', "fixture-call", "fixture-nonce"))
            + ";window.settlementFixtures="
            + json.dumps({
                "late": inline_execution('setTimeout(() => { try { ui.root; window.lateBlocked=false; } catch { window.lateBlocked=true; } try { window.automataUI.context(ui.toolCallId).root; window.freshBlocked=false; } catch { window.freshBlocked=true; } }, 0); return "scheduled";', "late-call", "nonce-late"),
                "lateerror": inline_execution('setTimeout(() => { try { ui.root; window.lateErrorBlocked=false; } catch { window.lateErrorBlocked=true; } }, 0); throw new Error("private");', "lateerror-call", "nonce-lateerror"),
                "lateserialization": inline_execution('setTimeout(() => { try { ui.root; window.lateSerializationBlocked=false; } catch { window.lateSerializationBlocked=true; } }, 0); return 1n;', "lateserialization-call", "nonce-lateserialization"),
                "existing": inline_execution('const root=ui.root; setTimeout(() => { ui.root.textContent="still live"; window.existingSame=(root===ui.root); }, 0); return 42;', "existing-call", "nonce-existing"),
                "error": inline_execution('ui.root; throw new Error("private");', "error-call", "nonce-error"),
                "serialization": inline_execution('ui.root; return 1n;', "serialization-call", "nonce-serialization"),
                "delayedowner": inline_execution('window.ownerBodyRan=true; ui.root.textContent="delayed owner UI"; return 7;', "delayedowner-call", "nonce-delayedowner", 120),
                "missingowner": inline_execution('window.missingBodyRan=true; ui.root;', "missingowner-call", "nonce-missingowner", 50),
                "historicalowner": inline_execution('window.historicalBodyRan=true; ui.root;', "historic", "nonce-historicalowner", 50),
                "ambiguousowner": inline_execution('window.ambiguousBodyRan=true; ui.root;', "duplicate", "nonce-ambiguousowner", 50),
                "disconnectedowner": inline_execution('window.disconnectedBodyRan=true; ui.root;', "disconnectedowner-call", "nonce-disconnectedowner", 120),
                "stoppedowner": inline_execution('window.stoppedBodyRan=true; ui.root;', "stoppedowner-call", "nonce-stoppedowner", 120),
            })
            + "</script>"
            + content
            + "<script src='/connection-bootstrap.js'></script>"
            + "<script type='module' src='/index.js'></script>"
            + TEST
            + "</body></html>"
        )
        bridge = os.environ.get("AUTOMATA_WEB_BRIDGE_JS")
        if bridge:
            (root / "bridge.js").write_bytes(_memory_bridge_source(Path(bridge).read_bytes()))
        else:
            (root / "bridge.js").write_text(
                "class FixtureBridge {status='idle'; async connect(){this.status='connected';}"
                "close(){this.status='closed';}}; "
                "const ticket=window.__automataBridgeTicket; delete window.__automataBridgeTicket;"
                "if (ticket === 'fixture-ticket') "
                "Object.defineProperty(window,'awr',{value:new FixtureBridge(),configurable:true});"
            )
        with socketserver.TCPServer(
            ("127.0.0.1", 0), functools.partial(QuietHandler, directory=directory)
        ) as server:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                for size in ("1280,900", "390,844"):
                    url = f"http://127.0.0.1:{server.server_address[1]}/chat/sessions/browser-fixture/#admission=synthetic"
                    result = subprocess.run(
                        [
                            chrome,
                            "--headless",
                            "--no-sandbox",
                            "--disable-gpu",
                            f"--user-data-dir={root / ('chrome-' + size)}",
                            f"--window-size={size}",
                            "--virtual-time-budget=3000",
                            "--dump-dom",
                            url,
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=30,
                    )
                    match = re.search(r'<pre id="test-result">(.*?)</pre>', result.stdout)
                    if not match:
                        raise AssertionError(f"{size}: missing result; {result.stderr[-1000:]}")
                    report = json.loads(match.group(1))
                    if not report["pass"]:
                        raise AssertionError(f"{size}: {report['failures']}")
                    print(f"{size}: PASS (synthetic browser transport)")
            finally:
                server.shutdown()


if __name__ == "__main__":
    main()
