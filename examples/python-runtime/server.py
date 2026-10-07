"""Loopback browser API; arbitrary Python is only available on a private Unix socket."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal

from runtime import KernelRuntime

ROOT = Path(__file__).resolve().parent
RUN = Path(os.environ.get("WORKSPACE_RUN_DIR", str(ROOT / ".run"))).resolve()
SOCKET = RUN / "agent.sock"
PORT = int(os.environ.get("WORKSPACE_PORT", "8021"))
HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
ORIGINS = {f"http://{host}" for host in HOSTS}
runtime = KernelRuntime()
connections = set()


async def agent_connection(reader, writer):
    task = asyncio.current_task()
    connections.add(task)
    try:
        raw = await asyncio.wait_for(reader.readline(), 5)
        message = json.loads(raw)
        command = message.get("command")
        if command == "execute":
            code = message.get("code")
            timeout = message.get("timeout", 10)
            if (not isinstance(code, str) or len(code) > 32000
                    or type(timeout) not in (float, int) or not 0.1 <= timeout <= 30):
                raise ValueError("code <=32000 chars; timeout between 0.1 and 30 seconds")
            result = await runtime.execute(code, timeout=timeout)
        elif command == "status":
            result = runtime.view()
        elif command == "interrupt":
            result = await runtime.interrupt()
        elif command == "restart":
            result = await runtime.restart()
        else:
            raise ValueError("unknown command")
        response = {"ok": True, "result": result}
    except Exception as exc:
        response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:1000]}
    finally:
        if not task.cancelling():
            writer.write((json.dumps(response) + "\n").encode())
            try:
                await writer.drain()
            except ConnectionError:
                pass
        writer.close()
        await writer.wait_closed()
        connections.discard(task)


@asynccontextmanager
async def lifespan(app):
    RUN.mkdir(mode=0o700, exist_ok=True)
    RUN.chmod(0o700)
    # Never unlink a possibly live other process's socket.
    if SOCKET.exists():
        raise RuntimeError(f"Socket exists: {SOCKET}; verify owner stopped before removal")
    agent_server = None
    pid_written = False
    try:
        # Include startup in cleanup: even a partial kernel/socket startup is owned.
        await runtime.start()
        agent_server = await asyncio.start_unix_server(agent_connection, SOCKET, limit=65536)
        SOCKET.chmod(0o600)
        (RUN / "server.pid").write_text(str(os.getpid()))
        pid_written = True
        yield
    finally:
        if agent_server is not None:
            agent_server.close()
            await agent_server.wait_closed()
        for task in tuple(connections):
            task.cancel()
        await asyncio.gather(*tuple(connections), return_exceptions=True)
        try:
            await runtime.close()
        finally:
            # Never remove a preexisting socket/PID that this startup did not own.
            if agent_server is not None:
                SOCKET.unlink(missing_ok=True)
            if pid_written:
                (RUN / "server.pid").unlink(missing_ok=True)


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def same_origin(request: Request, call_next):
    if (request.headers.get("host") not in HOSTS
            or request.headers.get("origin", next(iter(ORIGINS))) not in ORIGINS
            or request.headers.get("sec-fetch-site") == "cross-site"):
        return JSONResponse({"error": "local same-origin access only"}, status_code=403)
    if request.method == "POST" and request.headers.get("origin") not in ORIGINS:
        return JSONResponse({"error": "Origin required"}, status_code=403)
    return await call_next(request)


@app.get("/")
async def index():
    return FileResponse(ROOT / "web" / "index.html")


app.mount("/assets", StaticFiles(directory=ROOT / "browser"), name="assets")


class Action(BaseModel):
    action: Literal["increment", "decrement", "set"]
    value: int = Field(default=0, ge=-(10**12), le=10**12, strict=True)


@app.post("/action")
async def action(payload: Action):
    code = {"increment": "counter.value += 1", "decrement": "counter.value -= 1",
            "set": f"counter.value = {payload.value}"}[payload.action]
    try:
        return await runtime.execute(code, source="browser", timeout=5)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.websocket("/events")
async def events(websocket: WebSocket):
    if (websocket.headers.get("host") not in HOSTS
            or websocket.headers.get("origin") not in ORIGINS):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    queue = asyncio.Queue(maxsize=100)
    runtime.listeners.add(queue)
    try:
        await websocket.send_json({"kind": "snapshot", **runtime.view()})
        # Receiving concurrently notices disconnected idle clients immediately.
        async def send():
            while True:
                await websocket.send_json(await queue.get())
        async def receive():
            while True:
                await websocket.receive_text()
        sender = asyncio.create_task(send())
        receiver = asyncio.create_task(receive())
        done, pending = await asyncio.wait([sender, receiver], return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        runtime.listeners.discard(queue)
