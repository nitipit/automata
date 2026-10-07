#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "cyclopts>=4.11.1", "dictify>=5.0.2",
#   "jupyter-client>=8.6,<9", "ipykernel>=6.29,<8",
# ]
# ///
"""A trusted persistent Python kernel, controlled through a private local Unix socket."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter
from dictify import Field, Model

# Tool copies are read-only assets: do not leave import bytecode beside them.
sys.dont_write_bytecode = True
from automata_python_runtime import KernelRuntime, WorkspaceServer, request  # noqa: E402

app = App(
    name="python-runtime",
    help=(
        "Persistent trusted Python workspace (Linux/Unix; NOT a sandbox). "
        "serve runs in foreground; independent execute calls reuse the SAME kernel objects. "
        "Choose --workspace outside installed code, e.g. .agents/var/tools/python-runtime/demo. "
        "Its absolute agent.sock path must be shorter than 108 bytes (Unix socket limit). "
        "No network execute API. Workspace directory/socket are private to your user. "
        "JSON replies, bounded output, no interactive kernel stdin, no automatic replay. "
        "Restart loses memory but cannot undo filesystem/network/process side effects. "
        "Use status to inspect lifecycle, interrupt busy Python, restart/reset, stop cleanly."
    ),
)


class WorkspaceOptions(Model):
    workspace: Annotated[str, Field(required=True)]


class ServeOptions(WorkspaceOptions):
    cwd: Annotated[str | None, Field(default=None)]


class ExecuteOptions(WorkspaceOptions):
    timeout: Annotated[float, Field(default=10.0).verify(lambda n: 0.1 <= n <= 30)]


def emit(reply):
    print(json.dumps(reply, ensure_ascii=False))
    if not reply["ok"] or reply.get("result", {}).get("status", "ok") != "ok":
        raise SystemExit(1)


def call(command, options, **fields):
    emit(asyncio.run(request({"command": command, **fields}, Path(options.workspace))))


async def run_server(options):
    workspace = Path(options.workspace).expanduser().resolve()
    installed = Path(__file__).resolve().parent
    if workspace.is_relative_to(installed):
        raise ValueError("Workspace must be outside installed tool code")
    cwd = Path(options.cwd).expanduser().resolve() if options.cwd else Path.cwd()
    runtime = KernelRuntime(cwd=cwd)
    server = WorkspaceServer(workspace, runtime)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, server.stop_requested.set)
    try:
        await server.open()
        emit(
            {
                "ok": True,
                "result": {
                    "serving": True,
                    "pid": os.getpid(),
                    "workspace": str(workspace),
                    **runtime.view(),
                },
            }
        )
        sys.stdout.flush()
        await server.stop_requested.wait()
    finally:
        await server.close()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)


@app.command
def serve(options: Annotated[ServeOptions, Parameter(name="*")]):
    """Run foreground owner. --workspace is private runtime storage; --cwd is kernel CWD.

    Use a dedicated owned process/tmux session if persistence is needed. SIGTERM,
    Ctrl+C or stop closes the owned kernel/socket. Stale sockets require verified
    owner inactivity before manual removal. No arbitrary descendants are cleaned.
    """
    asyncio.run(run_server(options))


@app.command
def execute(code: str, options: Annotated[ExecuteOptions, Parameter(name="*")]):
    """Execute Python or '-' for CLI stdin; --timeout 0.1–30s, default 10.

    Queue waits at most 5s; timeout interrupts then waits up to 3s for reply+idle.
    Replies cap output at 8192 chars and include correlation/lifecycle markers.
    Python errors retain partial mutations. Transport errors may mean executed
    code: do not replay automatically. State inspection is caller-owned Python.
    """
    if code == "-":
        code = sys.stdin.read()
    call("execute", options, code=code, timeout=options.timeout)


@app.command
def status(options: Annotated[WorkspaceOptions, Parameter(name="*")]):
    """Read runtime ID, generation, busy/healthy state and bounded display events."""
    call("status", options)


@app.command
def interrupt(options: Annotated[WorkspaceOptions, Parameter(name="*")]):
    """Out-of-band kernel interrupt; never rolls back mutations or external effects."""
    call("interrupt", options)


@app.command
def restart(options: Annotated[WorkspaceOptions, Parameter(name="*")]):
    """Interrupt if busy, discard memory and start a new generation; no command replay."""
    call("restart", options)


@app.command
def stop(options: Annotated[WorkspaceOptions, Parameter(name="*")]):
    """Request clean owner shutdown; verify process/socket disappearance afterward."""
    call("stop", options)


def main():
    try:
        app()
    except (TimeoutError, OSError, RuntimeError, ValueError, Model.Error) as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"[:1000]}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
