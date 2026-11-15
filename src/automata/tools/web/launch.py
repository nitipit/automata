"""Prepare native Pi invocation without replacing the caller's agent environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PiLaunch:
    argv: tuple[str, ...]
    cwd: Path


def prepare_launch(
    *,
    pi: str,
    extension: Path,
    cwd: Path | None = None,
    provider: str | None = None,
    model: str | None = None,
    thinking: str | None = None,
    session: Path | None = None,
    session_inactive: bool = False,
    extra_args: tuple[str, ...] = (),
) -> PiLaunch:
    """Use persistent native defaults, or resume one explicitly inactive session.

    The assertion is supplied by the operator, not an external-process detector.
    Pi resolves a resumed session's recorded CWD/configuration itself. In particular,
    do not derive PATH or VIRTUAL_ENV from this host's Python interpreter: a caller
    may intentionally use a project environment for both the host and the agent.
    """
    directory = (cwd or Path.cwd()).expanduser().resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("Pi working directory must be an existing directory")
    argv = [pi, "--mode", "rpc", "-e", str(extension)]
    if session is not None:
        if not session_inactive:
            raise ValueError(
                "Resume requires --session-inactive; first confirm no Pi owns the session"
            )
        selected = session.expanduser()
        if not selected.is_absolute():
            selected = directory / selected
        selected = selected.resolve(strict=True)
        if not selected.is_file() or selected.suffix != ".jsonl":
            raise ValueError("--session requires an exact existing .jsonl file")
        inherited = os.environ.get("PI_SESSION_FILE")
        if inherited and selected == Path(inherited).expanduser().resolve():
            raise ValueError("Cannot resume the calling Pi session; it may still be active")
        argv.extend(("--session", str(selected)))
    elif session_inactive:
        raise ValueError("--session-inactive requires --session")
    for flag, value in (("--provider", provider), ("--model", model), ("--thinking", thinking)):
        if value is not None:
            argv.extend((flag, value))
    argv.extend(extra_args)
    return PiLaunch(tuple(argv), directory)
