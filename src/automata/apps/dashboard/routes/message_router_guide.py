"""Serve only the finished skill reference, without authoring or router access."""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

WEBREF = (
    Path(__file__).resolve().parents[3]
    / "runtimes/pi/skills/automata-message-router/webref"
)
PAGES = ("index", "configure", "connect", "discover", "send", "failures")
MODULES = (
    "components/reference-page.js",
    "components/protocol-diagram.js",
    "components/code-example.js",
    "lib/adaptive-ui.js",
    "lib/mermaid.js",
    *(f"{page}.css.js" for page in PAGES),
)
NOTICES = (
    "automata-LICENSE.txt", "adapter-LICENSE.txt", "arrow-LICENSE.txt",
    "edictor-LICENSE.txt", "mermaid-LICENSE.txt",
    "mermaid-dependencies-LICENSE.txt", "PROVENANCE.txt",
)
router = APIRouter()


def register_asset(name: str, media_type: str) -> None:
    def serve_asset():
        return FileResponse(WEBREF / name, media_type=media_type)

    router.add_api_route(f"/message-router/{name}", serve_asset, methods=["GET"])


for page in PAGES:
    register_asset(f"{page}.html", "text/html")
for module in MODULES:
    register_asset(module, "text/javascript")
for notice in NOTICES:
    register_asset(f"lib/{notice}", "text/plain")
