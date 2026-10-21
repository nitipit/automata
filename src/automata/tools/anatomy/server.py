"""Loopback Anatomy application: templates, live reload and closed public assets."""

import asyncio
import hashlib
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from watchfiles import awatch

from .config import SITE, SKILLS, TEMPLATES
from .content import discover
from .routes import monitoring, skills, tools

PUBLIC_ASSETS = (
    "shared/theme.js",
    "shared/components/anatomy-nav.js",
    "shared/components/live-refresh.js",
    "automata/index.css.js",
    "automata/components/monitor.js",
    "automata/components/monitor-state.js",
    "automata/components/activity-chart.js",
    "tools/inventory.js",
)
BUNDLES = {
    "skills/lib/prism.js": "db64933eccbb6f8edb10f1d0e0a94c1d5d4889fbc1c3705096a17dad9ffef8a2",
    "shared/lib/adaptive-ui.js": "c6642917e2be4da690c8c565d91f12e065c6e10247414bae67f2ca914b3ccc9a",
    "skills/lib/mermaid.js": "d0830a6c05546e9edb8fe20a8f545f3e0dc7c4c3134d584bad9c13a99d7a71e0",
}


def template_environment(templates):
    """One autoescaped, root-bounded environment for every document section."""
    class TemplateLoader(FileSystemLoader):
        def get_source(self, environment, template):
            if not (templates / template).resolve().is_relative_to(templates):
                raise TemplateNotFound(template)
            return super().get_source(environment, template)

    return Environment(loader=TemplateLoader(templates), autoescape=select_autoescape(("html",)))


def register_assets(app, templates, site):
    """Publish reviewed assets by exact URL, never mount a source directory."""
    for name, digest in BUNDLES.items():
        bundle = (templates / name).resolve()
        if not bundle.is_relative_to(templates):
            raise ValueError("Bundle escapes template root")
        if hashlib.sha256(bundle.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Unreviewed local bundle: {name}")

    def register(url, path, owner, *, optional=False):
        def serve_asset():
            resolved = path.resolve()
            if not resolved.is_relative_to(owner) or resolved.suffix != path.suffix:
                return JSONResponse({"detail": "Not found"}, status_code=404)
            if not resolved.is_file():
                return JSONResponse(
                    {"detail": "Asset unavailable" if optional else "Not found"},
                    status_code=503 if optional else 404,
                )
            media_type = "text/javascript" if path.suffix == ".js" else None
            return FileResponse(resolved, media_type=media_type)

        app.add_api_route(url, serve_asset, methods=["GET"])

    for asset in PUBLIC_ASSETS:
        register(f"/{asset}", templates / asset, templates, optional=True)
    register("/lib/adaptive-ui.js", templates / "shared/lib/adaptive-ui.js", templates)
    register("/lib/echarts.js", site / "lib/echarts.js", site, optional=True)
    viewer = templates / "skills"
    assets = {
        "templates/skill.css.js": viewer / "skill.css.js",
        "templates/catalog.css.js": viewer / "catalog.css.js",
        **{f"templates/lib/{Path(name).name}": templates / name for name in BUNDLES},
        **{f"templates/components/{p.name}": p for p in (viewer / "components").glob("*.js")},
        **{f"templates/licenses/{p.name}": p for p in (viewer / "licenses").glob("*.txt")},
        # Retain the old public URL for already-open documents and bookmarks.
        "templates/components/live-refresh.js": templates / "shared/components/live-refresh.js",
    }
    for url, path in assets.items():
        owner = viewer if path.is_relative_to(viewer) else templates / "shared"
        register(f"/{url}", path, owner)


def create_app(*, skills_root=SKILLS, templates_root=TEMPLATES, site_root=SITE, port=8766):
    canonical = Path(skills_root).resolve()
    templates = Path(templates_root).resolve()
    site = Path(site_root).resolve()
    discover(canonical, None, True)
    subscribers: set[asyncio.Queue] = set()

    async def watch():
        async for _changes in awatch(canonical, templates):
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
    app.state.skills_root = canonical
    app.state.subscribers = subscribers
    app.state.templates = Jinja2Templates(env=template_environment(templates))

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

    @app.get("/__anatomy/events")
    async def events(request: Request):
        async def stream():
            queue = asyncio.Queue(maxsize=1)
            subscribers.add(queue)
            try:
                yield ": connected\n\n"
                while not await request.is_disconnected():
                    try:
                        await asyncio.wait_for(queue.get(), timeout=15)
                        yield "event: change\ndata: reload\n\n"
                    except TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                subscribers.discard(queue)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    app.include_router(monitoring.router)
    app.include_router(tools.router)
    register_assets(app, templates, site)
    # Root-relative discovered reference/legacy URLs must resolve last.
    app.include_router(skills.router)
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
