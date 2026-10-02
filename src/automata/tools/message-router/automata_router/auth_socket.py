"""Session-bound output and retirement, independent of a stalled routing write."""
from __future__ import annotations

import asyncio
import time
from typing import Any

from .protocol import Connection, json_bytes


class SessionSocket:
    def __init__(self, auth: Any, session: dict, backend: Any, send: Any):
        self.session, self.backend, self.send = session, backend, send
        self.revoked, self.release = auth.watch(session)
        self.connection = Connection(self.emit)
        self.retired = False

    def check(self) -> None:
        if self.revoked.is_set() or self.session["expiresAt"] <= time.time():
            raise ValueError("Session expired or revoked")

    async def emit(self, value: dict) -> None:
        # Gate every caller, including NEW agent replies outside the page's loop.
        # A write already handed to the transport may have effects: never retract it.
        self.check()
        writing = asyncio.create_task(self.send(
            {"type": "websocket.send", "text": json_bytes(value).decode("utf-8")}))
        revoking = asyncio.create_task(self.revoked.wait())
        try:
            await asyncio.wait({writing, revoking}, return_when=asyncio.FIRST_COMPLETED)
            self.check()
            writing.result()
        finally:
            for task in (writing, revoking):
                if not task.done():
                    task.cancel()
            await asyncio.gather(writing, revoking, return_exceptions=True)

    async def retire(self) -> None:
        if self.retired:
            return
        self.retired = True
        # Existing backend removes peer and ALL capabilities before its first
        # notification await. A slow other peer must not keep this identity alive.
        try:
            await asyncio.wait_for(self.backend.disconnected(self.connection), timeout=1)
        except TimeoutError:
            pass  # Notification delivery uncertain; state is already retired.

    async def run(self, serve: Any) -> None:
        serving = asyncio.create_task(serve())
        revoking = asyncio.create_task(self.revoked.wait())
        try:
            await asyncio.wait({serving, revoking}, return_when=asyncio.FIRST_COMPLETED)
            if self.revoked.is_set():
                serving.cancel()
                await self.retire()
                try:
                    await asyncio.wait_for(self.send({"type": "websocket.close", "code": 1008,
                        "reason": "Session expired or revoked"}), timeout=1)
                except Exception:
                    pass  # Closing transport cannot undo already forwarded effects.
            else:
                serving.result()
        finally:
            for task in (serving, revoking):
                if not task.done():
                    task.cancel()
            await asyncio.gather(serving, revoking, return_exceptions=True)

    async def close(self) -> None:
        # Retire this connection's output even on ordinary disconnect. This event
        # does not revoke the persisted session or other independent watchers.
        self.revoked.set()
        try:
            await self.retire()
        finally:
            self.release()
