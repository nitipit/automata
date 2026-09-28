"""Real isolated router + synthetic credentials; no browser or model session."""
import asyncio
import json
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn
import websockets

from automata.apps.workspace.receiver import PostReceiver
from automata.apps.workspace.store import WorkspaceStore


def envelope(operation="operation-1", text="Hello"):
    return {"operationId": operation,
            "context": {"projectId": "project-northstar", "conversationId": "conversation-aster"},
            "content": [{"id": "text", "type": "text", "version": 1, "data": {"text": text}}]}

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/automata/tools/message-router"))
from automata_router.router import Router, validate_config  # noqa: E402
from automata_router.server import RouterApp  # noqa: E402


def wait(predicate):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.03)
    raise AssertionError("Isolated service did not reach expected state")


def test_offline_browser_multiple_posts_restart_receipt_and_page_rejection(tmp_path, monkeypatch):
    monkeypatch.delenv("WORKSPACE_PAGE_ENDPOINT", raising=False)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    config = {"v": 1, "participants": {
        "workspace-app": {"kind": "page", "token": "r" * 32, "allow": []},
        "workspace-agent": {"kind": "agent", "token": "a" * 32, "allow": ["workspace-app"]},
        "synthetic-page": {"kind": "page", "token": "p" * 32, "allow": ["workspace-app"]},
    }}
    router = Router(validate_config(config), public_url=f"http://127.0.0.1:{port}")
    server = uvicorn.Server(uvicorn.Config(RouterApp(router), log_level="error", lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    endpoint = tmp_path / "receiver.json"
    endpoint.write_text(json.dumps({"kind": "page", "participant": "workspace-app",
                                   "token": "r" * 32, "wsUrl": f"ws://127.0.0.1:{port}/ws"}))
    endpoint.chmod(0o600)
    store = WorkspaceStore(tmp_path / "data")
    receiver = PostReceiver(store, endpoint)

    async def post(value, *, page=False):
        async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
            await ws.send(json.dumps({"v": 2, "type": "hello",
                "participant": "synthetic-page" if page else "workspace-agent",
                "token": ("p" if page else "a") * 32,
                **({} if page else {"sessionId": "synthetic-no-model-session"})}))
            assert json.loads(await ws.recv())["type"] == "hello_ack"
            await ws.send(json.dumps({"v": 2, "type": "route", "requestId": "synthetic-request",
                                     "to": "workspace-app", "payload": value, "expectReply": True}))
            receipt = None
            forwarded = False
            for _ in range(2):
                packet = json.loads(await asyncio.wait_for(ws.recv(), 5))
                if packet["type"] == "response":
                    receipt = packet["payload"]
                if packet["type"] == "result":
                    forwarded = packet["status"] == "forwarded"
            assert forwarded
            return receipt

    try:
        wait(lambda: server.started)
        receiver.start()
        wait(lambda: receiver.phase == "connected")
        first = asyncio.run(post(envelope()))
        assert first["status"] == "saved"
        second = asyncio.run(post(envelope("progress-2", "Progress without another input")))
        assert second["seq"] == first["seq"] + 1
        assert asyncio.run(post(envelope(), page=True))["status"] == "rejected"
        receiver.shutdown()
        receiver = PostReceiver(WorkspaceStore(tmp_path / "data"), endpoint)
        receiver.start()
        wait(lambda: receiver.phase == "connected")
        assert asyncio.run(post(envelope())) == first
        assert asyncio.run(post(envelope(text="conflict")))["status"] == "rejected"
        assert len(store.load()["conversations"]["conversation-aster"]["messages"]) == 2
    finally:
        receiver.shutdown()
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
    assert not thread.is_alive()
