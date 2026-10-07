"""Single authoritative kernel; JSON projections are display caches, never state input."""
import asyncio
import sys
import time
from jupyter_client import AsyncKernelManager

MIME = "application/vnd.python-workspace.state+json"
BOOT = '''
from dataclasses import dataclass
from IPython.display import display
@dataclass
class Counter:
    value: int = 0
counter = Counter()
def publish_state():
    # Fixed primitive projection: never repr an arbitrary user object.
    if type(counter.value) is not int or abs(counter.value) > 10**12:
        raise ValueError("counter.value must be an integer within ±10^12")
    display({"application/vnd.python-workspace.state+json": {
        "count": counter.value, "object_id": str(id(counter))}}, raw=True)
publish_state()
'''


class KernelRuntime:
    def __init__(self):
        self.km = AsyncKernelManager(kernel_name="python3")
        self.client = None
        self.lock = asyncio.Lock()
        self.generation = 0
        self.state = None
        self.busy = False
        self.healthy = False
        self.sequence = 0
        self.listeners = set()
        self.events = []

    def emit(self, kind, source="runtime", **fields):
        self.sequence += 1
        event = dict(seq=self.sequence, kind=kind, source=source,
                     generation=self.generation, time=time.time(), **fields)
        self.events.append(event)
        self.events = self.events[-80:]
        for queue in tuple(self.listeners):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)
        return event

    def view(self):
        return dict(generation=self.generation, state=self.state, busy=self.busy,
                    healthy=self.healthy, events=self.events)

    async def start(self):
        # shutdown_kernel closes the manager's ZMQ context: use a fresh manager.
        self.km = AsyncKernelManager(kernel_name="python3")
        self.km.kernel_spec.argv[0] = sys.executable
        await self.km.start_kernel()
        self.client = self.km.client()
        self.client.start_channels()
        await self.client.wait_for_ready(timeout=15)
        self.generation += 1
        self.healthy = True
        await self._exchange(BOOT, "runtime", 10)
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
        # Interrupt is out-of-band; reset itself joins the serialized queue.
        if self.busy:
            await self.interrupt()
        async with self.lock:
            await self.close()
            self.state = None
            self.emit("state_lost", "python", reason="kernel restart; no code replay")
            await self.start()
            return self.view()

    async def execute(self, code, source="python", timeout=10):
        try:
            await asyncio.wait_for(self.lock.acquire(), 5)
        except asyncio.TimeoutError as exc:
            raise RuntimeError("Queue wait exceeded 5s; code not submitted") from exc
        try:
            if not self.healthy:
                raise RuntimeError("Kernel unresponsive; restart required")
            self.busy = True
            self.emit("busy", source)
            try:
                result = await self._exchange(code, source, timeout)
                # Explicit post-command projection runs even after Python errors.
                # Not a rollback: partial mutations are retained and shown.
                projection = await self._exchange("publish_state()", source, 3)
                if projection["status"] != "ok":
                    self.state = None
                    self.emit("projection_error", source, message=projection["error"])
                self.emit("completed", source, status=result["status"],
                          request_id=result["request_id"], error=result["error"])
                return {**result, "generation": self.generation, "state": self.state}
            except Exception:
                # Infrastructure failure is not a Python exception/transaction.
                self.healthy = False
                self.state = None
                self.emit("state_unknown", source, reason="Execution outcome unknown; restart required")
                raise
            finally:
                self.busy = False
                self.emit("idle", source, healthy=self.healthy)
        finally:
            self.lock.release()

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
                    projection = data.get(MIME)
                    if (isinstance(projection, dict)
                            and type(projection.get("count")) is int
                            and abs(projection["count"]) <= 10**12
                            and isinstance(projection.get("object_id"), str)
                            and len(projection["object_id"]) <= 32):
                        self.state = {"count": projection["count"],
                                      "object_id": projection["object_id"]}
                        self.emit("state", source, state=self.state,
                                  request_id=request_id)
                    text = data.get("text/plain", "")
                elif kind == "stream":
                    text = content.get("text", "")
                elif kind == "error":
                    error = (content.get("ename", "Error") + ": " +
                             content.get("evalue", ""))[:1000]
                    text = error + "\n"
                else:
                    continue
                if budget and isinstance(text, str):
                    piece = text[:budget]
                    chunks.append(piece)
                    budget -= len(piece)

        # Both channels must finish for THIS request before another execution.
        shell = asyncio.create_task(shell_reply())
        iopub = asyncio.create_task(iopub_idle())
        both = asyncio.gather(shell, iopub)
        timed_out = False
        try:
            try:
                reply, _ = await asyncio.wait_for(asyncio.shield(both), timeout)
            except asyncio.TimeoutError:
                timed_out = True
                await self.km.interrupt_kernel()
                self.emit("timeout", source, request_id=request_id)
                try:
                    reply, _ = await asyncio.wait_for(asyncio.shield(both), 3)
                except asyncio.TimeoutError:
                    self.healthy = False
                    raise RuntimeError("Interrupt did not reach reply+idle; restart required")
            return dict(request_id=request_id,
                        status="timeout" if timed_out else reply["status"],
                        error=error, output="".join(chunks), truncated=budget == 0,
                        reply_received=True, idle_received=True)
        finally:
            for task in (shell, iopub):
                if not task.done():
                    task.cancel()
            await asyncio.gather(shell, iopub, return_exceptions=True)
            if both.done() and not both.cancelled():
                both.exception()  # Consume any gathered failure.
