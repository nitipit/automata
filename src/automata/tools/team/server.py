"""One trusted-local Unix listener; graceful SIGINT/SIGTERM lifecycle."""

import asyncio
import os
import signal
from pathlib import Path

from shelfdb.protocol import serve_unix
from shelfdb.shelf import DB

from .store import DEFAULT_STATE_ROOT


async def serve(state_root=DEFAULT_STATE_ROOT):
    root = Path(state_root).resolve()
    socket = root / "db.sock"
    if len(os.fsencode(socket)) > 103:
        raise ValueError("Unix socket path too long; use a shorter --state-root")
    old_umask = os.umask(0o077)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    installed = []
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if socket.exists() or socket.is_symlink():
            raise ValueError("socket already exists; never replace a live listener")
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
            installed.append(sig)
        with DB(str(root / "db")) as db:
            server = await serve_unix(db, path=str(socket))
            try:
                await stop.wait()
            finally:
                server.close()
                await server.wait_closed()
                socket.unlink(missing_ok=True)
    finally:
        for sig in installed:
            loop.remove_signal_handler(sig)
        os.umask(old_umask)
