"""Verified profile connection and workspace-owned operation lock."""

import json
import os
import shlex
import sys
from contextlib import contextmanager
from pathlib import Path

# Resolve operational paths from the calling workspace, never from package/install source.
ROOT = Path.cwd().resolve()
PROFILE = (
    Path(os.environ.get("AUTOMATA_LINE_PROFILE", ROOT / ".agents/var/browser/line"))
    .expanduser()
    .resolve()
)
STATE = ROOT / ".agents/var/tools/line"
URL = "chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc/index.html"
ROOM = '[class*="chatroom-module__chatroom__"]'
HEADER = '[class*="chatroomHeader-module__button_name__"]'
PREVIEW = '[class*="pastedImageList-module__image_list_item__"]'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def check_profile_scope():
    """Never mix consumers/tokens when a workspace selects another browser profile."""
    require(sys.platform == "linux", "This tool currently supports Linux only")
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser().resolve()
    for personal in (
        config / "google-chrome",
        config / "chromium",
        config / "google-chrome-beta",
        config / "google-chrome-unstable",
    ):
        require(
            not PROFILE.is_relative_to(personal),
            "Personal/default Chrome profiles are not allowed; use an isolated profile",
        )
    scope = STATE / "profile.json"
    if scope.exists():
        try:
            stored = json.loads(scope.read_text())
        except (ValueError, OSError) as exc:
            raise RuntimeError("Cannot read profile scope; preserve state for inspection") from exc
        require(
            stored == {"version": 1, "profile": str(PROFILE)},
            "Workspace LINE state belongs to another profile; use a separate workspace",
        )


def bind_profile_scope():
    check_profile_scope()
    scope = STATE / "profile.json"
    if not scope.exists():
        # Called under the operation lock, only after a verified LINE page was found.
        from reading_state import atomic, json_bytes

        atomic(scope, json_bytes({"version": 1, "profile": str(PROFILE)}))


def profile_port():
    """Discover the debugging port only from the exact local isolated profile."""
    check_profile_scope()
    ports = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            args = (proc / "cmdline").read_bytes().split(b"\0")
            args = [a.decode() for a in args if a]
            # Chrome can rewrite argv into a single process-title string.
            if len(args) == 1:
                args = shlex.split(args[0])
            executable = (proc / "exe").resolve().name
            if (
                args
                and executable == "chrome"
                and f"--user-data-dir={PROFILE}" in args
                and not any(a.startswith("--type=") for a in args)
            ):
                require(
                    "--remote-debugging-address=127.0.0.1" in args,
                    "Expected loopback debugging address is missing",
                )
                ports.extend(
                    int(a.split("=", 1)[1])
                    for a in args
                    if a.startswith("--remote-debugging-port=")
                )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    require(
        len(ports) == 1 and 0 < ports[0] < 65536,
        "Exactly one Chrome using the configured isolated profile is required",
    )
    return ports[0]


@contextmanager
def locked():
    check_profile_scope()
    import fcntl

    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (STATE / "operation.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


@contextmanager
def connect():
    from line_send import Line
    from playwright.sync_api import sync_playwright

    with locked(), sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{profile_port()}")
        pages = [
            page
            for context in browser.contexts
            for page in context.pages
            if page.url.split("#", 1)[0] == URL
        ]
        require(len(pages) == 1, "Open exactly one LINE extension index page")
        page = pages[0]
        page.set_default_timeout(5000)
        bind_profile_scope()
        yield Line(page)
