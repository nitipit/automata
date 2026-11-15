"""App adapter/queue contracts; Node executes real JS without a browser/provider."""

import asyncio
import json
import shutil
import subprocess

import pytest

from automata.tools.web.connector import BrowserConnector, ConnectorError


class Session:
    is_connected = True

    def __init__(self):
        self.handlers = {}

    def set_handler(self, name, handler):
        self.handlers[name] = handler

    def remove_handler(self, name):
        self.handlers.pop(name, None)

    async def execute(self, code, *, timeout):
        node = shutil.which("node")
        if not node:
            pytest.skip("Node is required to execute the actual JavaScript wrapper")
        program = """
import fs from 'node:fs';
const code = JSON.parse(fs.readFileSync(0, 'utf8'));
const contexts = new Map();
const readyBudgets = [];
globalThis.window = {automataUI: {context(id) {
  if (!contexts.has(id)) {
    let materialized = false, finished = false;
    const root = {};
    contexts.set(id, {blockId:id, toolCallId:id,
      async ready(timeoutMs) {
        readyBudgets.push(timeoutMs);
        if (['missing-owner', 'inactive-owner'].includes(id)) {
          await new Promise(resolve => setTimeout(resolve, timeoutMs));
          throw new Error('PRIVATE: owner readiness deadline');
        }
        if (id === 'disconnected-owner') {
          await new Promise(resolve => setTimeout(resolve, 2));
          throw new Error('PRIVATE: bridge disconnected');
        }
        if (id === 'delayed-owner') {
          await new Promise(resolve => setTimeout(resolve, 5));
          window.ownerReady = true;
        }
      },
      get root() {
        if (finished && !materialized) throw new Error('First root creation is sealed');
        materialized = true; return root;
      },
      finish() { finished = true; },
      get materialized() { return materialized; }});
  }
  return contexts.get(id);
}}};
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
const bridge = {state:{}, emit(){}};
try {
  const value = await new AsyncFunction('bridge', code)(bridge);
  await new Promise(resolve => setTimeout(resolve, 5));
  console.log(JSON.stringify({value, observed:bridge.state, readyBudgets}));
}
catch { console.log(JSON.stringify({failed:true})); }
"""
        completed = await asyncio.to_thread(
            subprocess.run, [node, "--input-type=module", "--eval", program],
            input=json.dumps(code), capture_output=True, text=True, timeout=5, check=True,
        )
        data = json.loads(completed.stdout)
        if data.get("failed"):
            raise type("JavaScriptError", (Exception,), {})("PRIVATE browser error")
        self.observed = data["observed"]
        self.ready_budgets = data["readyBudgets"]
        return data["value"]


def execute(code, owner="owner"):
    async def check():
        connector = BrowserConnector()
        connector.bind(Session())
        return await connector.execute({"code": code, "toolCallId": owner})
    return asyncio.run(check())


def test_lazy_context_preserves_plain_value_and_does_not_materialize():
    value = {"execution": "pretend-nonce", "ok": False, "materialized": True,
             "ui": {"blockId": "not-owner"}, "value": [1, None, False]}
    assert execute("return " + json.dumps(value)) == {"ok": True, "value": value}
    assert execute("return undefined") == {"ok": True, "value": None}


def test_materialized_context_has_native_identity_and_unmodified_value():
    owner = "native/tool-'\\\"\nowner"
    result = execute("ui.root.textContent='Hello'; return {answer:42, owner:ui.toolCallId};", owner)
    assert result == {"ok": True, "value": {"answer": 42, "owner": owner},
                      "ui": {"blockId": owner, "toolCallId": owner}}


@pytest.mark.parametrize(
    "failure", ["throw new Error('PRIVATE secret')", "return 1n", "const a={}; a.a=a; return a"]
)
def test_caught_error_retains_materialized_marker_and_never_error_text(failure):
    result = execute("ui.root; " + failure)
    assert result["ok"] is False
    assert result["error"]["uncertain"] is True
    assert result["ui"] == {"blockId": "owner", "toolCallId": "owner"}
    assert "PRIVATE" not in json.dumps(result)


def test_error_without_root_has_no_marker():
    assert "ui" not in execute("throw new Error('PRIVATE')")


def test_delayed_exact_owner_is_ready_before_body_materialization():
    result = execute("ui.root; return window.ownerReady === true;", "delayed-owner")
    assert result == {
        "ok": True, "value": True,
        "ui": {"blockId": "delayed-owner", "toolCallId": "delayed-owner"},
    }


@pytest.mark.parametrize("owner", ["missing-owner", "inactive-owner", "disconnected-owner"])
def test_readiness_failure_is_bounded_and_body_never_runs(owner):
    async def check():
        connector = BrowserConnector()
        session = Session()
        connector.bind(session)
        result = await asyncio.wait_for(connector.execute({
            "code": "bridge.state.bodyRan=true; ui.root; return 'must not run';",
            "toolCallId": owner, "timeoutMs": 100,
        }), 2)
        assert result["ok"] is False
        assert result["error"]["code"] == "ui_unavailable"
        assert result["error"]["uncertain"] is False
        assert "body was not run" in result["error"]["message"]
        assert "PRIVATE" not in json.dumps(result)
        assert "ui" not in result and session.observed == {}
        assert session.ready_budgets == [50]
    asyncio.run(check())


@pytest.mark.parametrize("timeout_ms,ready_ms", [(100, 50), (1000, 500), (10000, 1000)])
def test_readiness_budget_reserves_server_deadline(timeout_ms, ready_ms):
    async def check():
        connector = BrowserConnector()
        session = Session()
        connector.bind(session)
        result = await connector.execute({
            "code": "return 42", "toolCallId": "owner", "timeoutMs": timeout_ms,
        })
        assert result == {"ok": True, "value": 42}
        assert session.ready_budgets == [ready_ms]
    asyncio.run(check())


