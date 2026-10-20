"""Canonical skill documents and a closed registry of reviewed viewer assets."""

import asyncio
import hashlib
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from .content import discover, lookup, render_markdown, url_slug
from .data import capabilities, tools
from .data import skills as installed_skills

SETUP_NAMES = {
    "installed": "Installed",
    "available": "Available to install",
    "incomplete": "Incomplete setup",
    "unknown": "Unknown setup",
}


def installation():
    rows, warnings = installed_skills()
    inventory = tools()
    packages = {row["name"] for row in inventory if row["kind"] == "Tool package"}
    projection = capabilities(rows, inventory)["items"]
    for row in projection:
        for tool in row["tools"]:
            tool["has_detail"] = tool.get("package") in packages
    return {row["name"]: row for row in projection}, warnings


BUNDLES = {
    "prism.js": "db64933eccbb6f8edb10f1d0e0a94c1d5d4889fbc1c3705096a17dad9ffef8a2",
    "adaptive-ui.js": "c6642917e2be4da690c8c565d91f12e065c6e10247414bae67f2ca914b3ccc9a",
    "mermaid.js": "d0830a6c05546e9edb8fe20a8f545f3e0dc7c4c3134d584bad9c13a99d7a71e0",
}


def register_catalog(app, skills: Path, templates: Path, subscribers: set):
    """Read canonical content per request, without serving arbitrary directories."""
    viewer = templates / "skills"
    discover(skills, None, True)
    for name, digest in BUNDLES.items():
        bundle = (viewer / "lib" / name).resolve()
        if not bundle.is_relative_to(viewer.resolve()):
            raise ValueError("Bundle escapes template root")
        if hashlib.sha256(bundle.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Unreviewed local bundle: {name}")

    class TemplateLoader(FileSystemLoader):
        def get_source(self, environment, template):
            if not (templates / template).resolve().is_relative_to(templates.resolve()):
                raise TemplateNotFound(template)
            return super().get_source(environment, template)

    environment = Environment(
        loader=TemplateLoader(templates), autoescape=select_autoescape(("html",))
    )
    assets = {
        "templates/skill.css.js": viewer / "skill.css.js",
        "templates/catalog.css.js": viewer / "catalog.css.js",
        **{f"templates/lib/{name}": viewer / "lib" / name for name in BUNDLES},
        **{f"templates/components/{p.name}": p for p in (viewer / "components").glob("*.js")},
        **{f"templates/licenses/{p.name}": p for p in (viewer / "licenses").glob("*.txt")},
    }

    def safe_file(path: Path, owner: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(owner.resolve()) or not resolved.is_file():
            raise HTTPException(404, "Not found")
        return resolved

    def render(template, **context):
        return HTMLResponse(environment.get_template(template).render(section="skills", **context))

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

    @app.get("/{path:path}")
    def public(path: str, name: str = "", reference: str = ""):
        try:
            pages = discover(skills, None, True)
            if path in ("templates/index.html", "skills"):
                return RedirectResponse("/skills/", status_code=307)
            if path in ("tools", "activity"):
                return RedirectResponse(f"/{path}/", status_code=307)
            if path == "skills/":
                setup, warnings = installation()
                canonical_names = {p.skill for p in pages if p.document == "SKILL.md"}
                return render(
                    "skills/catalog.html",
                    installed_only=[
                        row for name, row in setup.items() if name not in canonical_names
                    ],
                    title="Skills",
                    landings=[p for p in pages if p.document == "SKILL.md"],
                    installation=setup,
                    setup_names=SETUP_NAMES,
                    warnings=warnings,
                )
            page = None
            if path == "templates/skill.html":
                page = lookup(pages, name)
            elif path == "templates/reference.html":
                page = lookup(pages, name, reference)
                if page.document == "SKILL.md":
                    raise ValueError("Not a reference")
            else:
                page = next(
                    (
                        p
                        for p in pages
                        if path == p.url.lstrip("/")
                        or (p.url.endswith("/") and path == p.url.lstrip("/") + "index.html")
                    ),
                    None,
                )
            # Flat landing pages use the exact discovered skill name, not a filesystem path.
            flat = next(
                (
                    p
                    for p in pages
                    if p.document == "SKILL.md"
                    and path
                    in (f"skills/{p.skill}/", f"skills/{p.skill}/index.html", f"skills/{p.skill}")
                ),
                None,
            )
            if flat is not None:
                if path != f"skills/{flat.skill}/":
                    return RedirectResponse(f"/skills/{flat.skill}/", status_code=307)
                page = flat
            if page is not None:
                safe_file(page.source, lookup(pages, page.skill).source.parent)
                if page.document == "SKILL.md" and flat is None:
                    return RedirectResponse(f"/skills/{page.skill}/", status_code=307)
                setup, warnings = installation()
                return render(
                    "skills/skill.html",
                    skill=page.skill,
                    title=page.title,
                    document=page.document,
                    navigation=[
                        (f"/skills/{p.skill}/" if p.document == "SKILL.md" else p.url, p.title)
                        for p in pages
                        if p.skill == page.skill
                    ],
                    landing=lookup(pages, page.skill),
                    installation=setup.get(page.skill),
                    setup_names=SETUP_NAMES,
                    warnings=warnings,
                    raw_source=page.source.read_text(encoding="utf-8"),
                    reference_html=render_markdown(page) if page.document != "SKILL.md" else "",
                )
            raw = next(
                (
                    p
                    for p in pages
                    if p.document == "SKILL.md"
                    and path
                    in (f"skills/{p.skill}/SKILL.md", f"skills/{url_slug(p.skill)}/SKILL.md")
                ),
                None,
            )
            if raw:
                return FileResponse(
                    safe_file(raw.source, raw.source.parent), media_type="text/plain; charset=utf-8"
                )
            if path in assets:
                asset = safe_file(assets[path], viewer)
                if asset.suffix != Path(path).suffix:
                    raise HTTPException(404, "Not found")
                return FileResponse(asset)
        except (ValueError, OSError):
            raise HTTPException(404, "Not found") from None
        raise HTTPException(404, "Not found")

    return environment
