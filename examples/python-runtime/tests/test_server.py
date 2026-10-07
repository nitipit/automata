import asyncio
import json
import os
from pathlib import Path
import socket
import sys
import tempfile

import httpx
import pytest
import websockets
from driver import request

ROOT = Path(__file__).resolve().parents[1]


async def cli(code, agent_socket):
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(ROOT / "driver.py"), "execute", code, "--socket", str(agent_socket),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), 15)
    assert process.returncode == 0, stderr.decode() + stdout.decode()
    return json.loads(stdout)["result"]


async def test_real_server_bridge_security_independent_cli_and_shutdown():
    # A short temp path also stays within Unix socket's filesystem-path limit.
    with tempfile.TemporaryDirectory(prefix="py-live-") as directory:
        await exercise_server(Path(directory))


async def exercise_server(run_dir):
    agent_socket = run_dir / "agent.sock"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(port),
        cwd=ROOT, env={**os.environ, "WORKSPACE_PORT": str(port),
                       "WORKSPACE_RUN_DIR": str(run_dir)},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    async def ready():
        lines = []
        while True:
            line = await process.stdout.readline()
            lines.append(line.decode())
            if b"Application startup complete" in line:
                return
            if not line:
                raise AssertionError("".join(lines))
    try:
        await asyncio.wait_for(ready(), 20)
        assert agent_socket.stat().st_mode & 0o777 == 0o600
        async with httpx.AsyncClient(base_url=origin) as client:
            assert (await client.get("/")).status_code == 200
            assert (await client.post("/execute", json={"code": "1"}, headers={"Origin": origin})).status_code == 404
            assert (await client.post("/action", json={"action": "increment"})).status_code == 403
            assert (await client.post("/action", json={"action": "increment"}, headers={"Origin": "http://evil.example"})).status_code == 403
            assert (await client.get("/", headers={"Host": "evil.example"})).status_code == 403
            async with websockets.connect(f"ws://127.0.0.1:{port}/events", origin=origin) as ws:
                initial = json.loads(await ws.recv())
                identity = initial["state"]["object_id"]
                browser = await client.post("/action", json={"action": "set", "value": 17}, headers={"Origin": origin})
                assert browser.json()["state"]["count"] == 17
                first = await cli("saved = counter; assert counter.value == 17; counter.value += 4", agent_socket)
                second = await cli("assert saved is counter; counter.value += 1", agent_socket)
                assert first["state"]["object_id"] == second["state"]["object_id"] == identity
                assert second["state"]["count"] == 22
                seen = []
                while True:
                    event = json.loads(await asyncio.wait_for(ws.recv(), 5))
                    seen.append(event)
                    if event["kind"] == "state" and event["state"]["count"] == 22:
                        break
                assert any(e["kind"] == "state" and e["source"] == "browser" for e in seen)
                assert any(e["kind"] == "state" and e["source"] == "python" for e in seen)
            with pytest.raises(websockets.exceptions.InvalidStatus):
                async with websockets.connect(f"ws://127.0.0.1:{port}/events", origin="http://evil.example"):
                    pass
        status = await request({"command": "status"}, agent_socket)
        assert status["result"]["state"]["count"] == 22
        assert not status["result"]["busy"]
    finally:
        if process.returncode is None:
            process.terminate()
        await asyncio.wait_for(process.communicate(), 15)
        assert not agent_socket.exists()
        assert not (run_dir / "server.pid").exists()
