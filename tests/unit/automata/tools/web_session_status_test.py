"""Native session naming behavior through the browser host control interface."""
import asyncio

import pytest

pytest.importorskip("automata_web_runtime")
from automata.tools.web.host import BrowserHost
from automata.tools.web.rpc import RpcError


class NamingRpc:
    def __init__(self):
        self.name = "Saved name"
        self.commands = []
        self.fail = False

    async def command(self, kind, **data):
        self.commands.append((kind, data))
        if kind == "set_session_name":
            if self.fail:
                raise RpcError("Native write failed")
            self.name = data["name"]
        return {"sessionName": self.name} if kind == "get_state" else {}

    async def close(self):
        pass


def test_rename_uses_native_control_and_confirmed_state_without_messages():
    async def check():
        rpc = NamingRpc()
        host = BrowserHost(rpc=rpc)
        host._outbox = asyncio.Queue()
        try:
            await host.handle_command({"type": "rename", "id": "rename", "name": "  New name  "})
            assert rpc.commands == [("set_session_name", {"name": "New name"}), ("get_state", {})]
            ack = host._outbox.get_nowait()
            assert ack == {
                "type": "ack",
                "id": "rename",
                "success": True,
                "data": {"sessionName": "New name"},
            }
            assert host.state["sessionName"] == "New name"
            assert host.messages == [] and host.state["status"] == "idle"
            host.on_event({"type": "session_info_changed", "name": "External"})
            assert host.state["sessionName"] == "External"
            host.on_event({"type": "session_info_changed"})
            assert host.state["sessionName"] is None
        finally:
            await host.close()
    asyncio.run(check())


@pytest.mark.parametrize("name", ["", "  ", None, 42])
def test_blank_or_invalid_rename_never_reaches_pi(name):
    async def check():
        rpc = NamingRpc()
        host = BrowserHost(rpc=rpc)
        host._outbox = asyncio.Queue()
        try:
            await host.handle_command({"type": "rename", "id": "invalid", "name": name})
            assert not host._outbox.get_nowait()["success"]
            assert rpc.commands == [] and host.messages == []
        finally:
            await host.close()
    asyncio.run(check())


def test_failed_native_rename_preserves_confirmed_identity_and_activity():
    async def check():
        rpc = NamingRpc()
        rpc.fail = True
        host = BrowserHost(rpc=rpc)
        host.state.update(sessionName="Saved name", status="running")
        host._outbox = asyncio.Queue()
        try:
            await host.handle_command({"type": "rename", "id": "failed", "name": "Attempt"})
            ack = host._outbox.get_nowait()
            assert not ack["success"] and "Native write failed" in ack["error"]
            assert host.state["sessionName"] == "Saved name"
            assert host.state["status"] == "running" and host.messages == []
        finally:
            await host.close()
    asyncio.run(check())
