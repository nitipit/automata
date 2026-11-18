"""Control wire and scheduling against a disposable, session-bound RPC double."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from automata.tools.web.chat import ChatSession
from automata.tools.web.model_controls import SCOPE_KEY_ENV
from automata.tools.web.rpc import RpcRejected

SCOPE = [
    {"provider": "test", "id": "first", "name": "First", "headers": {"secret": "hidden"}},
    {"provider": "test", "id": "second", "name": "Second", "thinkingLevel": "medium"},
    {"provider": "test", "id": "third", "name": "Third"},
    {"provider": "test", "id": "plain", "name": "Plain"},
]
LEVELS = {
    "first": ["off", "low", "high"],
    "second": ["off", "low", "medium"],
    "third": ["off", "low"],
    "plain": ["off"],
}


class Native:
    def __init__(self, tmp_path, scope):
        self.path = tmp_path / "native.jsonl"
        self.scope = scope
        self.model = "first"
        self.level = "high"
        self.streaming = False
        self.commands = []
        self.mutations = []
        self.hold_set = asyncio.Event()
        self.release_set = asyncio.Event()
        self.release_set.set()
        self.fail = None
        self.closed = False

    async def start(self, argv, *, cwd, env):
        self.started = (argv, cwd)
        if self.scope is not None:
            self.event(
                {
                    "type": "extension_ui_request",
                    "method": "setStatus",
                    "statusKey": env[SCOPE_KEY_ENV],
                    "statusText": json.dumps(self.scope),
                }
            )

    async def command(self, kind, **data):
        self.commands.append(kind)
        if kind == "get_state":
            return {
                "sessionId": "native-id",
                "sessionFile": str(self.path),
                "model": {"provider": "test", "id": self.model, "headers": {"secret": "hidden"}},
                "thinkingLevel": self.level,
                "isStreaming": self.streaming,
            }
        if kind == "get_messages":
            return {"messages": []}
        if kind == "get_available_thinking_levels":
            return {"levels": LEVELS[self.model]}
        if kind.startswith("set_"):
            if self.fail:
                raise self.fail
            self.mutations.append((kind, data.get("modelId") or data.get("level")))
            self.hold_set.set()
            await self.release_set.wait()
            if kind == "set_model":
                self.model = data["modelId"]
                self.level = "low" if self.model != "plain" else "off"
            else:
                self.level = data["level"]
        if kind == "prompt":
            self.streaming = True
            self.mutations.append((kind, self.model, self.level))
            return {"disposition": "started"}

    async def close(self):
        self.closed = True


async def start(tmp_path, scope=SCOPE):
    native = Native(tmp_path, scope)
    chat = ChatSession(rpc=native)
    native.event = chat.on_event
    chat._outbox = asyncio.Queue()
    await chat.start(
        SimpleNamespace(argv=("pi",), cwd=tmp_path),
        origin="http://localhost:1234",
        project=tmp_path,
        caller=None,
        route_id=lambda value: value == "native-id",
    )
    return native, chat


async def command(chat, kind, key, **data):
    await chat.handle_command({"type": kind, "id": key, "sessionId": "native-id", **data})
    result = []
    while not chat._outbox.empty():
        result.append(chat._outbox.get_nowait())
    return result


def test_snapshot_and_native_switch_levels(tmp_path):
    async def check():
        native, chat = await start(tmp_path)
        state = chat._snapshot()["state"]
        assert state["modelChoices"][0] == {"provider": "test", "id": "first", "name": "First"}
        assert state["model"] == {"provider": "test", "id": "first", "name": "first"}
        assert "hidden" not in json.dumps(state)
        assert state["thinkingLevels"] == LEVELS["first"]
        assert chat._outbox.empty()  # private catalog is not a browser rpc_event

        # Previous high is unsupported; the explicit native scope default is usable.
        records = await command(chat, "set_model", "1", provider="test", modelId="second")
        assert [rec["type"] for rec in records] == ["host_status", "ack"]
        assert records[0]["model"]["id"] == "second"
        assert records[0]["thinkingLevel"] == records[1]["data"]["thinkingLevel"] == "medium"
        # Previous level is unsupported and there is no scope default; keep Pi's default.
        records = await command(chat, "set_model", "2", provider="test", modelId="third")
        assert records[-1]["data"]["thinkingLevel"] == "low"
        # Preserve supported off rather than resetting to the target's native low default.
        await command(chat, "set_thinking_level", "3", level="off")
        records = await command(chat, "set_model", "4", provider="test", modelId="first")
        assert records[-1]["data"]["thinkingLevel"] == "off"
        assert native.mutations == [
            ("set_model", "second"),
            ("set_thinking_level", "medium"),
            ("set_model", "third"),
            ("set_thinking_level", "off"),
            ("set_model", "first"),
            ("set_thinking_level", "off"),
        ]

    asyncio.run(check())


@pytest.mark.parametrize(
    "scope,available", [(None, False), ({}, False), (SCOPE * 2, False), ([], True)]
)
def test_missing_malformed_and_empty_scopes_never_expand(tmp_path, scope, available):
    async def check():
        native, chat = await start(tmp_path, scope)
        state = chat._snapshot()["state"]
        assert state["modelChoices"] == []
        assert ("controlsError" not in state) is available
        assert state["thinkingLevels"] == (LEVELS["first"] if available else [])
        records = await command(chat, "set_model", "1", provider="test", modelId="second")
        assert records[-1]["success"] is False
        records = await command(chat, "set_thinking_level", "2", level="low")
        assert records[-1]["success"] is available
        records = await command(chat, "prompt", "3", message="Ordinary chat still works")
        assert records[-1]["success"] is True
        assert not any(item[0] == "set_model" for item in native.mutations)

    asyncio.run(check())


def test_native_max_is_selectable(tmp_path, monkeypatch):
    monkeypatch.setitem(LEVELS, "first", ["low", "medium", "high", "xhigh", "max"])

    async def check():
        native, chat = await start(tmp_path)
        records = await command(chat, "set_thinking_level", "max", level="max")
        assert records[-1]["success"] and native.level == "max"
        assert chat.state["thinkingLevels"] == LEVELS["first"]

    asyncio.run(check())


def test_model_switch_independent_of_unrecognized_thinking(tmp_path, monkeypatch):
    monkeypatch.setitem(LEVELS, "first", ["high", "future"])
    monkeypatch.setitem(LEVELS, "second", ["low", "future"])

    async def check():
        native, chat = await start(tmp_path, [*SCOPE[:1], dict(SCOPE[1], thinkingLevel="future")])
        assert chat.state["thinkingLevels"] == [] and "controlsError" not in chat.state
        denied = await command(chat, "set_thinking_level", "1", level="high")
        assert not denied[-1]["success"]
        records = await command(chat, "set_model", "2", provider="test", modelId="second")
        assert records[-1]["success"] and native.model == "second"
        assert records[-1]["data"]["thinkingLevels"] == []

    asyncio.run(check())


def test_misbound_out_of_scope_unsupported_and_busy_are_refused(tmp_path):
    async def check():
        native, chat = await start(tmp_path)
        await chat.handle_command(
            {"type": "set_thinking_level", "id": "wrong", "sessionId": "other", "level": "low"}
        )
        assert not chat._outbox.get_nowait()["success"]
        for key, kind, data in [
            ("1", "set_model", {"provider": "other", "modelId": "first"}),
            ("2", "set_thinking_level", {"level": "xhigh"}),
            ("3", "set_thinking_level", {"level": []}),
        ]:
            records = await command(chat, kind, key, **data)
            assert not records[-1]["success"]
        native.streaming = True  # A lost/delayed agent_start cannot bypass the native check.
        records = await command(chat, "set_thinking_level", "4", level="low")
        assert "busy" in records[-1]["error"]
        assert native.mutations == []

    asyncio.run(check())


def test_prompt_waits_behind_a_change_and_active_reply_refuses_changes(tmp_path):
    async def check():
        native, chat = await start(tmp_path)
        native.release_set.clear()
        change = asyncio.create_task(
            chat.handle_command(
                {
                    "type": "set_thinking_level",
                    "id": "change",
                    "sessionId": "native-id",
                    "level": "low",
                }
            )
        )
        await native.hold_set.wait()
        prompt = asyncio.create_task(
            chat.handle_command({"type": "prompt", "id": "prompt", "message": "next"})
        )
        await asyncio.sleep(0)
        assert native.mutations == [("set_thinking_level", "low")]
        native.release_set.set()
        await asyncio.gather(change, prompt)
        records = await command(chat, "set_model", "racing", provider="test", modelId="second")
        assert "busy" in records[-1]["error"]
        assert native.mutations == [("set_thinking_level", "low"), ("prompt", "first", "low")]

    asyncio.run(check())


@pytest.mark.parametrize(
    "failure,closed", [(RpcRejected("internal detail"), False), (TimeoutError(), True)]
)
def test_confident_refusal_keeps_chat_but_uncertain_mutation_retires(tmp_path, failure, closed):
    async def check():
        native, chat = await start(tmp_path)
        native.fail = failure
        records = await command(chat, "set_model", "failed", provider="test", modelId="second")
        assert not records[-1]["success"]
        assert "internal detail" not in records[-1]["error"]
        assert native.closed is closed
        assert chat.state["status"] == ("error" if closed else "idle")

    asyncio.run(check())
