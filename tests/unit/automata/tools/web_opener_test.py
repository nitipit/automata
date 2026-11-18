"""Isolated fake openers/Pi only: never launch a real browser or model request."""

import asyncio
import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("automata_web_runtime")
httpx = pytest.importorskip("httpx")

from automata.tools.web import host as host_module  # noqa: E402

DRIVER = """import asyncio, contextlib, json, os
from pathlib import Path
from automata.tools.web import host
original_start = host.BrowserHost.start
async def start(self, **kwargs):
    await original_start(self, **kwargs)
    Path(os.environ['HOST_READY']).write_text(json.dumps({
        'origin': self.runtime.origin, 'token': self.initial_session.admission,
        'session': self.initial_session.id,
        'connector_token': self.initial_session.connector_token}))
host.BrowserHost.start = start
async def main():
    serving = asyncio.create_task(host.serve(
        pi=os.environ['FAKE_PI'], cwd=Path(os.environ['FAKE_WORKSPACE']),
        open_browser=os.environ['OPEN_BROWSER'] == '1'))
    if os.environ['STOP_MODE'] == 'cancel':
        while not Path(os.environ['CANCEL_TRIGGER']).exists() and not serving.done():
            await asyncio.sleep(.01)
        serving.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await serving
asyncio.run(main())
"""

FAKE_PI = """import json, os, sys
for line in sys.stdin:
    command = json.loads(line)
    with open(os.environ['RPC_COMMANDS'], 'a') as stream:
        stream.write(command['type'] + '\\n')
    if command['type'] == 'get_state':
        data = {'sessionId':'opener-fixture', 'sessionFile':os.path.abspath('opener-fixture.jsonl')}
    elif command['type'] == 'get_messages':
        data = {'messages': []}
    else:
        data = {}
    print(json.dumps({'type': 'response', 'id': command['id'],
                     'success': True, 'data': data}), flush=True)
"""

FAKE_BROWSER = """import json, os, sys, time
from pathlib import Path
# Deliberately noisy: neither browser output nor its private URL may leak.
print(sys.argv[-1], flush=True)
print(sys.argv[-1], file=sys.stderr, flush=True)
Path(os.environ['OPENER_READY']).write_text(json.dumps({
    'pid': os.getpid(), 'helper': os.getppid(), 'url': sys.argv[-1]}))
if os.environ['BROWSER_RESULT'] == 'fail':
    sys.exit(7)
if os.environ['BROWSER_RESULT'] == 'success':
    sys.exit(0)
while True:
    time.sleep(1)
"""


