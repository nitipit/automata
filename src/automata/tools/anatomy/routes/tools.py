"""Read-only tool inventory documents; route IDs distinguish inventory kinds."""

from fastapi import APIRouter, HTTPException, Request

from .. import data
from ..content import discover

router = APIRouter()


def inventory():
    """Project existing file evidence without claiming callable runtime readiness."""
    rows = []
    for item in data.tools():
        kind = "package" if item["kind"] == "Tool package" else "extension"
        rows.append(
            {
                **item,
                "identifier": f"{kind}--{item['name']}",
                "status": "installed"
                if any(c["scope"] != "bundled" for c in item["copies"])
                else "available",
            }
        )
    return rows


@router.get("/tools/")
def index(request: Request):
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="tools/index.html",
        context={"section": "tools", "title": "Tools", "tools": inventory()},
    )


@router.get("/tools/{identifier}/")
def detail(request: Request, identifier: str):
    row = next((row for row in inventory() if row["identifier"] == identifier), None)
    if row is None:
        raise HTTPException(404, "Not found")
    skill_rows, warnings = data.skills()
    canonical = {page.skill for page in discover(request.app.state.skills_root, None, True)}
    related = []
    if row["kind"] == "Tool package":
        for skill in data.capabilities(skill_rows, [row])["items"]:
            declarations = [tool for tool in skill["tools"] if tool.get("package") == row["name"]]
            if declarations:
                related.append(
                    {**skill, "declarations": declarations, "canonical": skill["name"] in canonical}
                )
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="tools/detail.html",
        context={
            "section": "tools",
            "title": row["name"],
            "tool": row,
            "related": related,
            "warnings": warnings,
        },
    )
