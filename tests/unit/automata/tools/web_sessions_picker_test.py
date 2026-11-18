"""Read-only browser picker metadata against isolated project and store fixtures."""

import asyncio
import json

import pytest

from automata.tools.web.chat import ChatSession
from automata.tools.web.launch import prepare_launch
from automata.tools.web.sessions import PAGE_SIZE


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
        self.commands = []

    async def start(self, *_args, **_kwargs):
        pass

    async def close(self):
        pass

    async def command(self, kind, **data):
        self.commands.append((kind, data))
        if kind == "get_state":
            return {
                "sessionFile": str(self.current),
                "sessionId": self.current.stem,
                "sessionName": self.current.stem,
            }
        if kind == "get_messages":
            return {"messages": [{"role": "user", "content": self.current.stem}]}
        pytest.fail(f"Unexpected RPC: {kind}")


@pytest.fixture
def store(tmp_path):
    cwd, store = tmp_path / "project", tmp_path / "store"
    cwd.mkdir()
    store.mkdir()
    current = saved(store / "A.jsonl", cwd, "A")
    target = saved(store / "B.jsonl", cwd, "B", "Conversation B")
    return cwd, store, current, target


async def issue(chat, kind, **data):
    await chat.handle_command({"type": kind, "id": str(len(chat._seen)), **data})
    while not chat._outbox.empty():
        frame = chat._outbox.get_nowait()
        if frame["type"] == "ack":
            return frame
    pytest.fail("No browser acknowledgement")


async def start(cwd, current, caller):
    rpc = FakePi(current)
    chat = ChatSession(rpc=rpc)
    launch = prepare_launch(pi="pi", extension=cwd / "inert.ts", cwd=cwd)
    await chat.start(
        launch, origin="http://127.0.0.1:1234", project=cwd, caller=caller, route_id=str.isalnum
    )
    chat._outbox = asyncio.Queue()
    return chat, rpc


def test_scoped_listing_current_preview_duplicate_and_paging(store):
    cwd, root, current, target = store
    saved(root / "external.jsonl", cwd / "subdir", "external", "Other project")
    saved(root / "duplicate.jsonl", cwd, "B", "Duplicate name")
    caller = saved(root / "caller.jsonl", cwd, "caller")
    (root / "alias.jsonl").symlink_to(target)
    (root / "broken.jsonl").write_text("invalid JSON")
    for index in range(PAGE_SIZE):
        saved(root / f"S{index}.jsonl", cwd, f"S{index}")

    async def main():
        chat, _ = await start(cwd, current, caller)
        try:
            first = (await issue(chat, "list_sessions"))["data"]
            second = (await issue(chat, "list_sessions", offset=first["nextOffset"]))["data"]
            assert first["current"] == second["current"]
            assert first["current"]["id"] == "A" and first["current"]["current"] is True
            assert first["current"]["snippet"] == "Preview A"
            assert second["previousOffset"] == 0 and second["nextOffset"] is None
            assert len(first["sessions"]) == PAGE_SIZE
            rows = first["sessions"] + second["sessions"]
            assert len(rows) == PAGE_SIZE + 3
            assert {row["id"] for row in rows if row["unavailable"]} == {"B", "caller"}
            assert [row["unavailable"] for row in rows if row["id"] == "caller"] == [
                "Open in the calling Pi session"
            ]
            assert [row["unavailable"] for row in rows if row["id"] == "B"] == [
                "Duplicate session ID"
            ] * 2
            blocked = await issue(
                chat, "preview_session", sessionId="B", fromSessionId="A", receipt=second["receipt"]
            )
            assert not blocked["success"]
            first_selection = first["sessions"][0]["id"]
            assert not (
                await issue(
                    chat,
                    "preview_session",
                    sessionId=first_selection,
                    fromSessionId="A",
                    receipt=first["receipt"],
                )
            )["success"]
        finally:
            await chat.close()

    asyncio.run(main())


def test_preview_is_read_only_scoped_and_uses_latest_persisted_branch(store):
    cwd, root, current, target = store
    caller = saved(root / "caller.jsonl", cwd, "caller")
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
            "message": {"role": "user", "content": "Discarded branch"},
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
        chat, rpc = await start(cwd, current, caller)
        try:
            listing = (await issue(chat, "list_sessions"))["data"]
            assert {row["id"] for row in listing["sessions"]} == {"B", "caller"}
            assert listing["sessions"][0].keys() == {
                "id",
                "label",
                "snippet",
                "modified",
                "unavailable",
            }
            args = {"fromSessionId": "A", "receipt": listing["receipt"]}
            preview = await issue(chat, "preview_session", sessionId="B", **args)
            assert preview["data"] == {
                "user": "Latest question",
                "assistant": "<script>literal preview text</script>",
                "model": "fixture/saved",
                "tokens": 42,
            }
            own = await issue(chat, "preview_session", sessionId="A", **args)
            assert own["data"] == {
                "user": "Preview A",
                "assistant": None,
                "model": None,
                "tokens": None,
            }
            for session_id in ("caller", "foreign", str(foreign), str(target)):
                assert not (await issue(chat, "preview_session", sessionId=session_id, **args))[
                    "success"
                ]
            assert not (
                await issue(
                    chat, "preview_session", sessionId="B", **{**args, "fromSessionId": "Z"}
                )
            )["success"]
            saved(target, cwd, "B", "Changed after preview")
            assert not (await issue(chat, "preview_session", sessionId="B", **args))["success"]
            assert chat.id == "A"
            assert [kind for kind, _ in rpc.commands] == ["get_state", "get_messages", "get_state"]
        finally:
            await chat.close()

    asyncio.run(main())
