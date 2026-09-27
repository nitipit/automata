"""Loopback-only API and explicit public asset routes for the workspace POC."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from threading import RLock
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from .binding import read_binding
from .store import RevisionConflict, WorkspaceStore, append_message

ROOT = Path(__file__).resolve().parents[4]
RUNTIME = Path(os.environ.get("WORKSPACE_RUNTIME_ROOT", ROOT / ".agents/var/apps/workspace"))
SITE = RUNTIME / "web-assets"
store = WorkspaceStore(RUNTIME / "data")
app = FastAPI(title="Workspace POC", docs_url=None, redoc_url=None, openapi_url=None)
app.state.port = int(os.environ.get("WORKSPACE_PORT", "8787"))
write_lock = RLock()


@app.middleware("http")
async def local_only(request: Request, call_next):
    address = f"127.0.0.1:{app.state.port}"
    origin = request.headers.get("origin")
    fetch_site = request.headers.get("sec-fetch-site")
    if (request.headers.get("host") != address or (origin and origin != f"http://{address}")
            or fetch_site not in {None, "same-origin", "none"}):
        return JSONResponse({"detail": "Local same-origin access only"}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    try:
        binding = read_binding()
        websocket = binding["credentials"]["wsUrl"] if binding else ""
    except (OSError, ValueError, TypeError):
        websocket = ""
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        f"connect-src 'self' {websocket}; frame-ancestors 'none'; base-uri 'none'"
    )
    return response


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
    allowed = {"components/text.js", "components/form.js", "components/registry.js",
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
            return store.save(value)
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
