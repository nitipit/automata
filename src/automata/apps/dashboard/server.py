"""Loopback-only Jinja application with a closed public JavaScript registry."""
import argparse

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from .data import ROOT
from .routes import automata, message_router_guide

SITE = ROOT / ".agents/var/apps/dashboard/public"
TEMPLATES = message_router_guide.TEMPLATES
app = FastAPI(title="Automata Anatomy", docs_url=None, redoc_url=None, openapi_url=None)
app.state.port = 8766


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
@app.get("/automata/")
def index():
    return RedirectResponse("/automata/index.html", status_code=302)


@app.get("/message-router/")
def guide_index():
    return RedirectResponse("/message-router/configure.html", status_code=302)


app.include_router(automata.router)
app.include_router(message_router_guide.router)

# Public-safe maintained assets only. Never mount templates or a filesystem tree.
PUBLIC_ASSETS = (
    "shared/theme.js", "shared/components/anatomy-nav.js",
    "automata/index.css.js", "automata/components/monitor.js",
    "automata/components/monitor-state.js",
    "automata/components/activity-chart.js",
    "message-router/components/protocol-diagram.js",
    "message-router/components/code-example.js",
    *(f"message-router/{page}.css.js" for page in message_router_guide.PAGES),
)


def register_asset(url, path):
    def serve_asset():
        if not path.is_file():
            return JSONResponse({"detail": "Asset unavailable"}, status_code=503)
        return FileResponse(path, media_type="text/javascript")
    app.add_api_route(url, serve_asset, methods=["GET"])


for asset in PUBLIC_ASSETS:
    register_asset(f"/{asset}", TEMPLATES / asset)
for library in ("adaptive-ui", "echarts", "mermaid"):
    register_asset(f"/lib/{library}.js", SITE / "lib" / f"{library}.js")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    app.state.port = args.port
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, proxy_headers=False)
