"""Offline host/transport tests; no model call and no simulated human proof."""

import asyncio
import json
import sys

import pytest

pytest.importorskip("automata_web_runtime")
httpx = pytest.importorskip("httpx")

from automata.tools.web.connector import BrowserConnector, ConnectorError  # noqa: E402
from automata.tools.web.host import BrowserHost  # noqa: E402
from automata.tools.web.rpc import PiRpc, RpcError  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class FakeSession:
    is_connected = True

    def __init__(self):
        self.handlers = {}

    def set_handler(self, name, handler):
        self.handlers[name] = handler

    def remove_handler(self, name):
        self.handlers.pop(name, None)

    async def execute(self, code, *, timeout):
        if code == "timeout":
            raise TimeoutError
        return {"code": code}


class FakeRpc:
    def __init__(self):
        self.commands = []
        self.sent = []
        self.closed = False

    async def command(self, kind, **data):
        self.commands.append((kind, data))
        if kind == "prompt":
            return {"disposition": "started"}
        return {}

    async def send(self, record):
        self.sent.append(record)

    async def close(self):
        self.closed = True


def test_connector_registration_correlation_duplicate_names_and_unsubscribe():
    async def check():
        bridge = BrowserConnector()
        session = FakeSession()
        bridge.bind(session)
        first = bridge.subscribe({"name": "choice", "correlationId": "a"})["subscriptionId"]
        second = bridge.subscribe({"name": "choice", "correlationId": "b"})["subscriptionId"]
        session.handlers["choice"]({"correlationId": "wrong"})
        assert bridge.subscriptions[first].queue.empty()
        session.handlers["choice"]({"correlationId": "a", "value": "accepted"})
        assert (await bridge.wait({"subscriptionId": first}))["event"]["value"] == "accepted"
        bridge.unsubscribe({"subscriptionId": first})
        assert "choice" in session.handlers
        waiting = asyncio.create_task(bridge.wait({"subscriptionId": second}))
        await asyncio.sleep(0)
        bridge.unsubscribe({"subscriptionId": second})
        with pytest.raises(ConnectorError, match="removed"):
            await waiting
        assert not session.handlers

    run(check())


def test_connector_timeout_overflow_disconnect_and_uncertain_execution():
    async def check():
        bridge = BrowserConnector()
        session = FakeSession()
        bridge.bind(session)
        key = bridge.subscribe({"name": "event"})["subscriptionId"]
        with pytest.raises(ConnectorError) as error:
            await bridge.wait({"subscriptionId": key, "timeoutMs": 100})
        assert error.value.code == "timeout"
        assert key in bridge.subscriptions
        for value in range(33):
            session.handlers["event"](value)
        with pytest.raises(ConnectorError) as error:
            await bridge.wait({"subscriptionId": key})
        assert error.value.code == "overflow"
        with pytest.raises(ConnectorError) as error:
            await bridge.execute({"code": "timeout"})
        assert error.value.uncertain
        bridge.cancel_all()
        key = bridge.subscribe({"name": "event"})["subscriptionId"]
        waiting = asyncio.create_task(bridge.wait({"subscriptionId": key}))
        await asyncio.sleep(0)
        bridge.bind(FakeSession())
        with pytest.raises(ConnectorError) as error:
            await waiting
        assert error.value.code == "browser_disconnected"

    run(check())


def test_host_commands_duplicates_final_message_settlement_and_stop_order():
    async def check():
        rpc = FakeRpc()
        host = BrowserHost(rpc=rpc)
        host._outbox = asyncio.Queue()
        try:
            await host.handle_command({"type": "prompt", "id": "p1", "message": "Hello"})
            await host.handle_command({"type": "prompt", "id": "p1", "message": "Hello"})
            assert [name for name, _ in rpc.commands] == ["prompt"]
            host.on_event({"type": "agent_end"})
            assert host.state["status"] == "running"
            message = {"role": "assistant", "content": [{"type": "text", "text": "final"}]}
            host.on_event({"type": "message_end", "message": message})
            assert host.messages == [message]
            host.on_event({"type": "agent_settled"})
            assert host.state["status"] == "idle"
            await host.handle_command({"type": "stop", "id": "stop1"})
            assert [name for name, _ in rpc.commands][-2:] == ["clear_queue", "abort"]
            frames = []
            while not host._outbox.empty():
                frames.append(host._outbox.get_nowait())
            assert any(f.get("success") is False and f.get("id") == "p1" for f in frames)
        finally:
            await host.close()

    run(check())


