"""Canonical skill documents, installation evidence and legacy document URLs."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from ..content import discover, lookup, render_markdown, url_slug
from ..data import capabilities, tools
from ..data import skills as installed_skills

router = APIRouter()
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


def render(request, template, **context):
    return request.app.state.templates.TemplateResponse(
        request=request, name=template, context={"section": "skills", **context}
    )


@router.get("/skills/")
def index(request: Request):
    pages = discover(request.app.state.skills_root, None, True)
    setup, warnings = installation()
    canonical_names = {p.skill for p in pages if p.document == "SKILL.md"}
    return render(
        request,
        "skills/catalog.html",
        installed_only=[row for name, row in setup.items() if name not in canonical_names],
        title="Skills",
        landings=[p for p in pages if p.document == "SKILL.md"],
        installation=setup,
        setup_names=SETUP_NAMES,
        warnings=warnings,
    )


# Discovered reference URLs and historical skill URLs are root-relative, so this
# compatibility resolver is deliberately included after all explicit app routes.
# It resolves only discovered documents, never arbitrary filesystem paths/assets.
@router.get("/{path:path}")
def document(request: Request, path: str, name: str = "", reference: str = ""):
    try:
        pages = discover(request.app.state.skills_root, None, True)
        if path in ("templates/index.html", "skills"):
            return RedirectResponse("/skills/", status_code=307)
        if path in ("tools", "activity"):
            return RedirectResponse(f"/{path}/", status_code=307)
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
        # Flat landing pages use exact discovered names, not filesystem paths.
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
            resolved = page.source.resolve()
            if not resolved.is_relative_to(lookup(pages, page.skill).source.parent):
                raise HTTPException(404, "Not found")
            if page.document == "SKILL.md" and flat is None:
                return RedirectResponse(f"/skills/{page.skill}/", status_code=307)
            setup, warnings = installation()
            return render(
                request,
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
            return FileResponse(raw.source, media_type="text/plain; charset=utf-8")
    except (ValueError, OSError):
        raise HTTPException(404, "Not found") from None
    raise HTTPException(404, "Not found")
