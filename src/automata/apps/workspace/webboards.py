"""One explicitly provisioned public board; no filesystem or identity discovery."""

import os
import stat
from pathlib import Path

from fastapi.responses import JSONResponse, Response

# Storage identity is deliberately not derived from the directory slug.
PROJECT_ID = "project-northstar"
BOARD_ID = "main"
PUBLIC_PATH = "/boards/project-northstar/main/"
ASSETS = {"index.html": "text/html", "board.css": "text/css", "board.js": "text/javascript"}
BOARD_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'none'; "
    "img-src 'none'; font-src 'none'; media-src 'none'; object-src 'none'; "
    "frame-src 'none'; worker-src 'none'; form-action 'none'; base-uri 'none'; "
    "frame-ancestors 'self'; sandbox allow-scripts"
)


def read_asset(runtime: Path, name: str) -> bytes:
    """Walk fixed directories using no-follow descriptors, including every ancestor
    below the operator-owned runtime. Never follow board-authored symlinks; retain
    descriptors across reads to avoid path check/open races.
    """
    if name not in ASSETS:
        raise ValueError("Unknown public asset")
    directory = os.open(runtime, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in ("northstar", "main", "web"):
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 256_000:
                raise ValueError("Not a bounded regular public asset")
            content = stream.read(256_001)
            if len(content) > 256_000:
                raise ValueError("Public asset too large")
            return content
    finally:
        os.close(directory)


def public_asset(runtime: Path, name: str) -> Response:
    try:
        content = read_asset(runtime, name)
    except (OSError, ValueError):
        return JSONResponse({"detail": "Board asset unavailable"}, status_code=404)
    return Response(content, media_type=ASSETS[name], headers={
        "Content-Security-Policy": BOARD_CSP,
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": ("camera=(), microphone=(), geolocation=(), "
                               "clipboard-read=(), clipboard-write=()"),
    })