def wait_until(condition, *, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = condition()
        if result:
            return result
        time.sleep(0.01)
    pytest.fail("Isolated test process did not become ready before deadline")


def process_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # On Linux a test-owned fake may briefly await the container init reaper.
    stat = Path(f"/proc/{pid}/stat")
    try:
        return stat.read_text().split(") ", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


class IsolatedHost:
    def __init__(self, tmp_path, *, open_browser=True, stop_mode="signal", result="block"):
        self.ready = tmp_path / "host.json"
        self.opener_ready = tmp_path / "opener.json"
        self.commands = tmp_path / "rpc.txt"
        self.cancel_trigger = tmp_path / "cancel"
        pi = tmp_path / "fake-pi"
        browser = tmp_path / "fake-browser"
        for path, source in ((pi, FAKE_PI), (browser, FAKE_BROWSER)):
            path.write_text(f"#!{sys.executable}\n" + source)
            path.chmod(0o700)
        env = dict(os.environ)
        # No desktop/browser discovery or user's real fallback on failed open.
        for name in ("DISPLAY", "WAYLAND_DISPLAY", "TERM"):
            env.pop(name, None)
        env.update(
            PATH=str(tmp_path),
            PYTHONPATH=os.pathsep.join(
                filter(
                    None,
                    (
                        str(Path(host_module.__file__).resolve().parents[3]),
                        env.get("PYTHONPATH"),
                    ),
                )
            ),
            BROWSER=str(browser) + " %s",
            HOST_READY=str(self.ready),
            OPENER_READY=str(self.opener_ready),
            RPC_COMMANDS=str(self.commands),
            CANCEL_TRIGGER=str(self.cancel_trigger),
            FAKE_PI=str(pi),
            FAKE_WORKSPACE=str(tmp_path),
            OPEN_BROWSER="1" if open_browser else "0",
            STOP_MODE=stop_mode,
            BROWSER_RESULT=result,
        )
        if result == "exception":
            # The helper still runs its real script, with a controlled stdlib error.
            (tmp_path / "sitecustomize.py").write_text(
                "import webbrowser\n"
                "def fail(url):\n"
                "    raise RuntimeError(url)\n"
                "webbrowser.open = fail\n"
            )
            env["PYTHONPATH"] = str(tmp_path) + os.pathsep + env["PYTHONPATH"]
        self.process = subprocess.Popen(
            [sys.executable, "-u", "-c", DRIVER],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.stop_mode = stop_mode
        self.output = None

    def metadata(self):
        wait_until(self.ready.exists)
        return json.loads(self.ready.read_text())

    def opener(self):
        wait_until(self.opener_ready.exists)
        return json.loads(self.opener_ready.read_text())

    def stop(self):
        if self.stop_mode == "cancel":
            self.cancel_trigger.touch()
        else:
            self.process.send_signal(signal.SIGTERM)
        self.output = self.process.communicate(timeout=6)
        assert self.process.returncode == 0

    def cleanup(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.communicate(timeout=3)
        # These fakes represent browsers: host shutdown must not kill them.
        if self.opener_ready.exists():
            opener = json.loads(self.opener_ready.read_text())
            for key in ("pid", "helper"):
                with contextlib.suppress(ProcessLookupError):
                    os.kill(opener[key], signal.SIGKILL)


def assert_private_output(app, metadata):
    stdout, stderr = app.output
    assert metadata["token"] not in stdout + stderr
    assert metadata["connector_token"] not in stdout + stderr
    assert "?token=" not in stdout + stderr
    assert "Traceback" not in stderr
    assert "admission URL private" in stdout


@pytest.mark.skipif(sys.platform != "linux", reason="POSIX signals and /proc ownership check")
@pytest.mark.parametrize("stop_mode", ["signal", "cancel"])
def test_blocking_configured_opener_keeps_http_native_stop_and_shutdown_live(tmp_path, stop_mode):
    app = IsolatedHost(tmp_path, stop_mode=stop_mode)
    try:
        metadata = app.metadata()
        opener = app.opener()
        assert process_alive(opener["helper"])
        assert process_alive(opener["pid"])
        with httpx.Client(trust_env=False, headers={"User-Agent": "Automata/1.0"}) as client:
            assert client.get(metadata["origin"], timeout=2).status_code == 200
            response = client.post(metadata["origin"] + "/connector/execute", json={})
            assert response.status_code == 403

        async def native_stop():
            import websockets

            origin = metadata["origin"]
            path = f"/sessions/{metadata['session']}/chat"
            async with httpx.AsyncClient(
                base_url=origin, headers={"User-Agent": "Automata/1.0"}
            ) as client:
                response = await client.post(
                    path + "/connection",
                    headers={
                        "Origin": origin,
                        "Authorization": f"Bearer {metadata['token']}",
                    },
                )
                ticket = response.json()["ticket"]
            ws_origin = origin.replace("http:", "ws:")
            async with websockets.connect(ws_origin + "/ws?token=" + ticket, origin=origin):
                async with websockets.connect(
                    ws_origin + path + "?token=" + ticket, origin=origin
                ) as chat:
                    assert json.loads(await chat.recv())["type"] == "snapshot"
                    await chat.send(json.dumps({"id": "stop", "type": "stop"}))
                    while True:
                        frame = json.loads(await chat.recv())
                        if frame.get("type") == "ack":
                            assert frame["success"]
                            return

        asyncio.run(asyncio.wait_for(native_stop(), 2))
        assert app.commands.read_text().splitlines()[:6] == [
            "get_state",
            "get_messages",
            "get_state",
            "get_state",
            "clear_queue",
            "abort",
        ]
        before = time.monotonic()
        app.stop()
        assert time.monotonic() - before < 6
        assert not process_alive(opener["helper"])
        assert process_alive(opener["pid"])  # Never kill a browser as part of host shutdown.
        assert_private_output(app, metadata)
    finally:
        app.cleanup()


@pytest.mark.parametrize("result", ["fail", "exception", "success"])
def test_opener_result_is_reported_honestly_without_url_and_host_keeps_serving(tmp_path, result):
    app = IsolatedHost(tmp_path, result=result)
    try:
        metadata = app.metadata()
        if result in {"fail", "success"}:
            opener = app.opener()
            wait_until(lambda: not process_alive(opener["helper"]))
        else:
            # Wait for the helper to report its exception via the generic warning.
            import select

            assert select.select([app.process.stderr], [], [], 3)[0]
        with httpx.Client(trust_env=False, headers={"User-Agent": "Automata/1.0"}) as client:
            assert client.get(metadata["origin"], timeout=2).status_code == 200
        app.stop()
        assert_private_output(app, metadata)
        assert app.output[1].count("Browser auto-open failed") == (result != "success")
    finally:
        app.cleanup()


def test_no_open_browser_does_not_start_configured_opener(tmp_path):
    app = IsolatedHost(tmp_path, open_browser=False)
    try:
        metadata = app.metadata()
        with httpx.Client(trust_env=False, headers={"User-Agent": "Automata/1.0"}) as client:
            assert client.get(metadata["origin"], timeout=2).status_code == 200
        app.stop()
        assert not app.opener_ready.exists()
        assert_private_output(app, metadata)
    finally:
        app.cleanup()


def test_opener_spawn_error_is_redacted(monkeypatch, capsys):
    async def unavailable(*args, **kwargs):
        raise OSError("test-secret-private-url")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", unavailable)
    asyncio.run(host_module._open_browser("test-secret-private-url"))
    output = capsys.readouterr()
    assert "Browser auto-open failed" in output.err
    assert "test-secret-private-url" not in output.out + output.err


def test_cancel_during_spawn_cannot_abandon_owned_helper(monkeypatch):
    original = asyncio.create_subprocess_exec
    spawned = []

    async def check():
        created = asyncio.Event()
        release = asyncio.Event()

        async def delayed(*args, **kwargs):
            process = await original(*args, **kwargs)
            spawned.append(process)
            created.set()
            await release.wait()
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed)
        monkeypatch.setattr(host_module, "_BROWSER_OPEN", "import time; time.sleep(60)")
        opening = asyncio.create_task(host_module._open_browser("private-test-url"))
        try:
            await asyncio.wait_for(created.wait(), 2)
            opening.cancel()
            await asyncio.sleep(0)
            assert not opening.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(opening, 2)
            assert spawned[0].returncode is not None
        finally:
            release.set()
            opening.cancel()
            await asyncio.gather(opening, return_exceptions=True)
            for process in spawned:
                if process.returncode is None:
                    process.kill()
                    await process.wait()

    asyncio.run(check())


@pytest.mark.skipif(sys.platform != "linux", reason="POSIX TERM/KILL semantics")
def test_stubborn_helper_is_killed_and_reaped_without_waiting_for_executor(tmp_path, monkeypatch):
    ready = tmp_path / "helper-ready"
    monkeypatch.setattr(
        host_module,
        "_BROWSER_OPEN",
        "import signal,time\n"
        "from pathlib import Path\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"Path({str(ready)!r}).touch()\n"
        "time.sleep(60)\n",
    )
    original = asyncio.create_subprocess_exec
    spawned = []

    async def capture(*args, **kwargs):
        assert "private-test-url" not in args
        process = await original(*args, **kwargs)
        spawned.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", capture)

    async def check():
        opening = asyncio.create_task(host_module._open_browser("private-test-url"))
        try:
            async with asyncio.timeout(2):
                while not ready.exists():
                    await asyncio.sleep(0.01)
            opening.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(opening, 2.5)
            assert spawned[0].returncode == -signal.SIGKILL
        finally:
            opening.cancel()
            await asyncio.gather(opening, return_exceptions=True)
            for process in spawned:
                if process.returncode is None:
                    process.kill()
                    await process.wait()

    asyncio.run(check())
