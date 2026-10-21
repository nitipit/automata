"""Monitoring document and compatible read-only aggregate API."""

from threading import Lock
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from ..activity import make_window
from ..data import snapshot

router = APIRouter()
snapshot_lock = Lock()


@router.get("/")
@router.get("/activity/")
def index(request: Request):
    section = "activity" if request.url.path == "/activity/" else "overview"
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="automata/index.html",
        context={"section": section, "title": "Activity" if section == "activity" else "Overview"},
    )


@router.get("/automata/")
@router.get("/automata/index.html")
def legacy_monitor(request: Request):
    params = dict(request.query_params)
    tab = params.pop("tab", "identity")
    target = {"identity": "/", "capabilities": "/skills/", "statistics": "/activity/"}.get(tab, "/")
    allowed = (
        {"query", "setup"}
        if target == "/skills/"
        else {"range", "timezone", "skill", "limit", "paused", "start", "end"}
    )
    query = urlencode({key: value for key, value in params.items() if key in allowed})
    return RedirectResponse(target + ("?" + query if query else ""), status_code=302)


@router.get("/api/anatomy")
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
