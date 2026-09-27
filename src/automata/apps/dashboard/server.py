"""Loopback-only development dashboard; serves explicit built-asset routes only."""

import argparse
from threading import Lock

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from .activity import make_window
from .data import ROOT, snapshot

SITE = ROOT / ".agents/var/apps/dashboard/public"
PAGE = SITE
app = FastAPI(title="Automata Anatomy", docs_url=None, redoc_url=None, openapi_url=None)
app.state.port = 8766
snapshot_lock = Lock()


@app.middleware("http")
async def local_only(request: Request, call_next):
    address = f"127.0.0.1:{app.state.port}"
    origin = request.headers.get("origin")
    if request.headers.get("host") != address or (origin and origin != f"http://{address}"):
        return JSONResponse({"detail": "Local same-origin access only"}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    )
    return response


@app.get("/")
def index():
    return FileResponse(PAGE / "index.html", media_type="text/html")


@app.get("/app.js")
def javascript():
    return FileResponse(PAGE / "app.js", media_type="text/javascript")


@app.get("/chart.js")
def chart_component():
    return FileResponse(PAGE / "chart.js", media_type="text/javascript")


@app.get("/layout.css")
def layout():
    return FileResponse(PAGE / "layout.css", media_type="text/css")


@app.get("/themes.css")
def themes():
    return FileResponse(PAGE / "themes.css", media_type="text/css")


@app.get("/theme.js")
def theme_module():
    return FileResponse(PAGE / "theme.js", media_type="text/javascript")


@app.get("/lib/adaptive-ui.js")
def adaptive_ui():
    return FileResponse(SITE / "lib/adaptive-ui.js", media_type="text/javascript")


@app.get("/lib/echarts.js")
def echarts():
    file = SITE / "lib/echarts.js"
    if not file.is_file():
        return JSONResponse({"detail": "ECharts asset not installed"}, status_code=503)
    return FileResponse(file, media_type="text/javascript")


@app.get("/api/anatomy")
def anatomy(
    range: str = "7d",
    timezone: str = "Asia/Bangkok",
    skill: str | None = None,
    start: str | None = None,
    end: str | None = None,
):
    try:
        window = make_window(range, timezone, start, end, skill)
    except ValueError as error:
        return JSONResponse({"detail": str(error)}, status_code=422)
    try:
        # Keep the existing ShelfDB reader serialized under FastAPI's thread pool.
        with snapshot_lock:
            return snapshot(window)
    except Exception as error:
        print("Snapshot failed:", type(error).__name__, flush=True)
        return JSONResponse({"detail": "Anatomy sources temporarily unavailable"}, status_code=503)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    app.state.port = args.port
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, proxy_headers=False)
