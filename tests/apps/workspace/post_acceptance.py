"""Actual app receiver/router + isolated Chrome; synthetic agent, ZERO model turns.

The browser is fully closed while two independent posts are saved. App restart and
same-operation retry preserve the original receipt; reopening catches up once.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext, suppress
from pathlib import Path

import uvicorn
import websockets
from browser_acceptance import ROOT, control, conversation, free_port, wait_for_server
from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(ROOT / "src/automata/tools/message-router"))
from automata_router.router import Router, validate_config  # noqa: E402
from automata_router.server import RouterApp  # noqa: E402


class ObservedRouter(Router):
    sources = []

    async def route(self, source, packet):
        self.sources.append(source.identity)
        return await super().route(source, packet)


def bounded_wait(predicate):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.03)
    raise AssertionError("Isolated receiver did not connect")


def run(area: Path):
    runtime = area / "runtime"
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("WORKSPACE_", "PI_", "AUTOMATA_MESSAGE_ROUTER",
                                          "AUTOMATA_AGENT_ROUTER"))}
    environment.update(WORKSPACE_RUNTIME_ROOT=str(runtime), PYTHONPATH=str(ROOT / "src"))
    subprocess.run(["deno", "task", "--config",
                    str(ROOT / "src/automata/apps/workspace/frontend/deno.json"), "build"],
                   env=environment, check=True, cwd=ROOT)
    (runtime / "lib").mkdir()
    shutil.copyfile(ROOT / ".agents/var/apps/workspace/lib/adaptive-ui.js",
                    runtime / "lib/adaptive-ui.js")
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    router_port = sock.getsockname()[1]
    app_port = free_port()
    url = f"http://127.0.0.1:{app_port}"
    ws_url = f"ws://127.0.0.1:{router_port}/ws"
    grants = {"v": 1, "participants": {
        "workspace-app": {"kind": "page", "token": "r" * 32, "allow": []},
        "workspace-page": {"kind": "page", "token": "p" * 32, "allow": ["workspace-agent"]},
        "workspace-agent": {"kind": "agent", "token": "a" * 32, "allow": ["workspace-app"]},
    }}
    router = ObservedRouter(validate_config(grants), public_url=f"http://127.0.0.1:{router_port}")
    router.sources = []
    server = uvicorn.Server(uvicorn.Config(RouterApp(router, origins=(url,)),
                                          log_level="error", lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    for name in ("workspace-app", "workspace-page"):
        endpoint = runtime / f"{name}.json"
        endpoint.write_text(json.dumps({"kind": "page", "participant": name, "wsUrl": ws_url,
                                        "token": grants["participants"][name]["token"]}))
        endpoint.chmod(0o600)
    environment.update(WORKSPACE_PORT=str(app_port), WORKSPACE_AGENT_ID="agent-automata",
                       WORKSPACE_AGENT_PARTICIPANT="workspace-agent",
                       WORKSPACE_PAGE_ENDPOINT=str(runtime / "workspace-page.json"),
                       WORKSPACE_APP_ENDPOINT=str(runtime / "workspace-app.json"))

    def start_app():
        process = subprocess.Popen([sys.executable, "-m", "automata.apps.workspace.server",
                                    "--port", str(app_port)], cwd=ROOT, env=environment,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_for_server(url + "/api/state", process)
        bounded_wait(lambda: "workspace-app" in router.peers)
        return process

    def stop_app(process):
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
            raise AssertionError("Owned test app failed graceful cleanup") from None
        bounded_wait(lambda: "workspace-app" not in router.peers)

    async def post(value):
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({"v": 2, "type": "hello", "participant": "workspace-agent",
                                     "token": "a" * 32, "sessionId": "synthetic-no-model"}))
            assert json.loads(await ws.recv())["type"] == "hello_ack"
            await ws.send(json.dumps({"v": 2, "type": "route", "requestId": "test-request",
                                     "to": "workspace-app", "payload": value}))
            result = None
            for _ in range(2):
                packet = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if packet["type"] == "response":
                    result = packet["payload"]
                else:
                    assert packet["status"] == "forwarded"
            return result

    def send_post(value):
        # Playwright sync owns a running loop on this thread.
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, post(value)).result(timeout=8)

    def envelope(operation, text):
        return {"operationId": operation,
                "context": {"projectId": "project-northstar",
                            "conversationId": "conversation-aster"},
                "content": [{"id": "text", "type": "text", "version": 1,
                             "data": {"text": text}}]}

    process = None
    browser = None
    errors = []
    try:
        process = start_app()
        first = envelope("initial-form", "Initial independently posted form")
        first["content"].append({"id": "form", "type": "form", "version": 1, "data": {
            "fields": [{"name": "title", "kind": "text", "label": "Title", "required": True}]}})
        assert send_post(first)["status"] == "saved"
        with sync_playwright() as playwright:
            launch = {"headless": True, "executable_path": shutil.which("google-chrome"),
                      "args": ["--no-sandbox"], "env": environment}
            browser = playwright.chromium.launch(**launch)
            page = browser.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url + "/project-northstar/", wait_until="networkidle")
            control(page, "#conversation-toggle").click()
            expect(conversation(page, ".message.agent")).to_have_count(1)
            compose = control(page, "wsp-composer textarea")
            compose.fill("Unsent composer survives closed browser")
            field = conversation(page, 'aui-form input[name="title"]')
            field.fill("Unsent form survives closed browser")
            assert send_post(envelope("while-open", "Arrival while form is focused"))[
                "status"] == "saved"
            expect(conversation(page, ".message.agent")).to_have_count(2)
            expect(field).to_be_focused()
            expect(field).to_have_value("Unsent form survives closed browser")
            expect(compose).to_have_value("Unsent composer survives closed browser")
            expect(control(page, ".notice")).to_contain_text("All changes saved")
            browser.close()
            browser = None
            bounded_wait(lambda: "workspace-page" not in router.peers)
            # No browser process/page exists here. App-owned transport is the receiver.
            saved = send_post(envelope("while-closed-1", "Closed browser progress one"))
            second = send_post(envelope("while-closed-2", "Closed browser progress two"))
            assert saved["status"] == second["status"] == "saved"
            assert second["seq"] == saved["seq"] + 1
            stop_app(process)
            process = start_app()
            retry = send_post(envelope("while-closed-1", "Closed browser progress one"))
            assert retry == saved
            assert send_post(envelope("while-closed-1", "Changed payload"))[
                "status"] == "rejected"
            browser = playwright.chromium.launch(**launch)
            page = browser.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url + "/project-northstar/", wait_until="networkidle")
            control(page, "#conversation-toggle").click()
            expect(conversation(page, ".message.agent")).to_have_count(4)
            expect(conversation(page, ".message.agent").nth(2)).to_contain_text(
                "Closed browser progress one")
            expect(conversation(page, ".message.agent").nth(3)).to_contain_text(
                "Closed browser progress two")
            expect(control(page, "wsp-composer textarea")).to_have_value(
                "Unsent composer survives closed browser")
            expect(conversation(page, 'aui-form input[name="title"]')).to_have_value(
                "Unsent form survives closed browser")
            assert set(router.sources) == {"workspace-agent"}, router.sources
            assert not errors, errors
            page.screenshot(path=str(area / "closed-browser-catch-up.png"))
            (area / "result.json").write_text(json.dumps({"status": "passed", "modelTurns": 0,
                "browserFullyClosed": True, "receiver": "actual app-owned Node adapter",
                "router": "actual router, random port, synthetic credentials",
                "retryReceiptUnchanged": retry == saved, "saved": saved, "second": second,
                "agentPostsObservedOnce": 4, "inputReplayCount": 0}, indent=2))
            browser.close()
            browser = None
        print("PASS: actual receiver/router + CLOSED browser + restart/dedup "
              "+ draft/focus catch-up")
    finally:
        if browser:
            with suppress(Exception):
                browser.close()
        try:
            if process and process.poll() is None:
                stop_app(process)
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            sock.close()
        assert not thread.is_alive()


def main():
    retained = os.environ.get("WORKSPACE_TEST_ROOT")
    if retained:
        Path(retained).mkdir(parents=True, exist_ok=False)
    area = (nullcontext(retained) if retained
            else tempfile.TemporaryDirectory(prefix="workspace-post-"))
    with area as root:
        run(Path(root))


if __name__ == "__main__":
    main()
