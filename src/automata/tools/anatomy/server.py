"""One loopback-only Anatomy server for monitoring and canonical skill reading."""

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from watchfiles import awatch

from .catalog import register_catalog
from .content import SKILLS
from .data import ROOT
from .routes import automata, tools

SITE = ROOT / ".agents/var/tools/automata-anatomy/public"
TEMPLATES = automata.TEMPLATES
PUBLIC_ASSETS = (
    "shared/theme.js",
    "shared/components/anatomy-nav.js",
    "automata/index.css.js",
    "automata/components/monitor.js",
    "automata/components/monitor-state.js",
    "automata/components/activity-chart.js",
    "tools/inventory.js",
)


def create_app(*, skills_root=SKILLS, templates_root=TEMPLATES, site_root=SITE, port=8766):
    skills = Path(skills_root).resolve()
    templates = Path(templates_root).resolve()
    site = Path(site_root).resolve()
    subscribers: set[asyncio.Queue] = set()

    async def watch():
        async for _changes in awatch(skills, templates):
            for queue in tuple(subscribers):
                if queue.empty():
                    queue.put_nowait(True)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(watch())
        app.state.watcher = task
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(
        title="Automata Anatomy", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.port = port
    app.state.skills_root = skills
    app.state.subscribers = subscribers

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

    app.include_router(automata.router)
    app.include_router(tools.router)

    def register_asset(url, path, owner):
        def serve_asset():
            resolved = path.resolve()
            if not resolved.is_relative_to(owner.resolve()) or resolved.suffix != path.suffix:
                return JSONResponse({"detail": "Not found"}, status_code=404)
            if not resolved.is_file():
                return JSONResponse({"detail": "Asset unavailable"}, status_code=503)
            return FileResponse(resolved, media_type="text/javascript")

        app.add_api_route(url, serve_asset, methods=["GET"])

    for asset in PUBLIC_ASSETS:
        register_asset(f"/{asset}", templates / asset, templates)
    # Share the already-reviewed Adaptive UI bundle with both monitor and viewer.
    register_asset("/lib/adaptive-ui.js", templates / "skills/lib/adaptive-ui.js", templates)
    register_asset("/lib/echarts.js", site / "lib/echarts.js", site)
    # The catch-all skill route must be registered last, after monitor and assets.
    environment = register_catalog(app, skills, templates, subscribers)
    app.state.templates = Jinja2Templates(env=environment)
    return app


def serve(port=8766, asset_root=None):
    import uvicorn

    uvicorn.run(
        create_app(port=port, site_root=asset_root or SITE),
        host="127.0.0.1",
        port=port,
        access_log=False,
        proxy_headers=False,
        timeout_graceful_shutdown=3,
    )


if __name__ == "__main__":
    from .cli import app

    app()
