"""Browser command guards exercised with isolated stores and a controlled Pi RPC."""

import asyncio
import json
from pathlib import Path

import pytest

pytest.importorskip("automata_web_runtime")

from automata.tools.web.host import BrowserHost  # noqa: E402
from automata.tools.web.sessions import PAGE_SIZE  # noqa: E402


def saved(path, cwd, session_id, name=None):
    entries = [
        {"type": "session", "cwd": str(cwd), "id": session_id},
        {"type": "message", "message": {"role": "user", "content": f"Preview {session_id}"}},
    ]
    if name:
        entries.append({"type": "session_info", "name": name})
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    return path


class FakePi:
    def __init__(self, current):
        self.current = current
        self.busy = {}
        self.commands = []
        self.switch_outcome = False
        self.switch_started = asyncio.Event()
        self.switch_gate = asyncio.Event()
        self.switch_gate.set()
        self.closed = False

    async def start(self, *_args, **_kwargs):
        pass

    async def close(self):
        self.closed = True

    async def command(self, kind, **data):
        self.commands.append((kind, data))
        if kind == "get_state":
            return {
                "sessionFile": str(self.current),
                "sessionId": self.current.stem,
                "sessionName": self.current.stem,
                "isStreaming": False,
                "isCompacting": False,
                "pendingMessageCount": 0,
                **self.busy,
            }
        if kind == "get_messages":
            if self.switch_outcome == "bad-history" and self.current.stem == "B":
                return {"messages": [None]}
            return {"messages": [{"role": "user", "content": self.current.stem}]}
        if kind == "switch_session":
            self.switch_started.set()
            await self.switch_gate.wait()
            if self.switch_outcome is True:
                return {"cancelled": True}
            self.current = Path(data["sessionPath"])
            if self.switch_outcome == "timeout":
                raise TimeoutError
            return {"cancelled": False}
        pytest.fail(f"Unexpected RPC: {kind}")


@pytest.fixture
def store(tmp_path):
    cwd = tmp_path / "project"
    store = tmp_path / "store"
    cwd.mkdir()
    store.mkdir()
    current = saved(store / "A.jsonl", cwd, "A")
    target = saved(store / "B.jsonl", cwd, "B", "Conversation B")
    return cwd, store, current, target


async def issue(host, kind, **data):
    await host.handle_command({"type": kind, "id": str(len(host._seen)), **data})
    while not host._outbox.empty():
        frame = host._outbox.get_nowait()
        if frame["type"] == "ack":
            return frame
    pytest.fail("No browser acknowledgement")


async def start(cwd, current):
    rpc = FakePi(current)
    host = BrowserHost(rpc=rpc)
    await host.start(cwd=cwd)
    host._outbox = asyncio.Queue()
    return host, rpc


async def selection(host):
    listing = await issue(host, "list_sessions")
    assert listing["success"], listing
    return {
        "sessionId": "B",
        "fromSessionId": "A",
        "receipt": listing["data"]["receipt"],
    }


def test_scoped_listing_current_preview_duplicate_and_paging(store, monkeypatch):
    cwd, root, current, target = store
    saved(root / "external.jsonl", cwd / "subdir", "external", "Other project")
    saved(root / "duplicate.jsonl", cwd, "B", "Duplicate name")
    caller = saved(root / "caller.jsonl", cwd, "caller")
    monkeypatch.setenv("PI_SESSION_FILE", str(caller))
    (root / "alias.jsonl").symlink_to(target)
    (root / "broken.jsonl").write_text("invalid JSON")
    for index in range(PAGE_SIZE):
        saved(root / f"S{index}.jsonl", cwd, f"S{index}")

    async def main():
        host, _ = await start(cwd, current)
        try:
            first = (await issue(host, "list_sessions"))["data"]
            second = (await issue(host, "list_sessions", offset=first["nextOffset"]))["data"]
            assert first["current"] == second["current"]
            assert first["current"]["id"] == "A" and first["current"]["current"] is True
            assert first["current"]["snippet"] == "Preview A"
            assert second["previousOffset"] == 0 and second["nextOffset"] is None
            assert len(first["sessions"]) == PAGE_SIZE
            rows = first["sessions"] + second["sessions"]
            assert len(rows) == PAGE_SIZE + 3
            assert {row["id"] for row in rows if row["unavailable"]} == {"B", "caller"}
            assert [row["label"] for row in rows if row["id"] == "caller"] == ["Preview caller"]
            assert [row["label"] for row in rows if row["id"] == "B"] == [
                "Duplicate name",
                "Conversation B",
            ]
            blocked = await issue(
                host,
                "switch_session",
                sessionId="B",
                fromSessionId="A",
                receipt=second["receipt"],
            )
            assert not blocked["success"]
        finally:
            await host.close()

    asyncio.run(main())


