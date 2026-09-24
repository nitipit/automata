"""Bounded installed-style checks for the reusable Python browser bridge."""

from __future__ import annotations

import importlib.util
import json
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest


def test_agent_browser_bridge_uv_script_declares_websocket_backend() -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required")
    source = (
        Path(__file__).parents[4]
        / "src"
        / "automata"
        / "tools"
        / "message-router"
        / "agent_browser_bridge.py"
    )
    result = subprocess.run(
        [uv, "run", "--offline", "--no-project", "--script", str(source), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "agent-browser-bridge" in result.stdout


def test_agent_browser_bridge_cli_and_generic_json_round_trip(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required")
    try:
        import websocket  # noqa: F401
    except ImportError:
        pytest.skip("cached websocket-client is required")

    source = Path(__file__).parents[4] / "src" / "automata" / "tools" / "message-router"
    runtime = tmp_path / "runtime"
    (runtime / "lib").mkdir(parents=True)
    (runtime / "lib" / "adaptive-ui.js").write_text("export const Chat = {};", encoding="utf-8")
    (runtime / "sessions" / "chat").mkdir(parents=True)
    (runtime / "sessions" / "chat" / "index.html").write_text(
        "<main>chat</main>\n", encoding="utf-8"
    )
    private = tmp_path / "private"
    private.mkdir()
    (private / "secret.txt").write_text("private\n", encoding="utf-8")
    (runtime / "sessions" / "escape").symlink_to(private, target_is_directory=True)
    endpoint = tmp_path / "private-endpoint" / "endpoint.json"
    command = [
        uv,
        "run",
        "--offline",
        "--no-project",
        "--script",
        str(source / "agent_browser_bridge.py"),
        "serve",
        "--runtime-root",
        str(runtime),
        "--session-id",
        "chat",
        "--endpoint-file",
        str(endpoint),
        "--port",
        "18796",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and not endpoint.exists():
            if process.poll() is not None:
                break
            time.sleep(0.05)
        if not endpoint.exists():
            stdout, stderr = process.communicate(timeout=2)
            raise AssertionError(f"bridge did not publish endpoint: {stdout}\n{stderr}")

        record = json.loads(endpoint.read_text(encoding="utf-8"))
        base = record["publicUrl"]
        deadline = time.monotonic() + 5
        while True:
            try:
                assert urllib.request.urlopen(f"{base}/health", timeout=1).status == 200
                break
            except urllib.error.URLError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)
        assert (
            urllib.request.urlopen(f"{base}/sessions/chat/", timeout=2).read()
            == b"<main>chat</main>\n"
        )
        assert urllib.request.urlopen(f"{base}/assets/client.js", timeout=2).status == 200
        with pytest.raises(urllib.error.HTTPError) as escaped:
            urllib.request.urlopen(f"{base}/sessions/escape/secret.txt", timeout=2)
        assert escaped.value.code == 404
        with pytest.raises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(
                f"{base}/.agents/var/tools/agent-browser-bridge/endpoint.json", timeout=2
            )
        assert missing.value.code == 404

        import websocket

        agent = websocket.create_connection(record["wsUrl"], origin=base, timeout=2)
        browser = None
        try:
            agent.send(
                json.dumps(
                    {
                        "type": "hello",
                        "role": "control",
                        "token": record["controlToken"],
                        "sessionId": "pi-session-1",
                        "deliveryOptions": 1,
                    }
                )
            )
            assert json.loads(agent.recv())["role"] == "control"
            agent.send(json.dumps({"type": "control", "action": "open", "requestId": "open"}))
            opened = json.loads(agent.recv())
            pair = parse_qs(urlsplit(opened["pairingUrl"]).fragment)["pair"][0]

            browser = websocket.create_connection(record["wsUrl"], origin=base, timeout=2)
            browser.send(
                json.dumps({"type": "hello", "role": "browser", "token": pair, "sessionId": "chat"})
            )
            assert json.loads(browser.recv())["type"] == "hello_ack"

            payloads = [
                None,
                False,
                0,
                3.5,
                "",
                [],
                ["ยูนิโค้ด", {"constructor": "data", "__proto__": {"safe": True}}],
                {"text": "hello", "context": {"componentId": "chat-1", "quote": "line\nnext"}},
                {"unicode": "界" * 9000},
            ]
            for index, payload in enumerate(payloads):
                identity = f"message-{index}"
                browser.send(
                    json.dumps(
                        {"v": 1, "id": identity, "kind": "message", "payload": payload},
                        ensure_ascii=False,
                    )
                )
                assert json.loads(browser.recv())["type"] == "receipt"
                event = json.loads(agent.recv())
                assert event["envelope"] == {
                    "v": 1,
                    "id": identity,
                    "kind": "message",
                    "payload": payload,
                }
                reply_payload = payload
                agent.send(
                    json.dumps(
                        {
                            "type": "control",
                            "action": "send",
                            "requestId": f"reply-{index}",
                            "envelope": {
                                "v": 1,
                                "id": f"reply-id-{index}",
                                "kind": "reply",
                                "correlationId": identity,
                                "payload": reply_payload,
                            },
                        },
                        ensure_ascii=False,
                    )
                )
                reply = json.loads(browser.recv())
                assert reply == {
                    "type": "reply",
                    "envelope": {
                        "v": 1,
                        "id": f"reply-id-{index}",
                        "kind": "reply",
                        "correlationId": identity,
                        "payload": reply_payload,
                    },
                }
                assert json.loads(agent.recv())["status"] == "accepted"

            # Context is a separate lane: it is routed while Pi is busy and never
            # occupies the single conversational reply slot.
            agent.send(
                json.dumps(
                    {
                        "type": "control",
                        "action": "state",
                        "requestId": "busy",
                        "payload": {"busy": True},
                    }
                )
            )
            assert json.loads(browser.recv())["type"] == "agent_state"
            assert json.loads(agent.recv())["busy"] is True
            selection = {
                "v": 1,
                "id": "selection",
                "kind": "message",
                "payload": None,
                "delivery": {"role": "context", "deliverAs": "nextTurn", "slot": "selected"},
            }
            browser.send(json.dumps(selection))
            assert json.loads(agent.recv())["envelope"] == selection
            for status in ("buffered", "attached"):
                agent.send(
                    json.dumps(
                        {
                            "type": "control",
                            "action": "context_result",
                            "requestId": status,
                            "id": "selection",
                            "status": status,
                        }
                    )
                )
                assert json.loads(browser.recv())["status"] == status
                assert json.loads(agent.recv())["browserDelivered"] is True
            browser.send(json.dumps(selection))
            assert json.loads(browser.recv())["type"] == "duplicate"
            control = {"v": 1, "id": "inspect", "kind": "context_control", "action": "inspect"}
            browser.send(json.dumps(control))
            assert json.loads(agent.recv())["envelope"] == control
            agent.send(
                json.dumps(
                    {
                        "type": "control",
                        "action": "context_result",
                        "requestId": "inspected",
                        "id": "inspect",
                        "status": "inspected",
                        "details": {"entries": []},
                    }
                )
            )
            assert json.loads(browser.recv())["details"] == {"entries": []}
            assert json.loads(agent.recv())["status"] == "accepted"
            for mode in ("steer", "followUp"):
                browser.send(
                    json.dumps(
                        {
                            "v": 1,
                            "id": mode,
                            "kind": "message",
                            "payload": mode,
                            "delivery": {"role": "user", "deliverAs": mode},
                        }
                    )
                )
                assert json.loads(browser.recv())["type"] == "receipt"
                assert json.loads(agent.recv())["envelope"]["delivery"]["deliverAs"] == mode
                agent.send(
                    json.dumps(
                        {
                            "type": "control",
                            "action": "reject",
                            "requestId": mode,
                            "correlationId": mode,
                        }
                    )
                )
                assert json.loads(browser.recv())["type"] == "rejected"
                assert json.loads(agent.recv())["status"] == "accepted"

            browser.send(
                json.dumps(
                    {"v": 1, "id": "legacy", "kind": "chat.message", "payload": {"text": "old"}}
                )
            )
            assert json.loads(browser.recv())["type"] == "error"
        finally:
            if browser is not None:
                browser.close()
            agent.close()

        # Python WebSocket clients can hide this failure. Exercise the same native
        # Node WebSocket implementation used by Pi: result must precede clean close.
        node = shutil.which("node")
        if node:
            close_probe = subprocess.run(
                [
                    node,
                    "-e",
                    """
const assert = require('node:assert/strict');
const endpoint = JSON.parse(require('node:fs').readFileSync(process.argv[1]));
const ws = new WebSocket(endpoint.wsUrl);
const events = [];
const timeout = setTimeout(() => { console.error('close timed out'); process.exit(1); }, 5000);
ws.onopen = () => ws.send(JSON.stringify({type:'hello',role:'control',
  token:endpoint.controlToken,sessionId:'native-close',deliveryOptions:1}));
ws.onmessage = event => {
  const value = JSON.parse(event.data);
  if (value.type === 'hello_ack') {
    ws.send(JSON.stringify({type:'control',action:'close',requestId:'close'}));
  } else events.push(value);
};
ws.onerror = () => events.push({type:'error'});
ws.onclose = event => {
  clearTimeout(timeout);
  assert.equal(event.code, 1000);
  assert.deepEqual(events, [{type:'result',requestId:'close',status:'closed'}]);
};
""",
                    str(endpoint),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            assert close_probe.returncode == 0, close_probe.stdout + close_probe.stderr
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=5)
        assert not endpoint.exists()


def test_json_validation_bounds_and_lossless_serialization() -> None:
    source = (
        Path(__file__).parents[4] / "src/automata/tools/message-router" / "agent_browser_bridge.py"
    )
    spec = importlib.util.spec_from_file_location("bridge_json_validation", source)
    assert spec and spec.loader
    bridge = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bridge
    # Load without generating bytecode beside maintained source.
    exec(compile(source.read_text(), str(source), "exec"), bridge.__dict__)
    for value in [
        None,
        False,
        True,
        0,
        -1,
        0.25,
        "",
        "\ud800",
        "😀",
        [],
        {"__proto__": None, "constructor": [False]},
    ]:
        assert json.loads(bridge.validate_payload(value)) == value
    assert len(bridge.validate_payload("x" * 32766)) == 32768
    for value in ["x" * 32767, float("inf"), float("nan"), 2**53, 1e20]:
        with pytest.raises(ValueError):
            bridge.validate_payload(value)
    nested = None
    for _ in range(32):
        nested = [nested]
    bridge.validate_payload(nested)
    with pytest.raises(ValueError):
        bridge.validate_payload([nested])
    for raw in [
        '{"payload":NaN}',
        '{"a":1,"a":2}',
        '{"payload":' + "[" * 2000 + "null" + "]" * 2000 + "}",
    ]:
        with pytest.raises(ValueError):
            bridge.parse_frame(raw)
    with pytest.raises(ValueError):
        bridge.validate_message({"v": True, "id": "bad", "kind": "message", "payload": None})
    with pytest.raises(ValueError):
        bridge.validate_message({"v": 1, "id": "absent", "kind": "message"})
    for delivery in (
        {"role": "system", "deliverAs": "immediate"},
        {"role": "user", "deliverAs": "nextTurn"},
        {"role": "user", "deliverAs": "steer", "triggerTurn": False},
        {"role": "context", "deliverAs": "nextTurn", "triggerTurn": True},
        {"role": "context", "deliverAs": "steer", "slot": "bad"},
        {"role": "context", "deliverAs": "nextTurn", "unknown": True},
        {"role": None},
    ):
        with pytest.raises(ValueError):
            bridge.validate_delivery(delivery)
    assert bridge.validate_delivery({}) == {"role": "user", "deliverAs": "immediate"}
    assert bridge.validate_message({"v": 1, "id": "null", "kind": "message", "payload": None}) == (
        "null",
        None,
    )