def test_prompt_deadline_has_explicit_uncertain_ack_not_blank_error():
    class TimeoutRpc(FakeRpc):
        async def command(self, kind, **data):
            raise TimeoutError

    async def check():
        host = BrowserHost(rpc=TimeoutRpc())
        host._outbox = asyncio.Queue()
        try:
            await host.handle_command({"type": "prompt", "id": "timeout", "message": "Hello"})
            frames = []
            while not host._outbox.empty():
                frames.append(host._outbox.get_nowait())
            ack = next(frame for frame in frames if frame["type"] == "ack")
            assert ack["success"] is False
            assert "uncertain" in ack["error"] and "replay" in ack["error"]
            assert host.state["status"] == "error"
        finally:
            await host.close()

    run(check())


def test_native_dialog_response_validation_once_and_fail_closed():
    async def check():
        rpc = FakeRpc()
        host = BrowserHost(rpc=rpc)
        host._chat = object()  # A UI is present; suppress immediate fail-closed path.
        try:
            host.on_event(
                {
                    "type": "extension_ui_request",
                    "id": "d1",
                    "method": "select",
                    "title": "Select",
                    "options": ["A", "B"],
                }
            )
            with pytest.raises(ValueError, match="Invalid selection"):
                await host._dialog_response({"id": "d1", "value": "X"})
            await host._dialog_response({"id": "d1", "value": "A"})
            with pytest.raises(ValueError, match="already answered"):
                await host._dialog_response({"id": "d1", "value": "B"})
            assert rpc.sent == [{"type": "extension_ui_response", "id": "d1", "value": "A"}]
            host.on_event({"type": "extension_ui_request", "id": "d2", "method": "confirm"})
            await host.stop()
            assert rpc.sent[-1] == {"type": "extension_ui_response", "id": "d2", "cancelled": True}
        finally:
            host._chat = None
            await host.close()

    run(check())


def test_connector_auth_exact_host_origin_separate_secret_and_body_validation():
    async def check():
        host = BrowserHost(rpc=FakeRpc())
        host.runtime._origin = "http://127.0.0.1:12345"
        transport = httpx.ASGITransport(app=host.runtime.app, client=("127.0.0.1", 42000))
        try:
            async with httpx.AsyncClient(
                transport=transport, base_url=host.runtime.origin
            ) as client:
                endpoint = "/connector/subscribe"
                assert (await client.post(endpoint, json={"name": "test"})).status_code == 403
                browser_auth = {"Authorization": f"Bearer {host.runtime.token}"}
                assert (
                    await client.post(endpoint, headers=browser_auth, json={})
                ).status_code == 403
                auth = {"Authorization": f"Bearer {host.connector_token}"}
                assert (
                    await client.post(
                        endpoint, headers={**auth, "Origin": host.runtime.origin}, json={}
                    )
                ).status_code == 403
                assert (
                    await client.post(endpoint, headers={**auth, "Host": "evil.test"}, json={})
                ).status_code == 403
                assert (await client.post(endpoint, headers=auth, content="{")).status_code == 400
                result = (await client.post(endpoint, headers=auth, json={"name": "test"})).json()
                assert result["error"]["code"] == "browser_unavailable"
                assert (await client.get("/assets/contract.md")).status_code == 404
        finally:
            await host.close()

    run(check())


def test_rpc_lf_framing_out_of_order_response_and_subprocess_cleanup():
    async def check():
        events = []
        rpc = PiRpc(events.append)
        source = """import sys,json
commands = [json.loads(sys.stdin.buffer.readline()) for _ in range(2)]
print(json.dumps({"type":"message_end","message":{"text":"A\\u2028B\\u2029C"}},ensure_ascii=False),flush=True)
for c in reversed(commands):
 print(json.dumps({"type":"response","id":c["id"],"success":True,"data":c["type"]}),flush=True)
for _ in sys.stdin: pass
"""
        await rpc.start([sys.executable, "-u", "-c", source])
        try:
            assert await asyncio.gather(rpc.command("one"), rpc.command("two")) == ["one", "two"]
            assert events[0]["message"]["text"] == "A\u2028B\u2029C"
        finally:
            await rpc.close(timeout=1)
        assert rpc.process.returncode == 0
        assert not rpc.pending

    run(check())


