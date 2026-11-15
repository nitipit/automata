"""Exercise the built frontend against an in-process synthetic browser transport.

Run from the repository root after npm ci: python src/automata/tools/web/frontend/_tests/browser_mock.py
Requires Google Chrome. No model, host server, external network, or human interaction.
"""

import functools
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import socketserver
import subprocess
import tempfile
import threading

TESTS = Path("src/automata/tools/web/frontend/_tests")
SETUP = "<script>" + (TESTS / "mock-setup.js").read_text() + "</script>"
TEST = "<script type='module'>" + (TESTS / "browser-test.js").read_text() + "</script>"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
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
        (root / "index.html").write_text(
            "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'></head><body>"
            + SETUP
            + content
            + "<script src='/bridge.js'></script><script type='module' src='/index.js'></script>"
            + TEST
            + "</body></html>"
        )
        bridge = os.environ.get("AUTOMATA_WEB_BRIDGE_JS")
        if bridge:
            shutil.copyfile(bridge, root / "bridge.js")
        else:
            (root / "bridge.js").write_text("window.awr={status:'connected',connect:async()=>{}};")
        with socketserver.TCPServer(
            ("127.0.0.1", 0), functools.partial(QuietHandler, directory=directory)
        ) as server:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                for size in ("1280,900", "390,844"):
                    url = f"http://127.0.0.1:{server.server_address[1]}/#token=synthetic"
                    result = subprocess.run(
                        [
                            chrome,
                            "--headless",
                            "--no-sandbox",
                            "--disable-gpu",
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
