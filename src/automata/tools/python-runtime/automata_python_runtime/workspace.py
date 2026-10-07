"""Private Unix workspace transport and lifecycle; no browser/network execution API."""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
from pathlib import Path

from .kernel import KernelRuntime


async def request(message, workspace: Path):
    """One independent request. A lost reply may mean executed code; never auto-replay."""
    socket = Path(workspace).expanduser().resolve() / "agent.sock"
    reader, writer = await asyncio.open_unix_connection(str(socket), limit=2_000_000)
    try:
        encoded = json.dumps(message) + "\n"
        if len(encoded.encode()) > 65536:
            raise ValueError("Request exceeds 65536 bytes")
        writer.write(encoded.encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.readline(), 60)
        if not raw:
            raise RuntimeError("No reply; outcome unknown; do not replay code")
        return json.loads(raw)
    finally:
        writer.close()
        await writer.wait_closed()


class WorkspaceServer:
    """Embed with a KernelRuntime adapter, or use the blank-kernel CLI serve command."""

    def __init__(self, workspace: Path, runtime: KernelRuntime):
        self.workspace = Path(workspace).expanduser().resolve()
        self.socket = self.workspace / "agent.sock"
        self.runtime = runtime
        self.server = None
        self.lock_file = None
        self.pid_written = False
        self.connections = set()
        self.stop_requested = asyncio.Event()

    async def open(self):
        if len(os.fsencode(self.socket)) >= 108:
            raise ValueError(
                "Unix socket path must be shorter than 108 bytes; choose a shorter workspace"
            )
        self.workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.workspace.chmod(0o700)
        self.lock_file = (self.workspace / "owner.lock").open("a+")
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.lock_file.close()
            self.lock_file = None
            raise RuntimeError("Workspace already owned by a running server") from exc
        try:
            if self.socket.exists():
                raise RuntimeError(
                    "Socket exists; verify previous owner stopped before stale cleanup"
                )
            await self.runtime.start()
            self.server = await asyncio.start_unix_server(
                self._connection, self.socket, limit=65536
            )
            self.socket.chmod(0o600)
            (self.workspace / "server.pid").write_text(str(os.getpid()))
            self.pid_written = True
        except BaseException:
            await self.close()
            raise

    async def close(self):
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
        tasks = tuple(self.connections)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await self.runtime.close()
        finally:
            if self.server is not None:
                self.socket.unlink(missing_ok=True)
                self.server = None
            if self.pid_written:
                (self.workspace / "server.pid").unlink(missing_ok=True)
                self.pid_written = False
            if self.lock_file is not None:
                self.lock_file.close()
                self.lock_file = None

    async def _connection(self, reader, writer):
        task = asyncio.current_task()
        self.connections.add(task)
        command = None
        try:
            raw = await asyncio.wait_for(reader.readline(), 5)
            message = json.loads(raw)
            if not isinstance(message, dict):
                raise ValueError("Request must be a JSON object")
            command = message.get("command")
            if command == "execute":
                result = await self.runtime.execute(
                    message.get("code"), timeout=message.get("timeout", 10)
                )
            elif command == "status":
                result = self.runtime.view()
            elif command == "interrupt":
                result = await self.runtime.interrupt()
            elif command == "restart":
                result = await self.runtime.restart()
            elif command == "stop":
                result = {"stopping": True, "runtime_id": self.runtime.runtime_id}
            else:
                raise ValueError("Unknown command; use execute/status/interrupt/restart/stop")
            response = {"ok": True, "result": result}
        except Exception as exc:
            response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:1000]}
        finally:
            try:
                if not task.cancelling():
                    writer.write((json.dumps(response) + "\n").encode())
                    await writer.drain()
                    if command == "stop" and response["ok"]:
                        self.stop_requested.set()
            except ConnectionError:
                pass
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except ConnectionError:
                    pass
                self.connections.discard(task)