def test_rpc_unexpected_exit_rejects_pending_without_hanging():
    async def check():
        events = []
        rpc = PiRpc(events.append)
        await rpc.start([sys.executable, "-c", "import sys; sys.stdin.readline()"])
        try:
            with pytest.raises(RpcError, match="exited"):
                await rpc.command("get_state", timeout=2)
            assert events[-1]["type"] == "host_rpc_exit"
        finally:
            await rpc.close()

    run(check())


def test_rpc_direct_send_bounds_lock_and_drain():
    class BlockedInput:
        def write(self, data):
            pass

        async def drain(self):
            await asyncio.Event().wait()

    class Process:
        returncode = None
        stdin = BlockedInput()

    async def check():
        rpc = PiRpc(lambda event: None)
        rpc.process = Process()
        await rpc._write_lock.acquire()
        try:
            with pytest.raises(RpcError, match="write deadline"):
                await asyncio.wait_for(
                    rpc.send({"type": "extension_ui_response"}, timeout=0.02), 0.2
                )
        finally:
            rpc._write_lock.release()
        with pytest.raises(RpcError, match="write deadline"):
            await asyncio.wait_for(rpc.send({"type": "extension_ui_response"}, timeout=0.02), 0.2)
        assert not rpc._write_lock.locked()

    run(check())


def test_stop_bounds_control_lock_and_retires_rpc_on_uncertain_failure():
    async def check():
        rpc = FakeRpc()
        host = BrowserHost(rpc=rpc)
        await host._control.acquire()
        try:
            with pytest.raises(RpcError, match="shut down"):
                await asyncio.wait_for(host.stop(timeout=0.02), 0.2)
            assert rpc.closed
            assert host.state["status"] == "error"
            assert rpc.commands == []  # No blind replay/abort without clearance.
        finally:
            host._control.release()
            await host.close()

    run(check())


def test_stop_reaps_real_nonreading_child_and_cancelled_close_keeps_cleanup():
    async def check():
        ready = asyncio.Event()
        rpc = PiRpc(lambda event: ready.set())
        source = """import json, signal, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
print(json.dumps({"type":"ready"}),flush=True)
time.sleep(60)
"""
        await rpc.start([sys.executable, "-u", "-c", source])
        await asyncio.wait_for(ready.wait(), 2)
        host = BrowserHost(rpc=rpc)
        # Fill the child's unconsumed stdin pipe; direct send is draining.
        sending = asyncio.create_task(rpc.send({"type": "test", "payload": "x" * 2000000}))
        await asyncio.sleep(0.02)
        assert not sending.done()
        try:
            # Use short shutdown phases to test actual EOF -> TERM -> KILL quickly.
            original_close = rpc.close

            async def fast_close():
                await original_close(timeout=0.05)

            rpc.close = fast_close
            with pytest.raises(RpcError, match="shut down"):
                await asyncio.wait_for(host.stop(timeout=0.05), 1)
            assert rpc.process.returncode is not None
            assert host.state["status"] == "error"
            await asyncio.gather(sending, return_exceptions=True)
        finally:
            await host.close()

        # A caller cancellation must not abandon the shielded owned child cleanup.
        rpc2 = PiRpc(lambda event: None)
        await rpc2.start([sys.executable, "-c", "import time; time.sleep(60)"])
        closing = asyncio.create_task(rpc2.close(timeout=0.03))
        await asyncio.sleep(0.005)
        closing.cancel()
        await asyncio.gather(closing, return_exceptions=True)
        await asyncio.wait_for(rpc2.close(timeout=0.03), 1)
        assert rpc2.process.returncode is not None

    run(check())


