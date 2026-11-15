"""Session-bound browser execution and bounded, correlated event subscriptions."""

from __future__ import annotations

import asyncio
import json
import math
import uuid
from dataclasses import dataclass, field
from typing import Any


class ConnectorError(RuntimeError):
    def __init__(self, code: str, message: str, *, uncertain: bool = False):
        super().__init__(message)
        self.code = code
        self.uncertain = uncertain


def timeout_seconds(body: dict, default: int) -> float:
    value = body.get("timeoutMs", default)
    if type(value) not in (int, float) or not math.isfinite(value) or not 100 <= value <= 120000:
        raise ConnectorError("invalid_request", "timeoutMs must be between 100 and 120000")
    return value / 1000


def inline_execution(
    code: str, tool_call_id: str, nonce: str, ready_timeout_ms: int = 1000
) -> str:
    """Private app adapter around the unchanged upstream async function body.

    A nested function isolates agent locals/returns from wrapper bookkeeping. JSON
    normalization runs inside the catch boundary so serialization errors also
    retain an already-materialized root, without leaking arbitrary error values.
    Settlement seals first root creation so delayed callbacks cannot create an
    unrecorded historical block; existing roots remain usable by their handlers.
    The per-call nonce and nesting prevent user return objects being mistaken for
    adapter metadata; neither this helper nor root ownership is a sandbox.
    """
    return f"""
const context = window.automataUI.context({json.dumps(tool_call_id)});
let outcome;
let started = false;
try {{
  await context.ready({ready_timeout_ms});
  started = true;
  const value = await (async function(bridge, ui) {{
{code}
  }})(bridge, context);
  outcome = {{ok: true, value: JSON.parse(JSON.stringify(value === undefined ? null : value))}};
}} catch {{
  outcome = {{ok: false, phase: started ? 'body' : 'readiness'}};
}}
context.finish();
return {{execution: {json.dumps(nonce)}, ...outcome, materialized: context.materialized === true}};
"""


@dataclass
class Subscription:
    session: Any
    name: str
    correlation: str | None
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=32))
    waiting: bool = False
    error: ConnectorError | None = None


