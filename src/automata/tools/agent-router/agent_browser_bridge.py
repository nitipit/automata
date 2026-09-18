#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["cyclopts>=4.11.1", "uvicorn>=0.30.0", "websockets>=12.0"]
# ///
"""Version-one CLI compatibility entry; install it as part of agent-router."""

import sys
from pathlib import Path

# Also support installed-style file imports used by external validation tooling.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from automata_router.cli import legacy_serve  # noqa: E402
from automata_router.cli import status as router_status
from automata_router.protocol import (  # noqa: E402,F401
    parse_frame,
    validate_delivery,
    validate_message,
    validate_payload,
)
from cyclopts import App  # noqa: E402


def setup(
    *,
    runtime_root: Path | None = None,
    endpoint_file: Path = Path(".agents/var/tools/agent-browser-bridge/endpoint.json"),
) -> None:
    if runtime_root is not None:
        (runtime_root / "lib").mkdir(parents=True, exist_ok=True)
        (runtime_root / "sessions").mkdir(parents=True, exist_ok=True)
    endpoint_file.parent.mkdir(parents=True, exist_ok=True)
    print("compatibility setup complete; no server, browser or agent started")


app = App(
    name="agent-browser-bridge", help="Explicit v1 single-pair compatibility; prefer agent-router."
)
app.command(setup)
app.command(legacy_serve, name="serve")


def status(
    *, endpoint_file: Path = Path(".agents/var/tools/agent-browser-bridge/endpoint.json")
) -> None:
    router_status(endpoint_file=endpoint_file)


app.command(status)

if __name__ == "__main__":
    app()
