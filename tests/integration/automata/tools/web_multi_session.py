"""Opt-in visible Firefox + one host + real offline Pi integration.

Build with ``npm run build:web``. Run with project src, the web runtime and
websocket-client importable, and a visible display. Uses only fresh HOME/Pi
session store and a disposable browser profile; never an external provider.
"""

# ruff: noqa: E501 -- inline BiDi JavaScript conditions are kept together.
import asyncio
import contextlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import websocket

from automata.tools.web.host import BrowserHost


class Browser:
    def __init__(self, socket):
        self.socket = socket
        self.sequence = 0
        self.errors = 0

    def exchange(self, method, params):
        self.sequence += 1
        self.socket.send(json.dumps({"id": self.sequence, "method": method, "params": params}))
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            reply = json.loads(self.socket.recv())
            if reply.get("method") == "log.entryAdded":
                entry = reply["params"]
                if entry["type"] == "javascript" and entry["level"] == "error":
                    self.errors += 1
            if reply.get("id") != self.sequence:
                continue
            if reply.get("type") != "success":
                raise AssertionError(f"Firefox BiDi {method}: {reply.get('error')}")
            return reply["result"]
        raise TimeoutError(f"Timed out waiting for Firefox BiDi {method}")

    async def call(self, method, **params):
        return await asyncio.to_thread(self.exchange, method, params)

    async def evaluate(self, tab, expression):
        reply = await self.call(
            "script.evaluate", target={"context": tab}, expression=expression, awaitPromise=True
        )
        assert reply["type"] == "success", "Firefox page evaluation failed"
        return reply["result"].get("value")

    async def wait(self, tab, condition, label, timeout=12):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if await self.evaluate(tab, condition):
                return
            await asyncio.sleep(0.05)
        state = await self.evaluate(
            tab,
            """JSON.stringify({
            connection: document.querySelector('#connection-detail')?.textContent,
            status: document.querySelector('#run-status')?.textContent,
            picker: document.querySelector('#sessions-status')?.textContent,
            action: document.querySelector('#send')?.dataset.action,
            transcript: document.querySelector('#transcript')?.textContent?.slice(-450),
        })""",
        )
        raise AssertionError(f"Did not observe {label}; disposable fixture state: {state}")

    async def tabs(self):
        result = await self.call("browsingContext.getTree", maxDepth=0)
        return {item["context"] for item in result["contexts"]}

    async def child(self, before):
        async with asyncio.timeout(7):
            while True:
                added = await self.tabs() - before
                if added:
                    assert len(added) == 1
                    return added.pop()
                await asyncio.sleep(0.05)

    async def open(self, url):
        tab = (await self.call("browsingContext.create", type="tab"))["context"]
        await self.call("browsingContext.navigate", context=tab, url=url, wait="complete")
        return tab

    async def close(self, tab):
        await self.call("browsingContext.close", context=tab)

    async def click(self, tab, selector):
        # Real WebDriver pointer activation (including when Firefox decides
        # whether to open a new tab), not synthetic DOM click for the form.
        target = json.dumps(selector)
        coords = await self.evaluate(
            tab,
            f"""JSON.stringify((() => {{
            const button = document.querySelector({target});
            if (!button || button.disabled) return null;
            button.scrollIntoView({{block: 'center'}});
            const r = button.getBoundingClientRect();
            return [Math.round(r.x+r.width/2), Math.round(r.y+r.height/2)];
        }})())""",
        )
        assert coords != "null", f"Control unavailable: {selector}"
        x, y = json.loads(coords)
        await self.call(
            "input.performActions",
            context=tab,
            actions=[
                {
                    "type": "pointer",
                    "id": "fixture-pointer",
                    "parameters": {"pointerType": "mouse"},
                    "actions": [
                        {"type": "pointerMove", "x": x, "y": y},
                        {"type": "pointerDown", "button": 0},
                        {"type": "pointerUp", "button": 0},
                    ],
                }
            ],
        )


