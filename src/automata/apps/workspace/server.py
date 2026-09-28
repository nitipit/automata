"""Loopback-only API and explicit public asset routes for the workspace POC."""

from __future__ import annotations

import argparse
import os
from contextlib import asynccontextmanager
from pathlib import Path
from threading import RLock
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from .binding import read_binding
from .lifecycle import configured_lifecycle
from .receiver import configured_receiver
from .store import RevisionConflict, WorkspaceStore, append_message
from .webboards import BOARD_CSP, PUBLIC_PATH, public_asset

ROOT = Path(__file__).resolve().parents[4]
RUNTIME = Path(os.environ.get("WORKSPACE_RUNTIME_ROOT", ROOT / ".agents/var/apps/workspace"))
SITE = RUNTIME / "web-assets"
store = WorkspaceStore(RUNTIME / "data")
@asynccontextmanager
async def lifespan(app):
    app.state.lifecycle_error = None
    try:
        app.state.lifecycle = configured_lifecycle(RUNTIME)
    except (OSError, ValueError, TypeError):
        app.state.lifecycle = None
        app.state.lifecycle_error = "Private agent configuration requires operator review"
    app.state.receiver = None
    app.state.receiver_error = None
    try:
        app.state.receiver = configured_receiver(store)
        if app.state.receiver:
            app.state.receiver.start()
    except (OSError, ValueError, RuntimeError):
        app.state.receiver_error = "Private app receiver configuration requires operator review"
    try:
        yield
    finally:
        if app.state.receiver:
            app.state.receiver.shutdown()
        if app.state.lifecycle:
            app.state.lifecycle.shutdown()


app = FastAPI(title="Workspace POC", docs_url=None, redoc_url=None,
              openapi_url=None, lifespan=lifespan)
app.state.port = int(os.environ.get("WORKSPACE_PORT", "8787"))
write_lock = RLock()


