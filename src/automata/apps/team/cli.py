"""Lightweight Cyclopts surface; optional dependencies load inside commands only."""

from __future__ import annotations

import asyncio
import json as json_module
import sys
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

app = App(help="Automata Team: trusted-local publishing and a read-only goal board.")
DEFAULT_STATE_ROOT = Path(".agents/var/apps/agent-team")
InputFile = Annotated[Path, Parameter(allow_leading_hyphen=True, help="JSON file or - for stdin.")]


def read_document(file):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"non-finite JSON constant: {value}")

    text = sys.stdin.read() if str(file) == "-" else Path(file).read_text()
    document = json_module.loads(text, object_pairs_hook=pairs, parse_constant=invalid)
    if type(document) is not dict:
        raise ValueError("JSON object required")
    return document


def execute(operation):
    try:
        return operation()
    except Exception as error:
        raise SystemExit(f"Automata Team: {error}") from error


@app.command
def serve(*, state_root: Path = DEFAULT_STATE_ROOT) -> None:
    """Serve trusted-local ShelfDB over Unix IPC until Ctrl-C or SIGTERM."""

    def run():
        from .server import serve as serve_backend

        asyncio.run(serve_backend(state_root))

    execute(run)


@app.command
def init(*, goal: str, actor: str, file: InputFile, state_root: Path = DEFAULT_STATE_ROOT) -> None:
    """Atomically add a complete new goal graph from JSON (use --file - for stdin)."""

    def run():
        from .store import initialize, service_url

        asyncio.run(initialize(read_document(file), actor, goal, service_url(state_root)))

    execute(run)


def publish_command(goal, actor, kind, id, file, state_root, replace):
    def run():
        from .store import publish, service_url

        shelf = {"goal": "goals", "team": "teams", "agent": "agents", "task": "tasks"}.get(kind)
        if shelf is None:
            raise ValueError("kind must be goal, team, agent, or task")
        result = asyncio.run(
            publish(
                shelf,
                id,
                read_document(file),
                actor,
                goal,
                replace=replace,
                url=service_url(state_root),
            )
        )
        print(json_module.dumps(result, allow_nan=False))

    execute(run)


@app.command
def put(
    *,
    goal: str,
    actor: str,
    kind: str,
    id: str,
    file: InputFile,
    state_root: Path = DEFAULT_STATE_ROOT,
) -> None:
    """Create or replace an authorized complete record; declared actor is not authentication."""
    publish_command(goal, actor, kind, id, file, state_root, True)


@app.command
def update(
    *,
    goal: str,
    actor: str,
    kind: str,
    id: str,
    file: InputFile,
    state_root: Path = DEFAULT_STATE_ROOT,
) -> None:
    """Recursively merge a JSON patch; omitted fields survive, identity is immutable."""
    publish_command(goal, actor, kind, id, file, state_root, False)


@app.command
def json(
    *,
    goal: str,
    kind: str | None = None,
    id: str | None = None,
    state_root: Path = DEFAULT_STATE_ROOT,
) -> None:
    """Emit one record or a complete goal-scoped plain-JSON snapshot."""

    def run():
        from .store import service_url, snapshot

        if (kind is None) != (id is None):
            raise ValueError("--kind and --id must be supplied together")
        result = asyncio.run(
            snapshot(goal, service_url(state_root), reports_only=kind in ("goal", "team", "agent"))
        )
        if kind is not None:
            shelf = {"goal": "goals", "team": "teams", "agent": "agents", "task": "tasks"}.get(kind)
            if shelf is None or id not in result[shelf]:
                raise ValueError("unknown kind/record")
            result = result[shelf][id]
        print(json_module.dumps(result, allow_nan=False))

    execute(run)


@app.command
def board(*, goal: str, state_root: Path = DEFAULT_STATE_ROOT) -> None:
    """Open a permanently goal-scoped read-only viewer; q leaves the backend running."""

    def run():
        from .app import Dashboard
        from .hierarchy import agent_parents
        from .store import service_url, snapshot

        url = service_url(state_root)

        state = asyncio.run(snapshot(goal, url, reports_only=True))
        agent_parents(state)  # Fail nonzero before entering the TUI if placement is ambiguous.
        Dashboard(goal, url).run()

    execute(run)
