"""Opt-in isolated native/mock-provider proof. Never contacts a real provider.

Parent invocation requires --binary and a NEW --state-root. Child and mock HTTP
server both run inside bubblewrap's private network, with no credentials/home.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import selectors
import subprocess
import sys
import threading
import time
from pathlib import Path


class Client:
    def __init__(self):
        self.process = subprocess.Popen(
            ["/codex", "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=open("/probe/stderr.log", "ab"),
        )
        self.sequence = 0
        self.buffer = b""
        self.events = []
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.request(
            "initialize",
            {
                "clientInfo": {"name": "automata_mock", "version": "1"},
                "capabilities": {"experimentalApi": True},
            },
        )
        self.send({"method": "initialized"})

    def send(self, value):
        self.process.stdin.write(json.dumps(value).encode() + b"\n")
        self.process.stdin.flush()

    def receive(self):
        deadline = time.monotonic() + 30
        while b"\n" not in self.buffer:
            if not self.selector.select(max(0, deadline - time.monotonic())):
                raise TimeoutError("native event")
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError("native exited")
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        value = json.loads(line)
        self.events.append(value)
        return value

    def request(self, method, params):
        self.sequence += 1
        identifier = self.sequence
        self.send({"id": identifier, "method": method, "params": params})
        while True:
            value = self.receive()
            if value.get("id") == identifier:
                if "error" in value:
                    raise RuntimeError(value["error"])
                return value["result"]

    def turn(self, thread_id, text):
        result = self.request(
            "turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": text}]}
        )
        turn_id = result["turn"]["id"]
        while True:
            event = self.receive()
            if event.get("method") == "turn/completed":
                turn = event["params"]["turn"]
                if turn["id"] == turn_id:
                    assert turn["status"] == "completed", turn
                    return

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=5)
        self.selector.close()


class Provider(http.server.BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        Provider.requests.append(json.loads(body))
        sequence = len(Provider.requests)
        item = {
            "type": "message",
            "id": f"msg_{sequence}",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "fixture answer"}],
        }
        response = {
            "id": f"resp_{sequence}",
            "object": "response",
            "status": "completed",
            "output": [item],
            "usage": {
                "input_tokens": 120000,
                "output_tokens": 25,
                "total_tokens": 120025,
                "input_tokens_details": {"cached_tokens": 10000, "cache_write_tokens": 2000},
                "output_tokens_details": {"reasoning_tokens": 5},
            },
        }
        events = [
            {"type": "response.created", "response": {"id": response["id"]}},
            {"type": "response.output_item.added", "output_index": 0, "item": item},
            {"type": "response.output_item.done", "output_index": 0, "item": item},
            {"type": "response.completed", "response": response},
        ]
        payload = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def control(thread, action, *extra):
    command = [
        "python3",
        "/probe/integration/token-awareness/token_awareness.py",
        action,
        "--state-root",
        "/probe/token-state",
        "--transcript",
        thread["path"],
        "--session",
        thread["sessionId"],
        *extra,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    assert not result.stderr
    return json.loads(result.stdout)


def child():
    version = subprocess.check_output(["/codex", "--version"], text=True).strip()
    assert version == "codex-cli 0.159.0", version
    root = Path("/probe")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    config = (
        'model = "gpt-5.1-codex"\nmodel_provider = "fixture"\n'
        'approval_policy = "on-request"\nsandbox_mode = "read-only"\n'
        '[model_providers.fixture]\nname = "Fixture"\nwire_api = "responses"\n'
        f'base_url = "http://127.0.0.1:{server.server_port}/v1"\n'
        "[analytics]\nenabled = false\n[feedback]\nenabled = false\n"
        "[features]\nmemories = false\nweb_search = false\n"
    )
    (root / "codex/config.toml").write_text(config)
    (root / "codex/hooks.json").write_text(
        (root / "integration/token-awareness/hooks.json").read_text()
    )
    first = Client()
    try:
        listing = first.request("hooks/list", {"cwds": ["/probe/project"]})
        (root / "hooks-list.json").write_text(json.dumps(listing, indent=2))
    finally:
        first.close()
    # Explicitly trust only the fixture commands generated above, in isolated HOME.
    for group in listing["data"]:
        for hook in group.get("hooks", []):
            config += f"\n[hooks.state.{json.dumps(hook['key'])}]\n"
            config += f"trusted_hash = {json.dumps(hook['currentHash'])}\n"
    (root / "codex/config.toml").write_text(config)
    client = Client()
    try:
        thread = client.request(
            "thread/start",
            {"cwd": "/probe/project", "model": "gpt-5.1-codex", "experimentalRawEvents": True},
        )["thread"]
        client.turn(thread["id"], "first controlled fixture")
        client.turn(thread["id"], "second controlled fixture")
        client.request("thread/compact/start", {"threadId": thread["id"]})
        while True:
            event = client.receive()
            if event.get("method") == "turn/completed":
                assert event["params"]["turn"]["status"] == "completed", event
                break
        client.turn(thread["id"], "after controlled compaction")
        thread = client.request("thread/read", {"threadId": thread["id"]})["thread"]
        controls = {
            "inspect": control(thread, "inspect"),
            "set": control(thread, "set", "--threshold", "1000000"),
        }
        events = list(client.events)
        client.close()
        client = Client()
        resumed = client.request("thread/resume", {"threadId": thread["id"]})["thread"]
        client.turn(resumed["id"], "after owned process restart")
        controls["resume"] = control(resumed, "inspect")
        forked = client.request("thread/fork", {"threadId": resumed["id"]})["thread"]
        client.turn(forked["id"], "owned fork fixture")
        controls["fork"] = control(forked, "inspect")
        (root / "controls.json").write_text(json.dumps(controls, indent=2))
        (root / "protocol.json").write_text(json.dumps(events + client.events, indent=2))
        (root / "requests.json").write_text(json.dumps(Provider.requests, indent=2))
    finally:
        client.close()
        server.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--state-root", type=Path)
    args = parser.parse_args()
    if args.child:
        child()
        return
    root = args.state_root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    for name in ["home", "codex", "project/.git"]:
        (root / name).mkdir(parents=True)
    (root / "runner.py").write_text(Path(__file__).read_text())
    source = Path(__file__).resolve().parents[4] / "src"
    sys.path.insert(0, str(source))
    from automata.install.codex import install_codex

    install_codex(target_root=root / "integration", state_root=root / "token-state")
    command = [
        "bwrap",
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind",
        "/lib",
        "/lib",
        "--ro-bind",
        "/lib64",
        "/lib64",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--dir",
        "/etc",
        "--dir",
        "/home",
        "--bind",
        str(root),
        "/probe",
        "--bind",
        str(root),
        str(root),
        "--ro-bind",
        str(args.binary.resolve()),
        "/codex",
        "--clearenv",
        "--setenv",
        "PATH",
        "/usr/bin:/bin",
        "--setenv",
        "HOME",
        "/probe/home",
        "--setenv",
        "CODEX_HOME",
        "/probe/codex",
        "--chdir",
        "/probe/project",
        "python3",
        "/probe/runner.py",
        "--child",
    ]
    subprocess.run(command, check=True, timeout=120)


if __name__ == "__main__":
    main()
