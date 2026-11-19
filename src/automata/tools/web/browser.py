"""Dispatch a Web UI navigation ticket to one exact Firefox profile."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from .config import _config_home


class BrowserError(RuntimeError):
    """Firefox targeting or launch failed without exposing the URL."""


@dataclass(frozen=True)
class FirefoxTarget:
    """Resolved executable and existing profile for one launch."""

    executable: Path
    profile: Path


def default_firefox_profile() -> Path:
    """Return the dedicated Automata Firefox profile path."""
    return _config_home() / "automata" / "browser-profiles" / "firefox" / "automata"


def _existing_profile(profile: Path) -> Path:
    try:
        resolved = profile.expanduser().resolve(strict=True)
        if resolved.is_dir() and os.access(resolved, os.R_OK | os.W_OK | os.X_OK):
            return resolved
    except (OSError, RuntimeError, ValueError):
        pass
    raise BrowserError(f"Firefox profile must be an existing, accessible directory: {profile}")


def preflight_browser(
    profile: Path | None = None, *, executable: str = "firefox"
) -> FirefoxTarget:
    """Check the exact profile and Firefox executable without writing or launching."""
    selected = _existing_profile(default_firefox_profile() if profile is None else profile)
    command = shutil.which(executable)
    if command is None:
        raise BrowserError("Firefox executable not found; install Firefox or use --no-open-browser")
    return FirefoxTarget(Path(command).absolute(), selected)


def _is_navigation_ticket_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (
            url.startswith("http://127.0.0.1:")
            and "#" not in url
            and not any(char.isspace() or char < " " or char == "\x7f" for char in url)
            and parsed.hostname == "127.0.0.1"
            and parsed.username is None
            and parsed.port is not None
            and parsed.port > 0
            and parsed.path.startswith("/")
        )
    except ValueError:
        return False


def open_browser(target: FirefoxTarget, url: str) -> None:
    """Dispatch a short-lived, one-use navigation URL and return before attachment.

    Firefox may retain its argv on cold start. The caller must enforce expiry
    and single use, and separately verify attachment. Never pass admission URLs.
    """
    if not _is_navigation_ticket_url(url):
        raise BrowserError("Firefox launch requires a fragment-free loopback navigation ticket")
    profile = _existing_profile(target.profile)
    if profile != target.profile:
        raise BrowserError("Firefox profile path changed after preflight")

    env = os.environ.copy()
    # Firefox restart variables can override --profile or disable profile remoting.
    for name in ("XRE_PROFILE_PATH", "XRE_PROFILE_LOCAL_PATH", "MOZ_NO_REMOTE", "MOZ_NEW_INSTANCE"):
        env.pop(name, None)
    try:
        # Firefox's remote identity includes the full profile path. The same argv
        # starts the exact profile when closed or remotes to it when already open.
        process = subprocess.Popen(
            [str(target.executable), "--profile", str(profile), "--new-tab", url],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        status = process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        return
    except (OSError, ValueError):
        raise BrowserError("Could not start Firefox for the selected profile") from None
    if status != 0:
        raise BrowserError("Firefox rejected the launch for the selected profile")
