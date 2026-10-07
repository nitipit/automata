# /// script
# requires-python = ">=3.12"
# dependencies = ["jupyter-client>=8.6,<9", "ipykernel>=6.29,<8"]
# ///
"""Inject startup failures against the installed runtime, using real owned kernels."""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
from automata_python_runtime import KernelRuntime, WorkspaceServer  # noqa: E402


async def main(stage):
    with tempfile.TemporaryDirectory(prefix="py-start-") as directory:
        runtime = KernelRuntime(
            bootstrap="raise ValueError('bad bootstrap')" if stage == "bootstrap" else ""
        )
        server = WorkspaceServer(Path(directory), runtime)
        start = runtime.start
        pid = None

        async def tracked_start():
            nonlocal pid
            try:
                await start()
            finally:
                pid = runtime.km.provisioner.pid
            if stage == "kernel_ready":
                raise RuntimeError("injected startup failure")

        async def fail_bind(*args, **kwargs):
            raise RuntimeError("injected startup failure")

        original_write = Path.write_text

        def fail_pid_write(path, *args, **kwargs):
            if path == server.workspace / "server.pid":
                raise RuntimeError("injected startup failure")
            return original_write(path, *args, **kwargs)

        runtime.start = tracked_start
        try:
            if stage == "socket_bind":
                with patch("asyncio.start_unix_server", fail_bind):
                    await server.open()
            elif stage == "pid_write":
                with patch.object(Path, "write_text", fail_pid_write):
                    await server.open()
            else:
                await server.open()
        except RuntimeError:
            pass
        else:
            await server.close()
            raise AssertionError("Expected injected startup failure")
        assert pid is not None
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise AssertionError(f"Owned kernel survived startup failure: {pid}")
        assert not server.socket.exists()
        assert not (server.workspace / "server.pid").exists()
        assert server.lock_file is None
        print(json.dumps({"startup_failure": stage, "kernel_pid": pid, "cleaned": True}))


asyncio.run(main(sys.argv[2]))
