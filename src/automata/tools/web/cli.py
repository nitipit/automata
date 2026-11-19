"""Web UI commands; optional Web UI dependencies are loaded only on execution."""

import json
import os
import subprocess
from contextvars import ContextVar
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

web = App(help="Open applications on the checkout's Web UI server.")
chat = App(help="Manage native Pi chat sessions.")
web.command(chat, name="chat")
app = web.meta
_config: ContextVar[Path | None] = ContextVar("web_ui_config", default=None)


@app.default
def entry(
    *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
    config: Annotated[
        Path | None, Parameter(help="Select a ShelfDB preferences directory.")
    ] = None,
):
    """Select settings for this invocation; do not save command-line overrides."""
    token = _config.set(config)
    try:
        web(tokens, result_action="return_value")
    finally:
        _config.reset(token)


def checkout_root(cwd: Path) -> Path:
    """Treat a linked Git worktree as its own checkout; outside Git use the directory."""
    cwd = cwd.resolve(strict=True)
    if not cwd.is_dir():
        raise ValueError("Expected a working directory")
    result = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        capture_output=True,
        timeout=5,
        env={**os.environ, "LC_ALL": "C"},
    )
    if result.returncode == 0:
        return Path(os.fsdecode(result.stdout.removesuffix(b"\n"))).resolve(strict=True)
    if b"not a git repository" in result.stderr:
        return cwd
    raise ValueError("Unable to identify this Git checkout")


@chat.command(name="new")
def new(
    *,
    cwd: Path | None = None,
    provider: str | None = None,
    model: str | None = None,
    thinking: str | None = None,
    as_json: Annotated[bool, Parameter(name="--json")] = False,
) -> None:
    """Create a native session on this checkout's server and open the configured Firefox."""
    try:
        from .browser import BrowserError, open_browser, preflight_browser
        from .config import ConfigError, WebConfig, load_config
        from .server import ServerError, find_or_start
    except ModuleNotFoundError:
        if as_json:
            print(
                json.dumps(
                    {
                        "error": "web_dependencies_missing",
                        "session_id": None,
                        "browser_connected": False,
                    }
                )
            )
            raise SystemExit(1) from None
        raise SystemExit("Web UI requires the automata[web] dependencies.") from None

    result = {"session_id": None, "browser_connected": False}
    try:
        config = load_config(_config.get())
        prefs = dict(config)
        prefs.update(
            {
                k: v
                for k, v in {"provider": provider, "model": model, "thinking": thinking}.items()
                if v is not None
            }
        )
        try:
            effective = WebConfig({k: v for k, v in prefs.items() if v is not None})
        except (ValueError, WebConfig.Error):
            raise ConfigError("invalid effective configuration") from None
        try:
            root = checkout_root(cwd or Path.cwd())
        except (ValueError, OSError, subprocess.TimeoutExpired):
            raise ConfigError("Invalid checkout") from None
        target = preflight_browser(
            Path(effective.browser_profile) if effective.browser_profile else None
        )
        options = {k: getattr(effective, k) for k in ("provider", "model", "thinking")}
        endpoint = find_or_start(root)
        admission = endpoint.new_session(**options)
        result["session_id"] = admission.session_id
        open_browser(target, admission.url)
        result["browser_connected"] = endpoint.wait_connected(admission.session_id, timeout=12)
        if not result["browser_connected"]:
            result["error"] = "browser_connection_unconfirmed"
    except BrowserError:
        result["error"] = "browser_open_failed" if result["session_id"] else "browser_unavailable"
    except ConfigError:
        result["error"] = "invalid_configuration"
    except ServerError as exc:
        result["error"] = exc.code
    if as_json:
        print(json.dumps(result, sort_keys=True))
    else:
        if result["session_id"]:
            print(f"Session: {result['session_id']}")
        print("Browser connected." if result["browser_connected"] else f"Web UI: {result['error']}")
    if not result["browser_connected"]:
        raise SystemExit(1)
