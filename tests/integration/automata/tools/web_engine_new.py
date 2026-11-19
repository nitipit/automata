"""Opt-in selected-engine CLI with a disposable IPython kernel and visible Firefox.

Run with built Web Chat assets, the web extra, jupyter_client, ipykernel and
websocket-client. Also needs local Pi, Firefox, ss and an X display. No model
service, personal profile, or existing engine is used.
"""

import ast
import asyncio
import json
import os
import shutil
import signal
import sqlite3
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from unittest.mock import patch

from jupyter_client import AsyncKernelManager

from automata.tools.web import bidi, engine
from automata.tools.web.browser import BrowserError, preflight_browser
from automata.tools.web.config import WebConfig, save_config


async def evaluate(client, code="", expression="None"):
    reply = await client.execute(
        code,
        silent=True,
        store_history=False,
        allow_stdin=False,
        user_expressions={"check": expression},
        reply=True,
        timeout=15,
    )
    content = reply["content"]
    assert content["status"] == "ok", content.get("ename")
    check = content["user_expressions"]["check"]
    assert check["status"] == "ok", check.get("ename")
    return ast.literal_eval(check["data"]["text/plain"])


async def cli(config, connection, action, project, *options):
    started = time.monotonic()
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "automata.cli",
        "web-ui",
        "--config",
        str(config),
        "chat",
        action,
        "--cwd",
        str(project),
        "--engine",
        str(connection),
        "--json",
        *options,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(80):
            stdout, _ = await child.communicate()
    finally:
        if child.returncode is None:
            child.kill()
            await child.wait()
    assert stdout, f"CLI did not return a result ({child.returncode})"
    result = json.loads(stdout)
    assert child.returncode == 0, result.get("error") or {
        name: status.get("reason") or status.get("host", {}).get("reason")
        for name in ("engine", "managed_host")
        if (status := result.get(name))
    }
    return result, time.monotonic() - started


async def stop_disposable_firefox(target):
    # Find only the process that locked this newly-created fixture profile.
    # A vanished or stale lock is not grounds to signal an unrelated process.
    try:
        pid = int(os.readlink(target.profile / "lock").split(":+")[-1])
        identity = bidi._process_identity(pid, target)
    except (OSError, ValueError):
        return
    for signum, seconds in [(signal.SIGTERM, 8), (signal.SIGKILL, 2)]:
        with suppress(ProcessLookupError):
            os.kill(pid, signum)
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                if bidi._process_identity(pid, target) != identity:
                    return
            except (OSError, ValueError):
                return
            await asyncio.sleep(0.05)
    raise AssertionError("Disposable Firefox did not exit")


async def exercise(config, connection, project, target, client):
    before, _ = await cli(config, connection, "status", project)
    assert before["managed_host"]["state"] == "not_running"
    assert before["engine"]["host"] == {"state": "running", "sessions": []}

    cold, cold_time = await cli(config, connection, "new", project)
    assert cold["creation"] == "created" and cold["browser_connected"]
    endpoint = bidi._endpoint(target, shutil.which("ss"))
    warm, warm_time = await cli(
        config, connection, "new", project, "--model", "plain", "--thinking", "off"
    )
    assert warm["creation"] == "created" and warm["browser_connected"]
    assert bidi._endpoint(target, shutil.which("ss")) == endpoint
    cold_id, warm_id = cold["session_id"], warm["session_id"]
    assert cold_id != warm_id
    assert await evaluate(
        client,
        expression=(
            "[(host._entries[sid].chat.state['model']['id'], "
            "host._entries[sid].chat.state['thinkingLevel']) "
            f"for sid in [{cold_id!r}, {warm_id!r}]]"
        ),
    ) == [("fixture", "low"), ("plain", "off")]

    origin = await evaluate(client, expression="host.runtime.origin")
    controller = await asyncio.to_thread(bidi.connect_firefox, target)
    try:
        tabs = controller.call("browsingContext.getTree", maxDepth=0)["contexts"]
        assert {tab["url"] for tab in tabs if tab["url"].startswith(origin)} == {
            f"{origin}/chat/sessions/{sid}/" for sid in (cold_id, warm_id)
        }
    finally:
        controller.close()

    # Keep the real kernel and Firefox preflight, but fail navigation after the
    # one actual native Pi creation. Status must show exactly one extra session.
    with patch.object(bidi.FirefoxBiDi, "open_chat", side_effect=BrowserError("fixture failure")):
        failed = await engine.create_chat(connection, project, target, {})
    assert failed == {
        "creation": "created",
        "session_id": failed["session_id"],
        "browser_connected": False,
        "error": "browser_open_failed",
    }
    assert failed["session_id"] not in {None, cold_id, warm_id}
    after, _ = await cli(config, connection, "status", project)
    assert after["managed_host"]["state"] == "not_running"
    assert {
        item["id"]: item["client_connected"] for item in after["engine"]["host"]["sessions"]
    } == {cold_id: True, warm_id: True, failed["session_id"]: False}
    assert await evaluate(
        client,
        expression=(
            "not any(name.startswith('_automata_engine_') for name in globals()) and "
            "not any('kernel_create' in source or '/launch/' in source for source in In)"
        ),
    )
    print(f"Cold Firefox: {cold_time:.3f}s; warm Firefox: {warm_time:.3f}s (CLI wall time)")
    return {f"{origin}/chat/sessions/{sid}/" for sid in (cold_id, warm_id)}


