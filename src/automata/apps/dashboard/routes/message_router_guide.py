"""Static learning material only: no router connections or credential access."""
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=TEMPLATES)
router = APIRouter()
PAGES = {
    "configure": ("Configure", "Decide who may start a message."),
    "connect": ("Connect", "Authenticate each client to one central router."),
    "discover": ("Discover", "Inspect your own allowed destinations."),
    "send": ("Send", "Start a message, then choose whether it needs a reply."),
    "failures": ("Handle failures", "Distinguish rejection from uncertain delivery."),
}


def register_page(slug, title, goal):
    def page(request: Request):
        return templates.TemplateResponse(request=request, name=f"message-router/{slug}.html",
                                          context={"section": "message-router", "page": slug,
                                                   "title": title, "goal": goal, "pages": PAGES})
    router.add_api_route(f"/message-router/{slug}.html", page, methods=["GET"], name=slug)


for slug, (title, goal) in PAGES.items():
    register_page(slug, title, goal)