@contextlib.asynccontextmanager
async def firefox(profile):
    executable = shutil.which(os.environ.get("AUTOMATA_FIREFOX", "firefox"))
    assert executable and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")), (
        "Visible Firefox and an available display are required"
    )
    env = dict(os.environ)
    env.pop("MOZ_HEADLESS", None)
    process = await asyncio.create_subprocess_exec(
        executable,
        "--profile",
        str(profile),
        "--no-remote",
        "--remote-debugging-port=0",
        "about:blank",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    sock = None
    browser = None
    try:
        note = profile / "WebDriverBiDiServer.json"
        async with asyncio.timeout(10):
            while not note.is_file():
                assert process.returncode is None, "Owned Firefox exited before BiDi started"
                await asyncio.sleep(0.05)
        endpoint = json.loads(note.read_text())
        port = int(endpoint["ws_port"])
        assert endpoint["ws_host"] == "127.0.0.1"
        listeners = await asyncio.to_thread(
            subprocess.check_output, ["ss", "-ltnp", f"sport = :{port}"], text=True
        )
        assert f"127.0.0.1:{port}" in listeners and f"pid={process.pid}," in listeners
        sock = await asyncio.to_thread(
            websocket.create_connection,
            f"ws://127.0.0.1:{port}/session",
            suppress_origin=True,
            timeout=4,
        )
        browser = Browser(sock)
        details = (await browser.call("session.new", capabilities={}))["capabilities"]
        assert details["browserName"] == "firefox"
        await browser.call("session.subscribe", events=["log.entryAdded"])
        print(
            f"Firefox {details['browserVersion']}: visible, disposable profile, BiDi loopback owned"
        )
        yield browser
    finally:
        if browser:
            with contextlib.suppress(
                OSError, AssertionError, TimeoutError, websocket.WebSocketException
            ):
                await browser.call("session.end")
        if sock:
            sock.close()
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 8)
            except TimeoutError:
                process.kill()
                await process.wait()
        assert process.returncode is not None


READY = "document.querySelector('#connection-status')?.textContent === 'Connected'"
SEND = "document.querySelector('#send')?.dataset.action === 'send'"
STOP = "document.querySelector('#send')?.dataset.action === 'stop'"


def transcript(text):
    return f"document.querySelector('#transcript')?.textContent.includes({json.dumps(text)})"


async def prompt(browser, tab, value):
    await browser.wait(tab, READY + " && " + SEND, "active Send mode")
    await browser.evaluate(
        tab,
        f"""(() => {{
        const field = document.querySelector('#prompt');
        field.value = {json.dumps(value)};
        field.dispatchEvent(new Event('input', {{bubbles:true}}));
    }})()""",
    )
    await browser.click(tab, "#send")


async def route(browser, tab, origin):
    path = await browser.evaluate(tab, "location.origin + location.pathname")
    assert path.startswith(origin + "/sessions/") and path.endswith("/")
    assert await browser.evaluate(tab, "!location.hash && !location.search")
    return urlsplit(path).path.split("/")[2]


async def picker_open(browser, tab, native_id):
    await browser.click(tab, "#sessions")
    await browser.wait(
        tab,
        "!!document.querySelector('#sessions-list button:not([aria-current])')",
        "saved picker row",
    )
    # Before selecting, verify the fixture list has just the target plus current.
    await browser.wait(
        tab,
        "document.querySelectorAll('#sessions-list button').length === 2",
        "bounded project picker",
    )
    await browser.click(tab, "#sessions-list button:not([aria-current])")
    await browser.wait(
        tab, "!document.querySelector('#sessions-open').disabled", "inert preview ready"
    )
    await browser.click(tab, "#sessions-open")
    await browser.wait(
        tab,
        f"location.pathname === '/sessions/{native_id}/' && {READY}",
        "same-tab saved navigation",
    )