async def main(root):
    assert os.environ.get("DISPLAY") and all(shutil.which(c) for c in ("firefox", "ss", "pi"))
    profile, project, store, agent, runtime = (
        root / part for part in ("fx", "project", "sessions", "agent", "runtime")
    )
    for directory in (profile, project, store, agent, runtime):
        directory.mkdir(mode=0o700)
    (agent / "settings.json").write_text(
        json.dumps(
            {
                "enabledModels": ["picker-fixture/fixture", "picker-fixture/plain"],
            }
        )
    )
    (profile / "user.js").write_text(
        'user_pref("browser.aboutwelcome.enabled", false);\n'
        'user_pref("browser.shell.checkDefaultBrowser", false);\n'
    )
    config, connection = root / "prefs", root / "private.json"
    save_config(config, WebConfig({"browser_profile": str(profile)}))
    fixture = Path(__file__).with_name("web_sessions_picker.ts").resolve()
    pi_options = (
        "--offline",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--session-dir",
        str(store),
        "-e",
        str(fixture),
    )
    manager = AsyncKernelManager(connection_file=str(connection), kernel_name="python3")
    manager.kernel_spec.argv = [
        sys.executable,
        "-m",
        "ipykernel_launcher",
        "-f",
        "{connection_file}",
    ]
    await manager.start_kernel()
    client = manager.client()
    client.start_channels()
    target = preflight_browser(profile)
    try:
        await client.wait_for_ready(timeout=12)
        await evaluate(
            client,
            (
                "from pathlib import Path\n"
                "from automata.tools.web.host import BrowserHost\n"
                "host = BrowserHost()\n"
                f"await host.start(cwd=Path({str(project)!r}), provider='picker-fixture', "
                f"model='fixture', thinking='low', extra_args={pi_options!r}, create_initial=False)"
            ),
        )
        urls = await exercise(config, connection, project, target, client)
        assert not (runtime / "automata-web-ui").exists()
    finally:
        try:
            with suppress(Exception):
                await evaluate(client, "await host.close()")
        finally:
            client.stop_channels()
            try:
                await manager.shutdown_kernel(now=True)
            finally:
                await stop_disposable_firefox(target)
    with sqlite3.connect(f"file:{profile / 'places.sqlite'}?mode=ro", uri=True) as places:
        visited = {
            url
            for (url,) in places.execute(
                "SELECT DISTINCT p.url FROM moz_places AS p "
                "JOIN moz_historyvisits AS v ON p.id = v.place_id "
                "WHERE p.url LIKE 'http://127.0.0.1:%'"
            )
        }
        assert visited == urls, (
            f"Firefox history: {len(visited & urls)} expected, {len(visited - urls)} other "
            "loopback visits"
        )
    print(
        "Selected-engine integration passed, including real creation followed by browser failure."
    )


if __name__ == "__main__":
    # Managed status also checks the 107-byte Linux sockaddr_un limit.
    with tempfile.TemporaryDirectory(prefix="ae-", dir="/tmp") as directory:
        env = dict(os.environ)
        env.pop("PI_SESSION_FILE", None)
        env.pop("MOZ_HEADLESS", None)
        root = Path(directory)
        for var, part in (
            ("HOME", "home"),
            ("XDG_CONFIG_HOME", "config"),
            ("XDG_CACHE_HOME", "cache"),
            ("XDG_DATA_HOME", "data"),
            ("XDG_STATE_HOME", "state"),
            ("IPYTHONDIR", "ipython"),
            ("XDG_RUNTIME_DIR", "runtime"),
            ("PI_CODING_AGENT_DIR", "agent"),
        ):
            env[var] = str(root / part)
        (root / "home").mkdir()
        env["MOZ_ENABLE_WAYLAND"] = "0"  # Keep the fixture's XDG runtime isolated; use DISPLAY.
        with patch.dict(os.environ, env, clear=True):
            asyncio.run(main(root))
