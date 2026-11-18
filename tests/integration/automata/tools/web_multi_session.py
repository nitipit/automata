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
from automata.tools.web.rpc import RpcRejected


class Browser:
    def __init__(self, socket):
        self.socket = socket
        self.sequence = 0
        self.errors = 0
        self.renewals = {}

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
            if reply.get("method") == "network.responseCompleted":
                event = reply["params"]
                if (
                    event["response"]["status"] == 204
                    and event["request"]["method"] == "POST"
                    and urlsplit(event["response"]["url"]).path.endswith("/browser-trust")
                ):
                    tab = event["context"]
                    self.renewals[tab] = self.renewals.get(tab, 0) + 1
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
        assert reply["type"] == "success", (
            f"Firefox page evaluation failed: {reply.get('exceptionDetails', {}).get('text')}"
        )
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
            controls: document.querySelector('#runtime-controls-status')?.textContent,
            model: document.querySelector('select[name=model]')?.value,
            thinking: document.querySelector('select[name=thinking-level]')?.value,
            messages: document.querySelector('#messages')?.textContent?.slice(-450),
        })""",
        )
        raise AssertionError(f"Did not observe {label}; disposable fixture state: {state}")

    async def wait_for_renewals(self, tab, expected):
        async with asyncio.timeout(8):
            while self.renewals.get(tab, 0) < expected:
                # BiDi wire events are drained by exchange(), not a background reader.
                await self.evaluate(tab, "document.readyState")
                await asyncio.sleep(0.05)
        assert self.renewals[tab] == expected

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

    async def key(self, tab, value):
        await self.call(
            "input.performActions",
            context=tab,
            actions=[
                {
                    "type": "key",
                    "id": "fixture-keyboard",
                    "actions": [{"type": kind, "value": value} for kind in ("keyDown", "keyUp")],
                }
            ],
        )

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
        await browser.call(
            "session.subscribe", events=["log.entryAdded", "network.responseCompleted"]
        )
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
    return f"document.querySelector('#messages')?.textContent.includes({json.dumps(text)})"


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


async def runtime_controls(browser, a, b, a_chat, b_chat):
    def model_key(model):
        return json.dumps(json.dumps(["picker-fixture", model], separators=(",", ":")))

    async def select(selector, literal):
        await browser.evaluate(
            a,
            f"""(() => {{
            const field = document.querySelector({json.dumps(selector)});
            field.value = {literal};
            field.dispatchEvent(new Event('change', {{bubbles:true}}));
        }})()""",
        )

    async def selected(tab, model, level):
        await browser.wait(
            tab,
            f"""
            !document.querySelector('select[name=model]').disabled &&
            !document.querySelector('select[name=thinking-level]').disabled &&
            document.querySelector('select[name=model]').value === {model_key(model)} &&
            document.querySelector('select[name=thinking-level]').value === {json.dumps(level)}
        """,
            f"confirmed native settings {model} / {level}",
        )

    await selected(a, "fixture", "low")
    assert await browser.evaluate(
        a,
        """
        JSON.stringify([...document.querySelectorAll('select[name=model] option:not(:disabled)')]
            .map(option => JSON.parse(option.value)[1]).sort()) === '["fixture","plain"]'
    """,
    )
    await browser.call("browsingContext.activate", context=a)
    assert await browser.evaluate(
        a,
        """(() => {
        // Constrain the actual Firefox composer, rather than resizing the desktop window.
        const composer = document.querySelector('#composer');
        const model = composer.elements.model;
        const level = composer.elements['thinking-level'];
        try {
            return [320, 390, 960].every(width => {
                composer.style.maxWidth = `${width}px`;
                const m = model.getBoundingClientRect();
                const l = level.getBoundingClientRect();
                const send = document.querySelector('#send').getBoundingClientRect();
                return composer.clientWidth <= width && composer.scrollWidth <= composer.clientWidth &&
                    m.width > 0 && l.width > 0 && m.right < l.left && l.right < send.left &&
                    m.height >= 44 && l.height >= 44 && Math.abs(l.bottom - send.bottom) < 1;
            });
        } finally { composer.style.removeProperty('max-width'); }
    })()""",
    )
    await browser.evaluate(a, "document.querySelector('#prompt').focus()")
    await browser.key(a, "\ue004")  # WebDriver Tab
    assert await browser.evaluate(
        a,
        "document.activeElement.matches('ui-select > select[name=model]') && "
        "document.activeElement.labels[0].textContent === 'Model'",
    )
    await browser.key(a, "\ue004")
    assert await browser.evaluate(
        a,
        "document.activeElement.matches('ui-select > select[name=thinking-level]') && "
        "document.activeElement.labels[0].textContent === 'Thinking' && "
        "document.activeElement.labels[0].control === document.activeElement",
    )
    await select("select[name=model]", model_key("plain"))
    await selected(a, "plain", "off")
    assert await browser.evaluate(
        a, "document.querySelector('select[name=thinking-level]').options.length === 1"
    )
    await select("select[name=model]", model_key("fixture"))
    await selected(a, "fixture", "off")  # The prior level remains supported on this model.

    # Inject exactly one negative mutation response at A's Pi RPC boundary;
    # catalog validation, native read-back, WebSocket ack, and the UI remain real.
    native_command = a_chat.rpc.command
    refused = []

    async def refuse_high(kind, **kwargs):
        if kind == "set_thinking_level" and kwargs.get("level") == "high":
            refused.append(kind)
            raise RpcRejected("Fixture refusal")
        return await native_command(kind, **kwargs)

    await browser.evaluate(
        a,
        """(() => {
            const draft = document.querySelector('#prompt');
            draft.value = 'Retain this draft';
            draft.dispatchEvent(new Event('input', {bubbles: true}));
            const level = document.querySelector('select[name=thinking-level]');
            window.levelBeforeRefusal = level;
            level.addEventListener('change', event => {
                window.trustedLevelChange = event.isTrusted && event.target.value === 'high';
            }, {capture: true, once: true});
            level.focus();
        })()""",
    )
    with patch.object(a_chat.rpc, "command", new=refuse_high):
        await browser.key(a, "h")  # Firefox type-ahead selects High on the native control.
        await browser.wait(
            a,
            "document.querySelector('#runtime-controls-status').textContent.includes('Pi did not complete')",
            "native settings refusal reached the composer",
        )
    assert refused == ["set_thinking_level"]
    await selected(a, "fixture", "off")
    assert await browser.evaluate(
        a,
        "trustedLevelChange === true && "
        "levelBeforeRefusal === document.querySelector('select[name=thinking-level]') && "
        "document.querySelector('#prompt').value === 'Retain this draft'",
    )
    assert (await a_chat.rpc.command("get_state"))["thinkingLevel"] == "off"
    print(
        "PASS: trusted Firefox keyboard change; RPC refusal preserves confirmed settings, "
        "control node and draft"
    )

    await select("select[name=thinking-level]", json.dumps("high"))
    await selected(a, "fixture", "high")
    assert (await a_chat.rpc.command("get_state"))["thinkingLevel"] == "high"
    assert (await b_chat.rpc.command("get_state"))["thinkingLevel"] == "low"
    await selected(b, "fixture", "low")
    # Observe the DOM synchronously at the end of the submit event, before any WS echo.
    await browser.evaluate(a, """document.addEventListener('submit', () => {
        const rows = [...document.querySelectorAll('#messages > chat-message > article')].slice(-2);
        window.firstTurnOrdered = rows.length === 2 && rows[0].matches('.user') &&
          rows[0].querySelector('.message-body').textContent === 'Fixture runtime settings' &&
          !!rows[1].querySelector('.reply-activity');
    }, {once:true})""")
    await prompt(browser, a, "Fixture runtime settings")
    assert await browser.evaluate(a, "window.firstTurnOrdered === true"), "first render order"
    await browser.wait(
        a,
        SEND + " && " + transcript("Native next message: fixture / high"),
        "next native message uses confirmed settings",
    )
    assert await browser.evaluate(a, """[...document.querySelectorAll('.user .message-body')]
        .filter(node => node.textContent === 'Fixture runtime settings').length === 1""")
    await browser.call("browsingContext.activate", context=b)
    await prompt(browser, b, "Fixture runtime settings")
    await browser.wait(
        b,
        SEND + " && " + transcript("Native next message: fixture / low"),
        "other chat's next native message uses its own unchanged settings",
    )
    assert not await browser.evaluate(a, transcript("Native next message: fixture / low"))
    assert not await browser.evaluate(b, transcript("Native next message: fixture / high"))
    print(
        "PASS: exact pins, responsive label and keyboard checks, "
        "both chats' next prompts use their own confirmed settings"
    )


async def streaming_descriptor(browser, tab, project):
    await browser.call("browsingContext.activate", context=tab)
    await prompt(browser, tab, "Stream descriptor child")
    await browser.wait(tab, STOP + " && " + transcript("Descriptor stream started"), "native first text delta")
    assert await browser.evaluate(tab, """(async () => {
        const ui = await import('/assets/ui.js');
        const { createComponent } = ui;
        const root = window.automataUI.context('descriptor-stream-owner').root;
        const article = root.closest('article');
        const descriptor = { _class: 'ui-card', _children: [
          { _class: 'ui-button', _data: { text: 'Activate first' } },
          { _class: 'ui-button', _data: { text: 'Activate second' } },
        ] };
        // Exercise the private named factory without adding an application test export.
        const detached = article.parentElement.constructor.create({
          _data: { role: 'assistant', text: '**Owned body**' }, _children: [descriptor],
        });
        const descriptorMounted = detached.querySelector('article > .message-body strong')?.textContent === 'Owned body' &&
          detached.querySelector('article > .message-ui > ui-card > ui-button + ui-button')?.textContent === 'Activate second';
        const child = createComponent(descriptor);
        root.append(child);
        const [first, second] = child.querySelectorAll('button');
        let clicks = 0;
        first.addEventListener('click', () => clicks++);
        first.focus();
        window.checkStreamingChild = (expectedClicks) =>
          root.closest('article') === article && article.parentElement.matches('chat-message') &&
          article.querySelector('.message-body').textContent.includes('Descriptor stream started') &&
          article.querySelector('.message-ui > .generated-content') === root && root.firstElementChild === child &&
          [...child.querySelectorAll('button')].every((node, i) => node === [first, second][i]) &&
          first.textContent === 'Activate first' && second.textContent === 'Activate second' &&
          document.activeElement === first && clicks === expectedClicks;
        const isPrivate = tag => {
          try { createComponent({ _class: tag }); }
          catch (error) { return error instanceof TypeError && error.message.includes('unknown component tag'); }
          return false;
        };
        return descriptorMounted && !('ChatComposer' in ui) && isPrivate('chat-composer') &&
          isPrivate('chat-message') && window.checkStreamingChild(0);
    })()""")
    (project / ".fixture-stream-update").touch()
    updated = transcript("Descriptor stream started and updated")
    await browser.wait(tab, STOP + " && " + updated, "native subsequent delta before settlement")
    assert await browser.evaluate(tab, "window.checkStreamingChild(0)")
    await browser.key(tab, "\ue007")  # Enter uses the same focused native button and its original listener.
    assert await browser.evaluate(tab, "window.checkStreamingChild(1)")
    (project / ".fixture-stream-finish").touch()
    await browser.wait(tab, SEND + " && " + updated, "native descriptor reply settlement")
    assert await browser.evaluate(tab, "window.checkStreamingChild(1)")
    await browser.evaluate(tab, "delete window.checkStreamingChild")
    print("PASS: private native article with ordered descriptor-built children; identity, focus and handler survive same-message streaming")


async def exercise(host, browser, project):
    origin = host.runtime.origin
    a = await browser.open(host.admission_url)
    await browser.wait(a, READY, "initial session admitted")
    a_id = await route(browser, a, host.runtime.origin)
    a_entry = host._entries[a_id]
    assert a_entry.chat is host.initial_session
    await browser.wait_for_renewals(a, 1)
    # Exercise focus catch-up under a browser-only accelerated clock. The host
    # clock and HTTP request/authentication remain real; no address-bar claim.
    await browser.evaluate(
        a,
        """(() => {
        const realNow = Date.now;
        Date.now = () => realNow() + 10 * 60_000 + 1000;
        try { window.dispatchEvent(new Event('focus')); }
        finally { Date.now = realNow; }
    })()""",
    )
    await browser.wait_for_renewals(a, 2)
    print("PASS: paired writer minted trust over HTTP; accelerated focus catch-up renewed it")
    before = await browser.tabs()
    await browser.click(a, "#new-chat")
    b = await browser.child(before)
    await browser.wait(b, READY, "fresh child admitted")
    b_id = await route(browser, b, host.runtime.origin)
    b_entry = host._entries[b_id]
    assert b_id != a_id and a_entry.chat.rpc.process.pid != b_entry.chat.rpc.process.pid
    assert await browser.evaluate(
        b,
        f"window.opener === null && !sessionStorage.getItem('automata.chat.admission.{a_id}') && !document.querySelector('#messages article')",
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

    await runtime_controls(browser, a, b, a_entry.chat, b_entry.chat)
    await browser.call("browsingContext.activate", context=a)
    await browser.evaluate(a, "window.fixtureEditor = document.querySelector('chat-composer textarea'); fixtureEditor.focus(); fixtureEditor.value = 'Parallel A'; fixtureEditor.setSelectionRange(10,10)")
    await browser.call("input.performActions", context=a, actions=[{"type": "key", "id": "composer-keys", "actions": [
        {"type": "keyDown", "value": "\ue008"}, {"type": "keyDown", "value": "\ue007"},
        {"type": "keyUp", "value": "\ue007"}, {"type": "keyUp", "value": "\ue008"},
    ]}])
    assert await browser.evaluate(a, SEND + " && fixtureEditor.value === 'Parallel A\\n'")
    await browser.key(a, "\ue007")  # One submission; submitted text is trimmed.
    await browser.wait(a, STOP + " && fixtureEditor.value === ''", "Enter accepted the prompt")
    await prompt(browser, b, "Parallel B")
    await browser.wait(
        a, STOP + " && " + transcript("Partial Parallel A"), "A live offline partial"
    )
    await browser.wait(
        b, STOP + " && " + transcript("Partial Parallel B"), "B live offline partial"
    )
    for tab in (a, b):
        assert await browser.evaluate(
            tab,
            "document.querySelector('select[name=model]').disabled && document.querySelector('select[name=thinking-level]').disabled && !document.querySelector('#send').disabled",
        )
    await browser.click(b, "#send")
    await browser.wait(b, SEND + " && " + transcript("Reply interrupted"), "B native Stop settled")
    await browser.call("browsingContext.activate", context=a)
    await browser.evaluate(a, "fixtureEditor.focus(); fixtureEditor.value='Next draft'; fixtureEditor.dispatchEvent(new Event('input',{bubbles:true}))")
    await browser.wait(
        a,
        SEND + " && " + transcript("Offline history: Fixture runtime settings | Parallel A"),
        "A completed independently",
    )
    assert await browser.evaluate(a, "fixtureEditor === document.activeElement && fixtureEditor === document.querySelector('chat-composer textarea') && fixtureEditor.value === 'Next draft' && [...document.querySelectorAll('article.user .message-body')].filter(node => node.textContent === 'Parallel A').length === 1")
    print("PASS: Shift+Enter inserts a newline, Enter sends once, and reply settlement preserves draft, node and focus")
    assert not await browser.evaluate(a, transcript("Parallel B"))
    assert not await browser.evaluate(
        b, transcript("Parallel A") + " || " + transcript("Offline history: Parallel B")
    )
    print("PASS: concurrent native offline streams; Stop B did not stop or leak into A")

    await streaming_descriptor(browser, a, project)

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
    await browser.wait_for_renewals(b, 1)
    await browser.call("browsingContext.activate", context=b)
    await browser.call("browsingContext.reload", context=b, wait="complete")
    await browser.wait(
        b,
        READY + " && " + transcript("Input received by Pi B: B"),
        "B refresh restores B native history",
    )
    assert await route(browser, b, host.runtime.origin) == b_id
    assert b_entry.chat.rpc.process.pid == before_pid
    await browser.wait_for_renewals(b, 2)
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

    heading = await browser.evaluate(a, "document.title")
    title_rect = """(() => {
      const row = document.querySelector('.session-title');
      return JSON.stringify([row.offsetLeft, row.offsetTop, row.offsetWidth, row.offsetHeight]);
    })()"""
    before_rename = await browser.evaluate(a, title_rect)
    await browser.click(a, "#session-name")
    assert await browser.evaluate(a, title_rect) == before_rename
    assert await browser.evaluate(a, "document.activeElement.id === 'session-name-input'")
    await browser.evaluate(a, "document.activeElement.value = 'Canceled title'")
    await browser.key(a, "\ue00c")  # WebDriver Escape
    assert await browser.evaluate(
        a, "document.querySelector('#rename-form').hidden && document.activeElement.id === 'rename'"
    )
    assert await browser.evaluate(a, "document.title") == heading
    await browser.key(a, "\ue007")  # WebDriver Enter activates the focused pencil.
    assert await browser.evaluate(a, "document.activeElement.id === 'session-name-input'")
    await browser.evaluate(a, "document.activeElement.value = 'Enter title'")
    await browser.key(a, "\ue007")
    await browser.wait(
        a,
        "document.title === 'Enter title' && document.querySelector('#rename-form').hidden",
        "native Enter rename confirmed",
    )
    await browser.click(a, "#rename")
    await browser.evaluate(a, "document.activeElement.value = 'Blur title'")
    await browser.click(a, "#prompt")
    await browser.wait(
        a,
        "document.title === 'Blur title' && document.querySelector('#rename-form').hidden",
        "native blur rename confirmed",
    )
    assert await browser.evaluate(a, "document.activeElement.id === 'prompt'")
    assert (await a_entry.chat.rpc.command("get_state"))["sessionName"] == "Blur title"
    print(
        "PASS: inline title/pencil activation, no row shift, Escape, native Enter/blur confirmation and focus"
    )

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
    assert await browser.evaluate(
        a, "document.querySelector('#prompt').value === '' && document.title === 'Blur title'"
    )
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
        settings = agent / "settings.json"
        settings.write_text(
            json.dumps(
                {
                    "defaultThinkingLevel": "low",
                    "enabledModels": ["picker-fixture/fixture", "picker-fixture/plain"],
                }
            )
        )
        settings_before = settings.read_bytes()
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
                    await exercise(host, browser, project)
            finally:
                await host.close()
        assert settings.read_bytes() == settings_before


if __name__ == "__main__":
    asyncio.run(main())
