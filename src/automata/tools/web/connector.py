"""Session-bound browser execution and bounded, correlated event subscriptions."""

from __future__ import annotations

import asyncio
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
        try:
            value = await session.execute(code, timeout=timeout)
            return {"ok": True, "value": value}
        except TimeoutError as error:
            raise ConnectorError(
                "timeout", "JavaScript deadline expired; effects may continue", uncertain=True
            ) from error
        except asyncio.CancelledError:
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