@app.middleware("http")
async def local_only(request: Request, call_next):
    address = f"127.0.0.1:{app.state.port}"
    origin = request.headers.get("origin")
    fetch_site = request.headers.get("sec-fetch-site")
    board_asset = request.url.path.startswith(PUBLIC_PATH)
    destination = request.headers.get("sec-fetch-dest")
    # Opaque sandbox subresources may have Origin:null / cross-site metadata.
    # Only the fixed public board route accepts them. All APIs reject frame,
    # script, object and other navigations, including same-origin iframe URLs.
    if (request.headers.get("host") != address
            or (not board_asset and (
                (origin and origin != f"http://{address}")
                or fetch_site not in {None, "same-origin", "none"}
                or (request.url.path.startswith("/api/")
                    and destination not in {None, "empty"})
                or destination in {"iframe", "frame", "object", "embed"}))):
        return JSONResponse({"detail": "Local same-origin access only"}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if board_asset:
        response.headers["Content-Security-Policy"] = BOARD_CSP
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
    try:
        binding = read_binding()
        websocket = binding["credentials"]["wsUrl"] if binding else ""
    except (OSError, ValueError, TypeError):
        websocket = ""
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        f"connect-src 'self' {websocket}; frame-src 'self'; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )
    return response


@app.get(PUBLIC_PATH + "{name}", include_in_schema=False)
def board_file(name: str):
    return public_asset(RUNTIME, name)


@app.get("/project-northstar/", include_in_schema=False)
def index():
    return FileResponse(SITE / "index.html", media_type="text/html")


@app.get("/workspace.js", include_in_schema=False)
def javascript():
    return FileResponse(SITE / "workspace.js", media_type="text/javascript")


@app.get("/workspace.css", include_in_schema=False)
def stylesheet():
    return FileResponse(SITE / "workspace.css", media_type="text/css")


@app.get("/workspace-root.css", include_in_schema=False)
def root_stylesheet():
    return FileResponse(SITE / "workspace-root.css", media_type="text/css")


@app.get("/workspace-tokens.css", include_in_schema=False)
def tokens():
    return FileResponse(SITE / "workspace-tokens.css", media_type="text/css")


@app.get("/work-surface.js", include_in_schema=False)
def work_surface_module():
    return FileResponse(SITE / "work-surface.js", media_type="text/javascript")


@app.get("/state-sync.js", include_in_schema=False)
def sync_module():
    return FileResponse(SITE / "state-sync.js", media_type="text/javascript")


@app.get("/conversation-view.js", include_in_schema=False)
def conversation_module():
    return FileResponse(SITE / "conversation-view.js", media_type="text/javascript")


@app.get("/message-composer.js", include_in_schema=False)
def composer_module():
    return FileResponse(SITE / "message-composer.js", media_type="text/javascript")


@app.get("/bottom-controls.js", include_in_schema=False)
def controls_module():
    return FileResponse(SITE / "bottom-controls.js", media_type="text/javascript")


@app.get("/lib/adaptive-ui.js", include_in_schema=False)
def adaptive_ui():
    path = RUNTIME / "lib/adaptive-ui.js"
    if not path.is_file():
        return JSONResponse({"detail": "Asset not built"}, status_code=503)
    return FileResponse(path, media_type="text/javascript")


@app.get("/modules/{module_path:path}", include_in_schema=False)
def component_module(module_path: str):
    # A fixed allowlist, not a generic private/static file server.
    allowed = {"components/text.js", "components/form.js", "components/form-response.js",
               "components/registry.js",
               "conversation/message.js", "agent/connection.js", "agent/conversation.js",
               "router/client.js", "router/protocol.js", "router/legacy-client.js"}
    if module_path not in allowed:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return FileResponse(SITE / module_path, media_type="text/javascript")


@app.get("/api/agent-binding")
def agent_binding(request: Request):
    if request.headers.get("sec-fetch-site") != "same-origin":
        return JSONResponse({"detail": "Same-origin browser bootstrap only"}, status_code=403)
    try:
        return {"binding": read_binding()}
    except (OSError, ValueError, TypeError):
        return JSONResponse({"detail": "Explicit agent binding unavailable"}, status_code=503)


@app.get("/api/agent-lifecycle")
def agent_lifecycle(request: Request):
    if request.headers.get("sec-fetch-site") != "same-origin":
        return JSONResponse({"detail": "Same-origin browser only"}, status_code=403)
    lifecycle = getattr(app.state, "lifecycle", None)
    if not lifecycle:
        error = getattr(app.state, "lifecycle_error", None)
        return {"configured": False, "phase": "failed" if error else "offline",
                "action": None, "detail": error or ""}
    binding = read_binding()
    if not binding or (binding["agentId"], binding["to"]) != (
            lifecycle.config.agent_id, lifecycle.config.participant):
        return JSONResponse({"detail": "Lifecycle assignment mismatch"}, status_code=503)
    return lifecycle.status()


@app.post("/api/agent-lifecycle/{action}")
def launch_agent(action: str, value: dict, request: Request):
    if request.headers.get("sec-fetch-site") != "same-origin":
        return JSONResponse({"detail": "Same-origin browser only"}, status_code=403)
    lifecycle = getattr(app.state, "lifecycle", None)
    if not lifecycle:
        return JSONResponse({"detail": "Agent launch is not configured"}, status_code=409)
    binding = read_binding()
    if (not binding or value != {"agentId": lifecycle.config.agent_id}
            or (binding["agentId"], binding["to"]) != (
                lifecycle.config.agent_id, lifecycle.config.participant)):
        return JSONResponse({"detail": "Only the configured agent may be launched"},
                            status_code=422)
    try:
        return lifecycle.launch(action)
    except (OSError, ValueError, RuntimeError):
        detail = "Launch rejected; inspect private configuration or saved session"
        return JSONResponse({"detail": detail}, status_code=409)


@app.get("/api/state")
def get_state():
    try:
        with write_lock:
            return store.load()
    except (OSError, RuntimeError, ValueError) as error:
        print("Workspace read failed:", type(error).__name__, flush=True)
        return JSONResponse({"detail": "Saved workspace state could not be read"}, status_code=503)


@app.put("/api/state")
def put_state(value: dict[str, Any]):
    try:
        with write_lock:
            return store.save(value, browser=True)
    except RevisionConflict as error:
        return JSONResponse(
            {"detail": str(error), "currentRevision": error.current_revision},
            status_code=409,
        )
    except ValueError as error:
        return JSONResponse({"detail": str(error)}, status_code=422)
    except (OSError, RuntimeError) as error:
        print("Workspace write failed:", type(error).__name__, flush=True)
        return JSONResponse({"detail": "Workspace changes were not saved"}, status_code=503)


@app.get("/api/conversation-posts")
def post_status():
    receiver = getattr(app.state, "receiver", None)
    error = getattr(app.state, "receiver_error", None)
    return {"receiver": receiver.status() if receiver else {
        "configured": False, "phase": "failed" if error else "offline"},
        "detail": error or ""}


@app.post("/api/conversation-posts")
def save_user_post(value: dict[str, Any], request: Request):
    if request.headers.get("sec-fetch-site") != "same-origin":
        return JSONResponse({"detail": "Same-origin browser only"}, status_code=403)
    try:
        # Never accept payload/router provenance from this human-browser route.
        return store.post(value)
    except (ValueError, TypeError) as error:
        return JSONResponse({"detail": str(error)}, status_code=422)
    except (OSError, RuntimeError):
        return JSONResponse({"detail": (
            "Save outcome uncertain; do not deliver or replay automatically")}, status_code=503)


@app.post("/api/conversations/{conversation_id}/messages")
def send_message(conversation_id: str, value: dict[str, Any]):
    try:
        with write_lock:
            if value.get("conversationId") != conversation_id:
                return JSONResponse(
                    {"detail": "Conversation path does not match envelope"}, status_code=422
                )
            state, duplicate = append_message(store, value)
        return {"state": state, "duplicate": duplicate}
    except ValueError as error:
        return JSONResponse({"detail": str(error)}, status_code=422)
    except (OSError, RuntimeError) as error:
        print("Simulated delivery/storage failed:", type(error).__name__, flush=True)
        return JSONResponse(
            {"detail": "Delivery or save outcome may be uncertain; do not resend automatically"},
            status_code=503,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    app.state.port = args.port
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, proxy_headers=False)


if __name__ == "__main__":
    main()
