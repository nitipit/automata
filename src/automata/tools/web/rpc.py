"""Bounded asynchronous JSONL transport for one owned Pi RPC subprocess."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import uuid
from collections.abc import Callable, Sequence
from typing import Any


class RpcError(RuntimeError):
    """Pi rejected a command or its owned transport failed."""


class RpcRejected(RpcError):
    """Pi returned a correlated, negative command response."""


class PiRpc:
    def __init__(self, on_event: Callable[[dict], None]):
        self.on_event = on_event
        self.process: asyncio.subprocess.Process | None = None
        self.pending: dict[str, asyncio.Future] = {}
        self._write_lock = asyncio.Lock()
        self._reader: asyncio.Task | None = None
        self._stderr: asyncio.Task | None = None
        self._closed = False
        self._close_task: asyncio.Task | None = None

    async def start(self, argv: Sequence[str], *, cwd=None, env=None) -> None:
        if self.process is not None or self._closed:
            raise RpcError("RPC transport cannot be restarted")
        creating = asyncio.create_task(
            asyncio.create_subprocess_exec(
                *argv,
                cwd=cwd,
                env={**os.environ, **(env or {})},
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=4 * 1024 * 1024,
            )
        )
        try:
            self.process = await asyncio.shield(creating)
        except asyncio.CancelledError:
            # Cancellation concurrent with fork must not lose the process handle.
            self.process = await creating
            await self.close()
            raise
        self._reader = asyncio.create_task(self._read())
        self._stderr = asyncio.create_task(self._drain_stderr())

    async def _drain_stderr(self) -> None:
        # Drain continuously, but never echo possibly credential-bearing diagnostics.
        assert self.process and self.process.stderr
        while await self.process.stderr.read(8192):
            pass

    async def _read(self) -> None:
        assert self.process and self.process.stdout
        reason = "Pi RPC exited"
        try:
            while line := await self.process.stdout.readline():
                # StreamReader splits LF only; U+2028/U+2029 stay inside JSON strings.
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("RPC record is not an object")
                if record.get("type") == "response":
                    future = self.pending.get(record.get("id"))
                    if future is not None and not future.done():
                        future.set_result(record)
                else:
                    self.on_event(record)
        except (ValueError, OSError) as error:
            reason = f"Pi RPC protocol failure: {type(error).__name__}"
        finally:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(RpcError(reason))
            if not self._closed:
                self.on_event({"type": "host_rpc_exit", "error": reason})

    async def send(self, record: dict, *, timeout: float = 5) -> None:
        process = self.process
        if self._closed or process is None or process.returncode is not None:
            raise RpcError("Pi RPC is unavailable")
        assert process.stdin
        try:
            # Covers BOTH lock acquisition and pipe backpressure. Direct native UI
            # responses use this too; they have no command-response outer deadline.
            async with asyncio.timeout(timeout):
                async with self._write_lock:
                    if self._closed:
                        raise RpcError("Pi RPC is unavailable")
                    process.stdin.write(json.dumps(record, ensure_ascii=False).encode() + b"\n")
                    await process.stdin.drain()
        except TimeoutError as error:
            raise RpcError("Pi RPC write deadline expired; delivery outcome uncertain") from error
        except (BrokenPipeError, ConnectionResetError) as error:
            raise RpcError("Pi RPC input closed; delivery outcome uncertain") from error

    async def command(self, kind: str, *, timeout: float = 15, **data) -> Any:
        if len(self.pending) >= 64:
            raise RpcError("Too many pending RPC commands")
        request_id = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        try:
            async with asyncio.timeout(timeout):
                await self.send({"type": kind, "id": request_id, **data})
                result = await future
            if not result.get("success"):
                raise RpcRejected(result.get("error", "Pi rejected command"))
            return result.get("data")
        finally:
            self.pending.pop(request_id, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()  # Observe a transport error concurrent with write cancellation.

    async def close(self, *, timeout: float = 2) -> None:
        # Shield owned cleanup: cancelling a caller must not abandon a live child.
        if self._close_task is None:
            self._closed = True
            self._close_task = asyncio.create_task(self._close(timeout))
        await asyncio.shield(self._close_task)

    async def _close(self, timeout: float) -> None:
        process = self.process
        for future in self.pending.values():
            if not future.done():
                future.set_exception(RpcError("Pi RPC closing"))
        try:
            if process is not None:
                if process.stdin:
                    process.stdin.close()
                try:
                    await asyncio.wait_for(process.wait(), timeout)
                except TimeoutError:
                    with contextlib.suppress(ProcessLookupError):
                        process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout)
                    except TimeoutError:
                        with contextlib.suppress(ProcessLookupError):
                            process.kill()
                        try:
                            await asyncio.wait_for(process.wait(), timeout)
                        except TimeoutError as error:
                            raise RpcError(
                                "Pi did not report exit after kill; cleanup unconfirmed"
                            ) from error
        finally:
            for task in (self._reader, self._stderr):
                if task is not None:
                    task.cancel()
            await asyncio.gather(
                *(t for t in (self._reader, self._stderr) if t is not None),
                return_exceptions=True,
            )
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(RpcError("Pi RPC closed"))