def test_receipt_and_stale_file_rejected_without_native_switch(store):
    cwd, _, current, target = store

    async def main():
        host, rpc = await start(cwd, current)
        try:
            args = await selection(host)
            no_op = await issue(host, "switch_session", sessionId="A", fromSessionId="A")
            assert no_op["data"] == {"unchanged": True}
            await selection(host)  # A newer listing invalidates this receipt.
            expired = await issue(host, "switch_session", **args)
            assert "not selectable" in expired["error"]
            args = await selection(host)
            spoofed_path = await issue(host, "switch_session", **{**args, "sessionId": str(target)})
            assert "not selectable" in spoofed_path["error"]
            args = await selection(host)
            saved(target, cwd, "B", "Edited after listing")
            stale = await issue(host, "switch_session", **args)
            assert "changed or is unavailable" in stale["error"]
            assert host.state["sessionId"] == "A" and host.messages == [
                {"role": "user", "content": "A"}
            ]
            assert "switch_session" not in [kind for kind, _ in rpc.commands]
        finally:
            await host.close()

    asyncio.run(main())


def test_preview_is_read_only_scoped_and_uses_latest_persisted_branch(store, monkeypatch):
    cwd, root, current, target = store
    caller = saved(root / "caller.jsonl", cwd, "caller")
    monkeypatch.setenv("PI_SESSION_FILE", str(caller))
    foreign = saved(root / "foreign.jsonl", cwd / "other", "foreign")
    entries = [
        {"type": "session", "version": 3, "cwd": str(cwd), "id": "B"},
        {
            "type": "message",
            "id": "a",
            "parentId": None,
            "message": {"role": "user", "content": "First question"},
        },
        {
            "type": "message",
            "id": "b",
            "parentId": "a",
            "message": {"role": "assistant", "content": "Abandoned branch"},
        },
        {
            "type": "message",
            "id": "c",
            "parentId": "a",
            "message": {"role": "user", "content": "Latest question"},
        },
        {
            "type": "message",
            "id": "d",
            "parentId": "c",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "Private thought"},
                    {"type": "toolCall", "id": "tool", "arguments": {"html": "Historic UI"}},
                    {"type": "text", "text": "<script>literal preview text</script>"},
                ],
                "provider": "fixture",
                "model": "saved",
                "usage": {"totalTokens": 42},
            },
        },
        {"type": "custom", "id": "e", "parentId": "d", "data": "Ignored custom content"},
    ]
    target.write_text("\n".join(map(json.dumps, entries)) + "\n")

    async def main():
        host, rpc = await start(cwd, current)
        try:
            listing = (await issue(host, "list_sessions"))["data"]
            assert {row["id"] for row in listing["sessions"]} == {"B", "caller"}
            assert listing["sessions"][0].keys() == {
                "id",
                "label",
                "snippet",
                "modified",
                "unavailable",
            }
            args = {"fromSessionId": "A", "receipt": listing["receipt"]}
            preview = await issue(host, "preview_session", sessionId="B", **args)
            assert preview["data"] == {
                "user": "Latest question",
                "assistant": "<script>literal preview text</script>",
                "model": "fixture/saved",
                "tokens": 42,
            }
            own = await issue(host, "preview_session", sessionId="A", **args)
            assert own["data"] == {
                "user": "Preview A",
                "assistant": None,
                "model": None,
                "tokens": None,
            }
            for session_id in ("caller", "foreign", str(foreign), str(target)):
                assert not (await issue(host, "preview_session", sessionId=session_id, **args))[
                    "success"
                ]
            assert not (
                await issue(
                    host, "preview_session", sessionId="B", **{**args, "fromSessionId": "Z"}
                )
            )["success"]
            saved(target, cwd, "B", "Changed after preview")
            assert not (await issue(host, "preview_session", sessionId="B", **args))["success"]
            assert host.state["sessionId"] == "A"
            assert [kind for kind, _ in rpc.commands] == ["get_state", "get_messages"]
        finally:
            await host.close()

    asyncio.run(main())


