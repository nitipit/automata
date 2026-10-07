"""Serialized persistent Python execution. Publications are display data, not authority."""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

from jupyter_client import AsyncKernelManager

PUBLICATION_MIME = "application/vnd.automata.workspace+json"


class KernelRuntime:
    """A trusted kernel with optional explicit, caller-owned bootstrap/publication hooks.

    bootstrap runs at start/reset; after_execute runs after each user command even
    after Python errors. Neither is required; arbitrary commands are never replayed.
    """

    def __init__(self, *, cwd: Path | None = None, bootstrap="", after_execute=""):
        self.cwd = Path(cwd or Path.cwd()).resolve()
        self.bootstrap = bootstrap
        self.after_execute = after_execute
        self.km = AsyncKernelManager(kernel_name="python3", ip="127.0.0.1")
        self.client = None
        self.lock = asyncio.Lock()
        self.runtime_id = str(uuid.uuid4())
        self.generation = 0
        self.publication = None
        self.busy = False
        self.healthy = False
        self.sequence = 0
        self.listeners = set()
        self.events = []

    def emit(self, kind, source="runtime", **fields):
        self.sequence += 1
        event = dict(
            seq=self.sequence,
            kind=kind,
            source=source,
            runtime_id=self.runtime_id,
            generation=self.generation,
            time=time.time(),
            **fields,
        )
        self.events.append(event)
        self.events = self.events[-80:]
        for queue in tuple(self.listeners):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)
        return event

    def view(self):
        return dict(
            runtime_id=self.runtime_id,
            generation=self.generation,
            kernel_pid=getattr(self.km.provisioner, "pid", None),
            publication=self.publication,
            busy=self.busy,
            healthy=self.healthy,
            events=self.events,
        )

    async def start(self):
        # Shutdown closes the manager's ZMQ context: create a fresh manager.
        self.km = AsyncKernelManager(kernel_name="python3", ip="127.0.0.1")
        self.km.kernel_spec.argv[0] = sys.executable
        await self.km.start_kernel(cwd=str(self.cwd))
        self.client = self.km.client()
        self.client.start_channels()
        await self.client.wait_for_ready(timeout=15)
        self.generation += 1
        self.healthy = True
        if self.bootstrap:
            result = await self._exchange(self.bootstrap, "runtime", 10)
            if result["status"] != "ok":
                raise RuntimeError(f"Bootstrap failed: {result['error']}")
        self.emit("ready")

    async def close(self):
        if self.km.has_kernel:
            await self.km.shutdown_kernel(now=True)
        if self.client:
            self.client.stop_channels()
        self.healthy = False

    async def interrupt(self):
        if self.km.has_kernel:
            await self.km.interrupt_kernel()
            self.emit("interrupt", "python")
        return self.view()

    async def restart(self):
        if self.busy:
            await self.interrupt()
        async with self.lock:
            await self.close()
            self.publication = None
            self.emit("state_lost", "python", reason="kernel restart; no command replay")
            try:
                await self.start()
            except BaseException:
                await self.close()
                raise
            return self.view()

    async def execute(self, code, source="python", timeout=10):
        if not isinstance(code, str) or len(code) > 32000:
            raise ValueError("code must be a string of at most 32000 characters")
        if type(timeout) not in (int, float) or not 0.1 <= timeout <= 30:
            raise ValueError("timeout must be 0.1–30 seconds")
        if not isinstance(source, str) or not 1 <= len(source) <= 64:
            raise ValueError("source must be a 1–64 character string")
        try:
            await asyncio.wait_for(self.lock.acquire(), 5)
        except TimeoutError as exc:
            raise RuntimeError("Queue wait exceeded 5s; code not submitted") from exc
        try:
            if not self.healthy:
                raise RuntimeError("Kernel unresponsive; restart required")
            self.busy = True
            self.emit("busy", source)
            try:
                result = await self._exchange(code, source, timeout)
                if self.after_execute:
                    after = await self._exchange(self.after_execute, source, 3)
                    if after["status"] != "ok":
                        self.publication = None
                        self.emit("publication_error", source, message=after["error"])
                        result["after_error"] = after["error"]
                self.emit(
                    "completed",
                    source,
                    status=result["status"],
                    request_id=result["request_id"],
                    error=result["error"],
                )
                return {
                    **result,
                    "runtime_id": self.runtime_id,
                    "generation": self.generation,
                    "publication": self.publication,
                }
            except Exception:
                self.healthy = False
                self.publication = None
                self.emit(
                    "state_unknown", source, reason="Execution outcome unknown; restart required"
                )
                raise
            finally:
                self.busy = False
                self.emit("idle", source, healthy=self.healthy)
        finally:
            self.lock.release()

    def _publish(self, payload, source, request_id):
        try:
            if not isinstance(payload, dict):
                raise ValueError("Publication must be a JSON object")
            encoded = json.dumps(payload, allow_nan=False)
            if len(encoded) > 16384:
                raise ValueError("Publication exceeds 16384 characters")
            # Detached primitive-only display cache; never feed it back into Python.
            self.publication = json.loads(encoded)
            self.emit("publication", source, publication=self.publication, request_id=request_id)
        except (ValueError, TypeError, RecursionError) as exc:
            self.publication = None
            self.emit("publication_error", source, message=str(exc)[:1000])

    async def _exchange(self, code, source, timeout):
        request_id = self.client.execute(code, allow_stdin=False, stop_on_error=True)
        chunks = []
        budget = 8192
        error = None

        async def shell_reply():
            while True:
                msg = await self.client.get_shell_msg(timeout=None)
                if msg.get("parent_header", {}).get("msg_id") == request_id:
                    if msg["msg_type"] == "execute_reply":
                        return msg["content"]

        async def iopub_idle():
            nonlocal budget, error
            while True:
                msg = await self.client.get_iopub_msg(timeout=None)
                if msg.get("parent_header", {}).get("msg_id") != request_id:
                    continue
                content = msg["content"]
                kind = msg["msg_type"]
                if kind == "status" and content["execution_state"] == "idle":
                    return
                if kind in ("display_data", "execute_result"):
                    data = content.get("data", {})
                    if PUBLICATION_MIME in data:
                        self._publish(data[PUBLICATION_MIME], source, request_id)
                    text = data.get("text/plain", "")
                elif kind == "stream":
                    text = content.get("text", "")
                elif kind == "error":
                    error = (content.get("ename", "Error") + ": " + content.get("evalue", ""))[
                        :1000
                    ]
                    text = error + "\n"
                else:
                    continue
                if budget and isinstance(text, str):
                    piece = text[:budget]
                    chunks.append(piece)
                    budget -= len(piece)

        shell = asyncio.create_task(shell_reply())
        iopub = asyncio.create_task(iopub_idle())
        both = asyncio.gather(shell, iopub)
        timed_out = False
        try:
            try:
                reply, _ = await asyncio.wait_for(asyncio.shield(both), timeout)
            except TimeoutError:
                timed_out = True
                await self.km.interrupt_kernel()
                self.emit("timeout", source, request_id=request_id)
                try:
                    reply, _ = await asyncio.wait_for(asyncio.shield(both), 3)
                except TimeoutError as exc:
                    self.healthy = False
                    raise RuntimeError("No reply+idle after interrupt; restart required") from exc
            return dict(
                request_id=request_id,
                status="timeout" if timed_out else reply["status"],
                error=error,
                output="".join(chunks),
                truncated=budget == 0,
                reply_received=True,
                idle_received=True,
            )
        finally:
            for task in (shell, iopub):
                if not task.done():
                    task.cancel()
            await asyncio.gather(shell, iopub, return_exceptions=True)
            if both.done() and not both.cancelled():
                both.exception()