class BrowserConnector:
    def __init__(self):
        self.session = None
        self.subscriptions: dict[str, Subscription] = {}

    def bind(self, session) -> None:
        if session is self.session:
            return
        self.cancel_all("browser_disconnected", "Browser session changed")
        self.session = session

    def cancel_all(self, code="cancelled", message="Browser wait cancelled") -> None:
        for subscription in self.subscriptions.values():
            subscription.error = ConnectorError(code, message)
            while not subscription.queue.empty():
                subscription.queue.get_nowait()
            subscription.queue.put_nowait(None)
            subscription.session.remove_handler(subscription.name)
        # Keep terminal errors for already pending waits; remove lookup entries.
        self.subscriptions.clear()

    def _session(self):
        if self.session is None or not self.session.is_connected:
            raise ConnectorError("browser_unavailable", "No live browser bridge")
        return self.session

    def _dispatch(self, name: str, session, data) -> None:
        for subscription in tuple(self.subscriptions.values()):
            if subscription.name != name or subscription.session is not session:
                continue
            if subscription.correlation is not None and (
                not isinstance(data, dict) or data.get("correlationId") != subscription.correlation
            ):
                continue
            if subscription.error:
                continue
            if subscription.queue.full():
                subscription.error = ConnectorError("overflow", "Browser event queue overflow")
                while not subscription.queue.empty():
                    subscription.queue.get_nowait()
                subscription.queue.put_nowait(None)
            else:
                subscription.queue.put_nowait(data)

    def subscribe(self, body: dict) -> dict:
        session = self._session()
        name, correlation = body.get("name"), body.get("correlationId")
        if not isinstance(name, str) or not 1 <= len(name) <= 256:
            raise ConnectorError("invalid_request", "name must be a nonempty bounded string")
        if correlation is not None and (
            not isinstance(correlation, str) or not 1 <= len(correlation) <= 256
        ):
            raise ConnectorError("invalid_request", "Invalid correlationId")
        if len(self.subscriptions) >= 32:
            raise ConnectorError("capacity", "At most 32 browser subscriptions are allowed")
        key = uuid.uuid4().hex
        # One runtime handler fans out by event name, retaining exact session identity.
        session.set_handler(name, lambda data: self._dispatch(name, session, data))
        self.subscriptions[key] = Subscription(session, name, correlation)
        return {"ok": True, "subscriptionId": key}

    def unsubscribe(self, body: dict) -> dict:
        key = body.get("subscriptionId")
        if not isinstance(key, str):
            raise ConnectorError("invalid_request", "subscriptionId is required")
        subscription = self.subscriptions.pop(key, None)
        if subscription:
            subscription.error = ConnectorError("cancelled", "Subscription removed")
            while not subscription.queue.empty():
                subscription.queue.get_nowait()
            subscription.queue.put_nowait(None)
            if not any(s.name == subscription.name for s in self.subscriptions.values()):
                subscription.session.remove_handler(subscription.name)
        return {"ok": True}

    async def wait(self, body: dict) -> dict:
        key = body.get("subscriptionId")
        if not isinstance(key, str) or key not in self.subscriptions:
            raise ConnectorError("subscription_unavailable", "Subscription is unavailable")
        subscription = self.subscriptions[key]
        if subscription.waiting:
            raise ConnectorError("busy", "Subscription already has a waiter")
        timeout = timeout_seconds(body, 30000)
        subscription.waiting = True
        try:
            if subscription.error:
                raise subscription.error
            if not subscription.session.is_connected:
                raise ConnectorError("browser_disconnected", "Original browser disconnected")
            try:
                async with asyncio.timeout(timeout):
                    event = await subscription.queue.get()
            except TimeoutError as error:
                raise ConnectorError("timeout", "No browser event before deadline") from error
            if subscription.error:
                raise subscription.error
            return {"ok": True, "event": event}
        finally:
            subscription.waiting = False

    async def execute(self, body: dict) -> dict:
        session = self._session()
        code = body.get("code")
        if not isinstance(code, str) or not code or len(code) > 262144:
            raise ConnectorError("invalid_request", "code must be a nonempty bounded string")
        timeout = timeout_seconds(body, 10000)
        tool_call_id = body.get("toolCallId")
        if tool_call_id is not None and (
            not isinstance(tool_call_id, str) or not 1 <= len(tool_call_id) <= 1024
        ):
            raise ConnectorError("invalid_request", "Invalid toolCallId")
        nonce = uuid.uuid4().hex if tool_call_id is not None else None
        if nonce is not None:
            # Exact-owner arrival uses the independent chat transport; reserve at
            # least half the server budget for body/result delivery, never retry.
            ready_ms = max(1, min(1000, int(timeout * 500)))
            code = inline_execution(code, tool_call_id, nonce, ready_ms)
        try:
            value = await session.execute(code, timeout=timeout)
            if nonce is None:
                return {"ok": True, "value": value}
            if (
                not isinstance(value, dict)
                or value.get("execution") != nonce
                or type(value.get("ok")) is not bool
                or (value["ok"] and "value" not in value)
            ):
                raise ConnectorError("protocol", "Invalid browser execution result", uncertain=True)
            result = {"ok": value["ok"]}
            if value["ok"]:
                result["value"] = value["value"]
            else:
                before_body = value.get("phase") == "readiness"
                result["error"] = {
                    "code": "ui_unavailable" if before_body else "javascript_error",
                    "message": (
                        "Inline UI owner unavailable before execution; JavaScript body was not run"
                        if before_body
                        else "Browser JavaScript failed; effects may have occurred"
                    ),
                    "uncertain": not before_body,
                }
            if value.get("materialized") is True:
                result["ui"] = {"blockId": tool_call_id, "toolCallId": tool_call_id}
            return result
        except TimeoutError as error:
            raise ConnectorError(
                "timeout", "JavaScript deadline expired; effects may continue", uncertain=True
            ) from error
        except (asyncio.CancelledError, ConnectorError):
            raise
        except Exception as error:
            # Public runtime exceptions have safe messages, but JS error stacks can
            # contain arbitrary page values. Expose class only; never credential URLs.
            raise ConnectorError(
                "javascript_error"
                if type(error).__name__ == "JavaScriptError"
                else "browser_disconnected",
                f"Browser execution failed ({type(error).__name__}); effects may have occurred",
                uncertain=True,
            ) from error