@pytest.mark.parametrize(
    "finish", ["return 'scheduled'", "throw new Error('PRIVATE')", "return 1n"]
)
def test_first_root_after_settlement_is_blocked_for_same_and_fresh_context(finish):
    async def check():
        connector = BrowserConnector()
        session = Session()
        connector.bind(session)
        code = """
setTimeout(() => {
  const pairs = [['same', ui], ['fresh', window.automataUI.context(ui.toolCallId)]];
  for (const [name, context] of pairs) {
    try { context.root; bridge.state[name] = 'created'; }
    catch { bridge.state[name] = 'blocked'; }
  }
}, 0);
""" + finish
        result = await connector.execute({"code": code, "toolCallId": "owner"})
        assert "ui" not in result
        assert result["ok"] is (finish == "return 'scheduled'")
        assert session.observed == {"same": "blocked", "fresh": "blocked"}
    asyncio.run(check())


@pytest.mark.parametrize(
    "finish", ["return 'scheduled'", "throw new Error('PRIVATE')", "return 1n"]
)
def test_materialized_root_remains_available_to_later_handlers(finish):
    async def check():
        connector = BrowserConnector()
        session = Session()
        connector.bind(session)
        code = """
const root = ui.root;
setTimeout(() => {
  bridge.state.same = ui.root === root;
  bridge.state.fresh = window.automataUI.context(ui.toolCallId).root === root;
}, 0);
""" + finish
        result = await connector.execute({"code": code, "toolCallId": "owner"})
        assert result["ui"] == {"blockId": "owner", "toolCallId": "owner"}
        assert result["ok"] is (finish == "return 'scheduled'")
        assert session.observed == {"same": True, "fresh": True}
    asyncio.run(check())


def test_parallel_contexts_are_lexical_and_values_do_not_collide():
    async def check():
        connector = BrowserConnector()
        connector.bind(Session())
        results = await asyncio.gather(*(
            connector.execute({
                "code": "ui.root; await Promise.resolve(); return ui.blockId;", "toolCallId": owner
            })
            for owner in ["first", "second"]
        ))
        for result, owner in zip(results, ["first", "second"], strict=True):
            assert result == {
                "ok": True, "value": owner, "ui": {"blockId": owner, "toolCallId": owner}
            }
    asyncio.run(check())


def test_invalid_adapter_response_is_uncertain_not_success():
    class Invalid(Session):
        async def execute(self, code, *, timeout):
            return {"execution": "wrong", "ok": True, "value": 1}
    async def check():
        connector = BrowserConnector()
        connector.bind(Invalid())
        with pytest.raises(ConnectorError) as error:
            await connector.execute({"code": "return 1", "toolCallId": "owner"})
        assert error.value.code == "protocol"
        assert error.value.uncertain is True
    asyncio.run(check())


def test_timeout_remains_uncertain_without_replay():
    class Deadline(Session):
        calls = 0
        async def execute(self, code, *, timeout):
            self.calls += 1
            raise TimeoutError
    async def check():
        connector = BrowserConnector()
        session = Deadline()
        connector.bind(session)
        with pytest.raises(ConnectorError) as error:
            await connector.execute({"code": "ui.root", "toolCallId": "owner"})
        assert error.value.code == "timeout" and error.value.uncertain
        assert session.calls == 1
    asyncio.run(check())


def test_cancelled_execution_is_not_retried_or_reported_as_rollback():
    class Pending(Session):
        calls = 0
        async def execute(self, code, *, timeout):
            self.calls += 1
            await asyncio.Future()
    async def check():
        connector = BrowserConnector()
        session = Pending()
        connector.bind(session)
        task = asyncio.create_task(connector.execute({"code": "ui.root", "toolCallId": "owner"}))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert session.calls == 1
    asyncio.run(check())


def test_queue_payloads_correlation_and_exact_connection_ownership():
    async def check():
        connector = BrowserConnector()
        original = Session()
        connector.bind(original)
        a = connector.subscribe({
            "name": "invoice:approved", "correlationId": "block-a"
        })["subscriptionId"]
        b = connector.subscribe({
            "name": "invoice:approved", "correlationId": "block-b"
        })["subscriptionId"]
        payload = {
            "correlationId": "block-b", "invoice": {"lines": [1, {"amount": 7}]}, "custom": False
        }
        original.handlers["invoice:approved"](payload)
        assert connector.subscriptions[a].queue.empty()
        assert (await connector.wait({"subscriptionId": b}))["event"] == payload
        pending = asyncio.create_task(connector.wait({"subscriptionId": a}))
        await asyncio.sleep(0)
        replacement = Session()
        connector.bind(replacement)
        with pytest.raises(ConnectorError) as error:
            await pending
        assert error.value.code == "browser_disconnected"
        assert not original.handlers and not replacement.handlers
        assert not connector.subscriptions
    asyncio.run(check())


def test_cancel_all_releases_handlers_and_overflow_fails_not_drops_silently():
    async def check():
        connector = BrowserConnector()
        session = Session()
        connector.bind(session)
        key = connector.subscribe({"name": "changes"})["subscriptionId"]
        for i in range(33):
            session.handlers["changes"]({"i": i})
        with pytest.raises(ConnectorError) as error:
            await connector.wait({"subscriptionId": key})
        assert error.value.code == "overflow"
        connector.cancel_all()
        assert not session.handlers and not connector.subscriptions
    asyncio.run(check())