async def exercise(host, browser):
    origin = host.runtime.origin
    a = await browser.open(host.admission_url)
    await browser.wait(a, READY, "initial session admitted")
    a_id = await route(browser, a, host.runtime.origin)
    a_entry = host._entries[a_id]
    assert a_entry.chat is host.initial_session
    before = await browser.tabs()
    await browser.click(a, "#new-chat")
    b = await browser.child(before)
    await browser.wait(b, READY, "fresh child admitted")
    b_id = await route(browser, b, host.runtime.origin)
    b_entry = host._entries[b_id]
    assert b_id != a_id and a_entry.chat.rpc.process.pid != b_entry.chat.rpc.process.pid
    assert await browser.evaluate(
        b,
        f"window.opener === null && !sessionStorage.getItem('automata.chat.admission.{a_id}') && !document.querySelector('#transcript article')",
    )
    print("PASS: native New chat opens clean independent Firefox tab on the same origin/port")

    # Browser-created duplicate intentionally inherits B's route-keyed storage;
    # the server, not frontend storage identity, must refuse its writer claim.
    await browser.evaluate(
        b,
        """(() => {
        const clone = document.createElement('button');
        clone.id = 'test-browser-duplicate'; clone.textContent = 'Fixture duplicate';
        clone.onclick = () => { const child = window.open(location.pathname, '_blank');
            if (child) child.opener = null; clone.remove(); };
        document.querySelector('.connection-controls').append(clone);
    })()""",
    )
    before = await browser.tabs()
    await browser.click(b, "#test-browser-duplicate")
    duplicate = await browser.child(before)
    await browser.wait(
        duplicate,
        "document.querySelector('#connection-detail')?.textContent.includes('open in another tab')",
        "duplicate writer refusal",
    )
    assert await browser.evaluate(
        duplicate,
        f"!!sessionStorage.getItem('automata.chat.admission.{b_id}') && document.querySelector('#prompt').disabled && document.querySelector('#new-chat').disabled && !window.awr",
    )
    await browser.close(duplicate)
    assert b_entry.chat.rpc.process.returncode is None and await browser.evaluate(b, READY)
    print("PASS: cloned storage refused as competing writer without clearing proof or evicting B")

    await prompt(browser, a, "Parallel A")
    await prompt(browser, b, "Parallel B")
    await browser.wait(
        a, STOP + " && " + transcript("Partial Parallel A"), "A live offline partial"
    )
    await browser.wait(
        b, STOP + " && " + transcript("Partial Parallel B"), "B live offline partial"
    )
    await browser.click(b, "#send")
    await browser.wait(b, SEND + " && " + transcript("Reply interrupted"), "B native Stop settled")
    await browser.wait(
        a, SEND + " && " + transcript("Offline history: Parallel A"), "A completed independently"
    )
    assert not await browser.evaluate(a, transcript("Parallel B"))
    assert not await browser.evaluate(
        b, transcript("Parallel A") + " || " + transcript("Offline history: Parallel B")
    )
    print("PASS: concurrent native offline streams; Stop B did not stop or leak into A")

    await prompt(browser, a, "UI A")
    await prompt(browser, b, "UI B")
    for tab, label in ((a, "A"), (b, "B")):
        await browser.wait(
            tab,
            f"document.querySelector('article.assistant #fixture-choice')?.textContent === 'Choose {label}'",
            f"Pi {label} generated its own live control",
        )
    await browser.click(b, "#fixture-choice")
    await browser.wait(
        b,
        SEND + " && " + transcript("Input received by Pi B: B"),
        "real tool callback received by B",
    )
    assert await browser.evaluate(a, STOP + " && !" + transcript("Input received"))
    await browser.click(a, "#fixture-choice")
    await browser.wait(
        a,
        SEND + " && " + transcript("Input received by Pi A: A"),
        "real tool callback received by A",
    )
    assert not await browser.evaluate(b, transcript("Input received by Pi A"))
    print(
        "PASS: actual native web UI tools, overlapping tool/event IDs and tab events back to their own Pi"
    )

    before_pid = b_entry.chat.rpc.process.pid
    await browser.call("browsingContext.reload", context=b, wait="complete")
    await browser.wait(
        b,
        READY + " && " + transcript("Input received by Pi B: B"),
        "B refresh restores B native history",
    )
    assert await route(browser, b, host.runtime.origin) == b_id
    assert b_entry.chat.rpc.process.pid == before_pid
    assert await browser.evaluate(
        b, "!!document.querySelector('.inactive-ui') && !document.querySelector('#fixture-choice')"
    )
    assert await browser.evaluate(a, READY + " && !!document.querySelector('#fixture-choice')")
    await browser.close(b)
    await prompt(browser, a, "A after close")
    await browser.wait(
        a, SEND + " && " + transcript("A after close"), "A remains usable after B closes"
    )
    async with asyncio.timeout(5):
        while b_entry.pair:
            await asyncio.sleep(0.05)
    print("PASS: refresh restored B without replaying UI; closing B left A usable")

    await browser.evaluate(a, "document.querySelector('#prompt').value = 'Draft belongs to A'")
    before = await browser.tabs()
    await picker_open(browser, a, b_id)
    assert await browser.tabs() == before
    assert await browser.evaluate(
        a,
        "document.querySelector('#prompt').value === '' && "
        + transcript("Input received by Pi B: B"),
    )
    await picker_open(browser, a, a_id)
    assert await browser.evaluate(
        a, "document.querySelector('#prompt').value === 'Draft belongs to A'"
    )
    await browser.call("browsingContext.reload", context=a, wait="complete")
    await browser.wait(a, READY, "A ordinary reload")
    assert await browser.evaluate(a, "document.querySelector('#prompt').value === ''")
    print(
        "PASS: saved picker navigates same tab and carries separate draft only on intentional navigation"
    )

    b = await browser.open(host.runtime.origin + b_entry.url)
    await browser.wait(b, READY, "B reattached for joint shutdown")
    await host.close()
    assert (
        a_entry.chat.rpc.process.returncode is not None
        and b_entry.chat.rpc.process.returncode is not None
    )
    await browser.wait(a, "!window.awr || window.awr.status !== 'connected'", "A bridge closed")
    await browser.wait(b, "!window.awr || window.awr.status !== 'connected'", "B bridge closed")
    with contextlib.suppress(ConnectionRefusedError):
        _, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", urlsplit(origin).port), 2
        )
        writer.close()
        await writer.wait_closed()
        raise AssertionError("Shared listener still accepts connections after shutdown")
    assert browser.errors == 0, f"Unexpected Firefox JavaScript errors: {browser.errors}"
    print(
        "PASS: joint host shutdown closed both native children, both bridges and the one listener"
    )


async def main():
    fixture = Path(__file__).with_name("web_sessions_picker.ts").resolve()
    with tempfile.TemporaryDirectory(prefix="automata-native-web-multi-") as temporary:
        root = Path(temporary)
        home, agent, project, store, profile = (
            root / name
            for name in (
                "home",
                "agent",
                "project",
                "store",
                "firefox",
            )
        )
        for directory in (home, agent, project, store, profile):
            directory.mkdir()
        with patch.dict(os.environ, {"HOME": str(home), "PI_CODING_AGENT_DIR": str(agent)}):
            os.environ.pop("PI_SESSION_FILE", None)
            host = BrowserHost()
            try:
                await host.start(
                    cwd=project,
                    provider="picker-fixture",
                    model="fixture",
                    extra_args=(
                        "--offline",
                        "--no-extensions",
                        "--no-skills",
                        "--no-prompt-templates",
                        "--no-themes",
                        "--session-dir",
                        str(store),
                        "-e",
                        str(fixture),
                    ),
                )
                async with firefox(profile) as browser:
                    await exercise(host, browser)
            finally:
                await host.close()


if __name__ == "__main__":
    asyncio.run(main())
