"""Monitoring document and compatible read-only aggregate API."""
from threading import Lock

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..activity import make_window
from ..data import snapshot
from .message_router_guide import templates

router = APIRouter()
snapshot_lock = Lock()


@router.get("/automata/index.html")
def index(request: Request):
    return templates.TemplateResponse(request=request, name="automata/index.html",
                                      context={"section": "automata", "title": "Automata"})


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
