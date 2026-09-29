"""Loopback skill preview: shared Jinja views, explicit assets, one watcher/SSE."""

import asyncio
import hashlib
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from watchfiles import awatch

from .content import SOURCE, discover, lookup, render_markdown, url_slug

BUNDLES = {
    "prism.js": "db64933eccbb6f8edb10f1d0e0a94c1d5d4889fbc1c3705096a17dad9ffef8a2",
    "adaptive-ui.js": "c6642917e2be4da690c8c565d91f12e065c6e10247414bae67f2ca914b3ccc9a",
    "mermaid.js": "d0830a6c05546e9edb8fe20a8f545f3e0dc7c4c3134d584bad9c13a99d7a71e0",
}


def create_app(selector=None, all_skills=False, root=SOURCE):
    """Read canonical content on requests; never write source or build output.

    Only discovered documents and explicit shared assets are public. Templates
    inherit privately; HTML is always rendered, never returned as source files.
    This is a local development preview, not a production hosting boundary.
    """
    root = Path(root).resolve()
    skills, templates = root / "skills", root / "templates"
    if any(not directory.resolve().is_relative_to(root) for directory in (skills, templates)):
        raise ValueError("Content directory escapes app root")
    discover(skills, selector, all_skills)  # Fail selection errors before startup.
    for name, digest in BUNDLES.items():
        bundle = (templates / "lib" / name).resolve()
        if not bundle.is_relative_to(templates.resolve()):
            raise ValueError("Bundle escapes template root")
        if hashlib.sha256(bundle.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Unreviewed local bundle: {name}")
    class TemplateLoader(FileSystemLoader):
        def get_source(self, environment, template):
            if not (root / template).resolve().is_relative_to(templates.resolve()):
                raise TemplateNotFound(template)
            return super().get_source(environment, template)

    environment = Environment(
        loader=TemplateLoader(root), autoescape=select_autoescape(("html",))
    )
    subscribers: set[asyncio.Queue] = set()

    async def watch():
        async for _changes in awatch(skills, templates):
            for queue in tuple(subscribers):
                if queue.empty():
                    queue.put_nowait(True)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(watch())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    def safe_file(path: Path, owner: Path) -> Path:
        resolved = path.resolve()
        if (not resolved.is_relative_to(root)
                or not resolved.is_relative_to(owner.resolve()) or not resolved.is_file()):
            raise HTTPException(404, "Not found")
        return resolved

    def render(template, **context):
        # Template names below are constants, never user-supplied paths.
        return HTMLResponse(environment.get_template(template).render(**context))

    @app.get("/__skill_builder/events")
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
            stream(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/{path:path}")
    def public(path: str, name: str = "", reference: str = ""):
        try:
            if any(not directory.resolve().is_relative_to(root)
                   for directory in (skills, templates)):
                raise HTTPException(404, "Not found")
            pages = discover(skills, selector, all_skills)
            if path == "templates/index.html":
                return render(
                    "templates/catalog.html",
                    landings=[p for p in discover(skills, None, True) if p.document == "SKILL.md"],
                )
            page = None
            if path == "templates/skill.html":
                page = lookup(pages, name)
            elif path == "templates/reference.html":
                page = lookup(pages, name, reference)
                if page.document == "SKILL.md":
                    raise ValueError("Not a reference")
            else:
                page = next((p for p in pages if path == p.url.lstrip("/") or (
                    p.url.endswith("/") and path == p.url.lstrip("/") + "index.html"
                )), None)
            if page is not None:
                safe_file(page.source, skills / page.skill)
                return render(
                    "templates/skill.html", skill=page.skill, title=page.title,
                    document=page.document,
                    navigation=[(p.url.removeprefix(f"/{url_slug(page.skill)}/"), p.title)
                                for p in pages if p.skill == page.skill],
                    raw_source=page.source.read_text(encoding="utf-8"),
                    reference_html=render_markdown(page) if page.document != "SKILL.md" else "",
                )
            # Retain the canonical raw-source URL, not arbitrary Markdown access.
            raw = next((p for p in pages if p.document == "SKILL.md"
                        and path in (f"skills/{p.skill}/SKILL.md",
                                     f"skills/{url_slug(p.skill)}/SKILL.md")), None)
            if raw:
                return FileResponse(safe_file(raw.source, skills / raw.skill),
                                    media_type="text/plain; charset=utf-8",
                                    headers={"Cache-Control": "no-cache"})
            assets = {
                "templates/skill.css.js", "templates/catalog.css.js",
                *(f"templates/lib/{bundle}" for bundle in BUNDLES),
                *(p.relative_to(root).as_posix() for p in (templates / "components").glob("*.js")),
                *(p.relative_to(root).as_posix() for p in (templates / "licenses").glob("*.txt")),
            }
            if path in assets:
                asset = safe_file(root / path, templates)
                if asset.suffix != Path(path).suffix:
                    raise HTTPException(404, "Not found")
                return FileResponse(asset, headers={"Cache-Control": "no-cache"})
        except (ValueError, OSError):
            raise HTTPException(404, "Not found") from None
        raise HTTPException(404, "Not found")

    return app


def serve(selector=None, all_skills=False, port=8788, root=SOURCE):
    import uvicorn

    uvicorn.run(
        create_app(selector, all_skills, root), host="127.0.0.1", port=port,
        timeout_graceful_shutdown=3,  # Bound shutdown even with an open SSE tab.
    )
