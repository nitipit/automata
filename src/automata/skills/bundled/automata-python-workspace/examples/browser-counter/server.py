"""Constrained browser adapter embedding the separately installed generic runtime tool."""

import asyncio
import os
import signal
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from counter import BOOTSTRAP, counter_event, counter_snapshot, counter_state
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from runtime_import import KernelRuntime, WorkspaceServer

ROOT = Path(__file__).resolve().parent
RUN = Path(os.environ.get("WORKSPACE_RUN_DIR", str(ROOT / ".run"))).resolve()
PORT = int(os.environ.get("WORKSPACE_PORT", "8021"))
HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
ORIGINS = {f"http://{host}" for host in HOSTS}
runtime = KernelRuntime(cwd=ROOT, bootstrap=BOOTSTRAP, after_execute="publish_state()")
workspace = WorkspaceServer(RUN, runtime)


@asynccontextmanager
async def lifespan(app):
    await workspace.open()  # Includes owned-kernel cleanup on startup failure.

    async def stop_service():
        await workspace.stop_requested.wait()
        os.kill(os.getpid(), signal.SIGTERM)

    stopper = asyncio.create_task(stop_service())
    try:
        yield
    finally:
        stopper.cancel()
        await asyncio.gather(stopper, return_exceptions=True)
        await workspace.close()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def same_origin(request: Request, call_next):
    if (
        request.headers.get("host") not in HOSTS
        or request.headers.get("origin", next(iter(ORIGINS))) not in ORIGINS
        or request.headers.get("sec-fetch-site") == "cross-site"
    ):
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
    code = {
        "increment": "counter.value += 1",
        "decrement": "counter.value -= 1",
        "set": f"counter.value = {payload.value}",
    }[payload.action]
    try:
        result = await runtime.execute(code, source="browser", timeout=5)
        return {**result, "state": counter_state(result["publication"])}
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.websocket("/events")
async def events(websocket: WebSocket):
    if websocket.headers.get("host") not in HOSTS or websocket.headers.get("origin") not in ORIGINS:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    queue = asyncio.Queue(maxsize=100)
    runtime.listeners.add(queue)
    tasks = []
    try:
        await websocket.send_json({"kind": "snapshot", **counter_snapshot(runtime)})

        async def send():
            while True:
                await websocket.send_json(counter_event(await queue.get()))

        async def receive():
            while True:
                await websocket.receive_text()

        tasks = [asyncio.create_task(send()), asyncio.create_task(receive())]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        runtime.listeners.discard(queue)
