import os
from pathlib import Path
import tempfile

import pytest
import server
from runtime import KernelRuntime


@pytest.mark.parametrize("failure_stage", ["kernel_ready", "socket_bind", "pid_write"])
async def test_startup_failure_closes_its_owned_kernel(monkeypatch, failure_stage):
    kernel = KernelRuntime()
    started_pid = None
    original_start = kernel.start
    original_write = Path.write_text

    async def tracked_start():
        nonlocal started_pid
        await original_start()
        started_pid = kernel.km.provisioner.pid
        if failure_stage == "kernel_ready":
            raise RuntimeError("injected startup failure")

    async def fail_bind(*args, **kwargs):
        assert started_pid is not None
        raise RuntimeError("injected startup failure")

    def fail_pid_write(path, *args, **kwargs):
        if path == server.RUN / "server.pid":
            raise RuntimeError("injected startup failure")
        return original_write(path, *args, **kwargs)

    with tempfile.TemporaryDirectory(prefix="py-start-") as directory:
        monkeypatch.setattr(server, "RUN", Path(directory))
        monkeypatch.setattr(server, "SOCKET", Path(directory) / "agent.sock")
        monkeypatch.setattr(server, "runtime", kernel)
        monkeypatch.setattr(kernel, "start", tracked_start)
        if failure_stage == "socket_bind":
            monkeypatch.setattr(server.asyncio, "start_unix_server", fail_bind)
        if failure_stage == "pid_write":
            monkeypatch.setattr(Path, "write_text", fail_pid_write)
        with pytest.raises(RuntimeError, match="injected startup failure"):
            async with server.lifespan(server.app):
                pytest.fail("Startup should not reach serving state")
        assert started_pid is not None
        with pytest.raises(ProcessLookupError):
            os.kill(started_pid, 0)
        assert not server.SOCKET.exists()
        assert not (server.RUN / "server.pid").exists()