@pytest.mark.parametrize(
    "native_busy",
    [
        {"isStreaming": True},
        {"isCompacting": True},
        {"pendingMessageCount": 1},
    ],
)
def test_native_work_blocks_switch_and_no_abort(store, native_busy):
    cwd, _, current, _ = store

    async def main():
        host, rpc = await start(cwd, current)
        try:
            rpc.busy = native_busy
            result = await issue(host, "switch_session", **(await selection(host)))
            assert not result["success"] and "busy" in result["error"]
            assert [kind for kind, _ in rpc.commands] == ["get_state", "get_messages", "get_state"]
        finally:
            await host.close()

    asyncio.run(main())


def test_concurrent_browser_commands_cannot_cross_session_boundary(store):
    cwd, _, current, _ = store

    async def main():
        host, rpc = await start(cwd, current)
        switch = None
        try:
            rpc.switch_gate.clear()
            args = await selection(host)
            switch = asyncio.create_task(issue(host, "switch_session", **args))
            await asyncio.wait_for(rpc.switch_started.wait(), 2)
            assert host.state["status"] == "switching" and host.state["sessionId"] == "A"
            for kind, data in (
                ("prompt", {"message": "Stale prompt", "sessionId": "A"}),
                ("rename", {"name": "Stale rename", "sessionId": "A"}),
                ("stop", {}),
            ):
                result = await issue(host, kind, **data)
                assert not result["success"] and "switch is in progress" in result["error"]
            rpc.switch_gate.set()
            assert (await switch)["data"] == {"sessionId": "B"}
            assert host.messages == [{"role": "user", "content": "B"}]
            assert not {"prompt", "abort", "set_session_name"} & {kind for kind, _ in rpc.commands}
        finally:
            rpc.switch_gate.set()
            if switch is not None:
                await asyncio.gather(switch, return_exceptions=True)
            await host.close()

    asyncio.run(main())


@pytest.mark.parametrize("outcome", [True, "bad-history", "timeout"])
def test_cancel_preserves_binding_but_uncertain_rebind_fails_closed(store, outcome):
    cwd, _, current, _ = store

    async def main():
        host, rpc = await start(cwd, current)
        try:
            rpc.switch_outcome = outcome
            result = await issue(host, "switch_session", **(await selection(host)))
            assert not result["success"]
            assert host.state["sessionId"] == "A" and host.messages == [
                {"role": "user", "content": "A"}
            ]
            if outcome is True:
                assert "cancelled" in result["error"]
                assert host.state["status"] == "idle" and not rpc.closed
                rpc.switch_outcome = False
                result = await issue(host, "switch_session", **(await selection(host)))
                assert result["data"] == {"sessionId": "B"}
                stale_prompt = await issue(host, "prompt", sessionId="A", message="Old draft")
                assert not stale_prompt["success"]
            else:
                assert "could not be verified" in result["error"]
                assert host.state["status"] == "error" and rpc.closed
                assert not (await issue(host, "prompt", sessionId="A", message="Do not send"))[
                    "success"
                ]
                assert not (await issue(host, "stop"))["success"]
            assert "prompt" not in [kind for kind, _ in rpc.commands]
        finally:
            await host.close()

    asyncio.run(main())