def test_stop_cancels_sequential_native_dialogs_while_prompt_holds_control():
    class DialogRpc(FakeRpc):
        def __init__(self):
            super().__init__()
            self.host = None
            self.replies = {}
            self.started = asyncio.Event()

        async def command(self, kind, **data):
            self.commands.append((kind, data))
            if kind != "prompt":
                return {}
            for index, method in enumerate(("confirm", "select", "input", "editor")):
                key = f"dialog-{index}"
                self.replies[key] = asyncio.get_running_loop().create_future()
                self.host.on_event(
                    {
                        "type": "extension_ui_request",
                        "id": key,
                        "method": method,
                        "options": ["A", "B"],
                    }
                )
                self.started.set()
                await self.replies[key]
            return {"disposition": "handled"}

        async def send(self, record):
            self.sent.append(record)
            self.replies[record["id"]].set_result(record)

    async def check():
        rpc = DialogRpc()
        host = BrowserHost(rpc=rpc)
        rpc.host = host
        host._chat = object()
        host._outbox = asyncio.Queue()
        prompt = asyncio.create_task(
            host.handle_command({"type": "prompt", "id": "p", "message": "/sequential-dialogs"})
        )
        try:
            await rpc.started.wait()
            await asyncio.wait_for(host.stop(timeout=0.5), 1)
            await prompt
            assert host.state["status"] == "idle"
            assert not rpc.closed
            assert not host.dialogs
            assert len(rpc.sent) == 4 and all(value["cancelled"] for value in rpc.sent)
            assert [kind for kind, _ in rpc.commands][-2:] == ["clear_queue", "abort"]
            statuses = []
            while not host._outbox.empty():
                frame = host._outbox.get_nowait()
                if frame["type"] == "host_status":
                    statuses.append(frame["status"])
            assert statuses == ["running", "stopping", "idle"]
        finally:
            host._chat = None
            await host.close()

    run(check())


def test_host_close_bounds_stalled_socket_and_survives_caller_cancellation():
    class Socket:
        async def close(self, **kwargs):
            await asyncio.Event().wait()

    async def check():
        rpc = FakeRpc()
        host = BrowserHost(rpc=rpc)
        host._chat = Socket()
        closing = asyncio.create_task(host.close())
        await asyncio.sleep(0.005)
        closing.cancel()
        await asyncio.gather(closing, return_exceptions=True)
        assert not rpc.closed  # Shielded cleanup is still waiting for socket deadline.
        await asyncio.wait_for(host.close(), 1.5)
        assert rpc.closed
        assert host.runtime._closed
        assert host._close_task.done()

    run(check())


def test_queue_overflow_latches_one_close_task_and_late_settled_cannot_revive_error():
    class Socket:
        calls = 0

        async def close(self, **kwargs):
            self.calls += 1
            await asyncio.Event().wait()

    async def check():
        host = BrowserHost(rpc=FakeRpc())
        socket = Socket()
        host._chat = socket
        host._outbox = asyncio.Queue(maxsize=1)
        for value in range(1000):
            host._publish({"value": value})
        assert len(host._tasks) == 1
        await asyncio.sleep(0)
        assert socket.calls == 1
        host._status("error")
        host.on_event({"type": "agent_settled"})
        host.on_event({"type": "agent_start"})
        assert host.state["status"] == "error"
        host._chat = None
        await host.close()
        assert not host._tasks

    run(check())


def test_one_real_runtime_server_with_synthetic_browser_execution_and_chat():
    async def check():
        import websockets

        host = BrowserHost(rpc=FakeRpc())
        await host.runtime.start()
        monitor = asyncio.create_task(host._monitor_browser())
        try:
            origin = host.runtime.origin
            ws_origin = origin.replace("http:", "ws:")
            async with websockets.connect(
                ws_origin + "/ws?token=" + host.runtime.token, origin=origin
            ) as browser:
                for _ in range(100):
                    if host.connector.session is not None:
                        break
                    await asyncio.sleep(0.01)
                call = asyncio.create_task(host.connector.execute({"code": "return 42"}))
                frame = json.loads(await browser.recv())
                assert frame["type"] == "execute"
                await browser.send(
                    json.dumps({"type": "result", "id": frame["id"], "ok": True, "value": 42})
                )
                assert await call == {"ok": True, "value": 42}
                async with websockets.connect(
                    ws_origin + "/chat?token=" + host.runtime.token, origin=origin
                ) as chat:
                    assert json.loads(await chat.recv())["type"] == "snapshot"
                    await chat.send(json.dumps({"type": "prompt", "id": "p1", "message": "Hello"}))
                    assert json.loads(await chat.recv())["status"] == "running"
                    assert json.loads(await chat.recv())["success"] is True
            for _ in range(100):
                if host.connector.session is None:
                    break
                await asyncio.sleep(0.01)
            assert host.connector.session is None
            assert [kind for kind, _ in host.rpc.commands][-2:] == ["clear_queue", "abort"]
        finally:
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)
            await host.close()

    run(check())
