"""Actual upstream bridge + guarded host, controlled native-event fixtures only.

PYTHONPATH=src:$PWD/.venv/lib/python3.13/site-packages \
 /home/nitipit/.local/share/uv/tools/automata/bin/python \
 src/automata/tools/web/frontend/_tests/reconnect_runtime.py
"""
# ruff: noqa: E501 -- browser fixtures are easier to review as complete sequences.
import asyncio
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from automata.tools.web.host import BrowserHost


class InertRpc:
    def __init__(self, project):
        self.session = project / "fixture.jsonl"
        self.starts = 0
        self.commands = []
        self.partial = None
        self.abort_gate = asyncio.Event()
        self.abort_gate.set()
        self.history = [
            {"role": "user", "content": [{"type": "text", "text": "<b>Native first message</b>\nภาษาไทย 🐈 " + "long " * 20}]},
            {"role": "assistant", "content": [{"type": "toolCall", "id": "old-ui"}]},
            {"role": "toolResult", "toolCallId": "old-ui", "details": {"ui": {"blockId": "old-ui", "toolCallId": "old-ui"}}},
        ]

    async def start(self, *_args, **_kwargs):
        self.starts += 1

    async def command(self, kind, **data):
        self.commands.append(kind)
        if kind in {"prompt", "steer", "follow_up"}:
            raise AssertionError("Model test prompts are not authorized")
        if kind == "get_messages":
            return {"messages": list(self.history)}
        if kind == "get_state":
            return {"sessionId": "owned-fixture-session", "sessionFile": str(self.session), "sessionName": getattr(self, "name", None)}
        if kind == "set_session_name":
            self.name = data["name"]
            self.host.on_event({"type": "session_info_changed", "name": self.name})
        if kind == "abort":
            await self.abort_gate.wait()
            if self.partial:
                self.host.on_event({"type": "message_end", "message": self.partial})
                self.partial = None
                self.host.on_event({"type": "agent_settled"})
        return {}

    async def close(self):
        pass

    async def send(self, _record):
        pass


SOCKET_OBSERVER = """(() => {
 const NativeSocket=window.WebSocket; window.fixtureSockets=[];
 window.WebSocket=class extends NativeSocket { constructor(...args){super(...args);window.fixtureSockets.push(this);} };
})();"""


async def ready(page):
    try:
        await page.wait_for_function("document.querySelector('#connection-status')?.textContent==='Connected' && !document.querySelector('#sessions').disabled")
    except Exception:
        print(await page.evaluate("({connection:document.querySelector('#connection-status')?.textContent,detail:document.querySelector('#connection-detail')?.textContent,status:document.querySelector('#run-status')?.textContent,bridge:window.awr?.status,sockets:window.fixtureSockets?.map(s=>({path:new URL(s.url).pathname,state:s.readyState}))})"))
        raise


async def wait_released(entry):
    for _ in range(300):
        if entry.pair is None:
            return
        await asyncio.sleep(.02)
    raise AssertionError("Owned fixture connection cleanup did not settle")


async def main():
    temporary = TemporaryDirectory(prefix="automata-reconnect-browser-")
    project = Path(temporary.name)
    rpc = InertRpc(project)
    server = BrowserHost(rpc_factory=lambda _handler: rpc, pair_seconds=2)
    checks = []
    try:
        await server.start(cwd=project)
        host = rpc.host = server.initial_session
        entry = server._entries[host.id]
        route = server.runtime.origin + f"/sessions/{host.id}/"
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
            try:
                context = await browser.new_context(user_agent="Automata/1.0", viewport={"width": 390, "height": 844})
                await context.add_init_script(SOCKET_OBSERVER)
                page = await context.new_page()
                errors = []
                admission_statuses = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("response", lambda response: admission_statuses.append(response.status) if response.url.endswith('/chat/connection') else None)
                # No credential: never try a socket or create an agent.
                await page.goto(route)
                await page.wait_for_function("document.querySelector('#connection-detail')?.textContent.includes('Missing access')")
                assert await page.evaluate("fixtureSockets.length===0 && document.querySelector('#connect').disabled && document.title==='Untitled session'")
                checks.append("no-token initial load is explicit and inert")
                await page.goto(server.admission_url)
                await ready(page)
                assert await page.evaluate("location.hash==='' && !!sessionStorage.getItem('automata.chat.admission.owned-fixture-session')")
                expected = await page.locator("#session-name").text_content()
                assert expected.startswith("<b>Native first message</b> ภาษาไทย 🐈") and expected.endswith("…")
                assert await page.title() == expected
                assert await page.locator("#session-name b").count() == 0
                assert await page.locator(".panel-heading").count() == 0
                assert await page.locator("#conversation[aria-label=Conversation]").count() == 1
                assert await page.locator(".inactive-ui").count() == 1
                assert await page.evaluate("document.documentElement.scrollWidth<=innerWidth && document.querySelector('#rename').getBoundingClientRect().left-document.querySelector('#session-name').getBoundingClientRect().right<10")
                assert await page.get_by_role("button", name="Rename session").get_attribute("title") == "Rename session"
                checks.append("literal native-first-user heading/tab and compact accessible mobile header")
                await page.reload()
                await ready(page)
                assert await page.title() == expected and rpc.starts == 1
                assert await page.evaluate("fixtureSockets.some(x=>new URL(x.url).pathname==='/ws'&&x.readyState===1) && fixtureSockets.some(x=>new URL(x.url).pathname==='/sessions/owned-fixture-session/chat'&&x.readyState===1)")
                checks.append("refresh restores credential before actual bridge and chat; same agent")
                # Test real keyboard naming, then native name event priority and fallback.
                await page.get_by_role("button", name="Rename session").click()
                await page.get_by_label("Session name", exact=True).fill("Explicit <saved> 🐈")
                await page.get_by_label("Session name", exact=True).press("Enter")
                await page.wait_for_function("document.title==='Explicit <saved> 🐈'")
                host.on_event({"type": "session_info_changed", "name": "External saved name"})
                await page.wait_for_function("document.title==='External saved name'")
                host.on_event({"type": "session_info_changed"})
                await page.wait_for_function("document.title.startsWith('<b>Native')")
                checks.append("Enter rename/name-event priority and cleared-name fallback")
                # A live owned UI becomes historical/inactive after losing its bridge.
                owned = {"role": "assistant", "content": [{"type": "text", "text": "Owned UI fixture"}, {"type": "toolCall", "id": "live-before-drop"}]}
                host.on_event({"type": "agent_start"})
                host.on_event({"type": "message_start", "message": owned})
                host.on_event({"type": "message_end", "message": owned})
                host.on_event({"type": "message_end", "message": {"role": "toolResult", "toolCallId": "live-before-drop", "details": {"ui": {"blockId": "live-before-drop", "toolCallId": "live-before-drop"}}}})
                host.on_event({"type": "agent_settled"})
                await page.wait_for_function("document.querySelector('#messages').textContent.includes('Owned UI fixture')")
                await page.evaluate("window.fixtureRoot=window.automataUI.context('live-before-drop').root; window.fixtureExecutions=0; const button=document.createElement('button');button.textContent='Owned fixture control';button.onclick=()=>window.fixtureExecutions++;fixtureRoot.append(button)")
                # Controlled partial message, never a prompt. Hold abort to verify reservation.
                rpc.abort_gate.clear()
                rpc.partial = {"role": "assistant", "content": [{"type": "text", "text": "Owned partial reply"}], "stopReason": "aborted"}
                host.on_event({"type": "agent_start"})
                host.on_event({"type": "message_start", "message": {"role": "assistant", "content": []}})
                host.on_event({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": "Owned partial reply"}})
                await page.wait_for_function("document.querySelector('.reply-activity')?.closest('article').textContent.includes('Owned partial reply')")
                await page.evaluate("fixtureSockets.find(x=>new URL(x.url).pathname.endsWith('/chat')&&x.readyState===1).close()")
                await page.wait_for_function("document.querySelector('#connection-status').textContent==='Connecting…'")
                for _ in range(100):
                    if host.state["status"] == "stopping":
                        break
                    await asyncio.sleep(.01)
                assert entry.pair is not None and host.state["status"] == "stopping"
                for _ in range(100):
                    if 409 in admission_statuses:
                        break
                    await asyncio.sleep(.01)
                assert 409 in admission_statuses
                rpc.abort_gate.set()
                await ready(page)
                assert await page.locator(".reply-outcome").filter(has_text="interrupted").count() == 1
                assert "Owned partial reply" in await page.locator("#messages").text_content()
                assert await page.locator(".reply-activity").count() == 0
                assert await page.locator(".inactive-ui").count() == 2
                assert await page.locator(".generated-content").count() == 0
                assert await page.evaluate("!fixtureRoot.isConnected && fixtureRoot.inert && fixtureExecutions===0")
                checks.append("chat drop interrupts partial; cleanup reservation; native snapshot restores outcome and inactive UI without replay")
                rpc.partial = {"role": "assistant", "content": [{"type": "text", "text": "Partial interrupted by refresh"}], "stopReason": "aborted"}
                host.on_event({"type": "agent_start"})
                host.on_event({"type": "message_start", "message": {"role": "assistant", "content": []}})
                host.on_event({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": "Partial interrupted by refresh"}})
                await page.wait_for_function("document.querySelector('.reply-activity')?.closest('article').textContent.includes('Partial interrupted by refresh')")
                await page.reload()
                await ready(page)
                assert await page.locator(".reply-outcome").filter(has_text="interrupted").count() == 2
                assert "Partial interrupted by refresh" in await page.locator("#messages").text_content()
                assert rpc.starts == 1
                checks.append("refresh interrupts active reply and restores native partial/outcome without prompt replay")
                # Drop upstream bridge itself: fresh actual class must reconnect both sockets.
                await page.evaluate("window.oldFixtureBridge=window.awr; window.awr.close()")
                await page.wait_for_function("window.awr!==window.oldFixtureBridge && window.awr.status==='connected'")
                await ready(page)
                assert rpc.starts == 1
                checks.append("terminal upstream bridge replaced; both connections recover without Pi restart")
                # Exhaust a bounded admission window, then exercise repeated manual Retry clicks.
                probes = []
                async def unavailable(route):
                    probes.append(1)
                    await route.fulfill(status=503, body="unavailable")
                await page.route("**/chat/connection", unavailable)
                await page.evaluate("fixtureSockets.find(x=>new URL(x.url).pathname.endsWith('/chat')&&x.readyState===1).close()")
                await page.wait_for_function("document.querySelector('#connection-status').textContent==='Disconnected' && !document.querySelector('#connect').disabled", timeout=25000)
                assert len(probes) == 5
                await asyncio.sleep(.6)
                assert len(probes) == 5
                await page.unroute("**/chat/connection", unavailable)
                await page.evaluate("for(let i=0;i<5;i++)document.querySelector('#connect').click()")
                await ready(page)
                assert await page.evaluate("fixtureSockets.filter(x=>new URL(x.url).pathname.endsWith('/chat')&&x.readyState===1).length===1 && fixtureSockets.filter(x=>new URL(x.url).pathname==='/ws'&&x.readyState===1).length===1")
                checks.append("bounded automatic attempts; explicit Retry; duplicate clicks create no duplicate sockets")
                for width in (1280, 390):
                    await page.set_viewport_size({"width": width, "height": 900})
                    assert await page.evaluate("document.documentElement.scrollWidth<=innerWidth")
                    rect = await page.locator("#rename").bounding_box()
                    assert rect["width"] >= 44 and rect["height"] >= 44
                checks.append("desktop/mobile no overflow and 44px edit target")
                assert not errors, errors
                assert not any(x in rpc.commands for x in ("prompt", "steer", "follow_up")) and rpc.starts == 1
                await context.close()
                await wait_released(entry)
                # Interrupt the first bridge script after authenticated pairing
                # but before either socket can claim the short-lived ticket.
                interrupted = await browser.new_context(user_agent="Automata/1.0")
                await interrupted.add_init_script(SOCKET_OBSERVER)
                loading = await interrupted.new_page()
                bridge_requested, release_request = asyncio.Event(), asyncio.Event()
                interrupted_probes = []
                loading.on("response", lambda response: interrupted_probes.append(response.status) if response.url.endswith('/chat/connection') else None)

                async def hold_bridge(request):
                    bridge_requested.set()
                    await release_request.wait()
                    with suppress(PlaywrightError):
                        await request.abort()

                await loading.route("**/bridge.js", hold_bridge, times=1)
                try:
                    await loading.goto(server.admission_url, wait_until="domcontentloaded")
                    await asyncio.wait_for(bridge_requested.wait(), 5)
                    assert await loading.evaluate("location.hash.startsWith('#token=') && !location.hash.includes('admission=') && fixtureSockets.length===0")
                    admission_remained = """() => {
                        const proof = sessionStorage.getItem('automata.chat.admission.owned-fixture-session');
                        return !!proof && proof !== new URLSearchParams(location.hash.slice(1)).get('token');
                    }"""
                    assert await loading.evaluate(admission_remained)
                    await loading.reload(wait_until="domcontentloaded")
                    await ready(loading)
                    assert 409 in interrupted_probes and interrupted_probes.count(200) == 2
                    assert await loading.evaluate(admission_remained)
                    assert await loading.evaluate("location.hash === '' && fixtureSockets.length === 2")
                    assert rpc.starts == 1
                finally:
                    release_request.set()
                    await interrupted.close()
                await wait_released(entry)
                checks.append("interrupted initial bridge lease expires; reload keeps scoped admission and pairs once")
                # Bad credentials are terminal, clear storage and do not hot-loop.
                rejected = await browser.new_context(user_agent="Automata/1.0")
                await rejected.add_init_script(SOCKET_OBSERVER)
                bad = await rejected.new_page()
                requests = []
                bad.on("request", lambda request: requests.append(1) if request.url.endswith("/chat/connection") else None)
                await bad.goto(route + "#admission=owned-invalid-fixture")
                await bad.wait_for_function("document.querySelector('#connection-detail')?.textContent.includes('rejected or expired')")
                assert await bad.evaluate("location.hash==='' && sessionStorage.getItem('automata.chat.admission.owned-fixture-session')===null && document.querySelector('#connect').disabled")
                await asyncio.sleep(.6)
                assert len(requests) == 1 and rpc.starts == 1
                await rejected.close()
                checks.append("rejected credential is actionable terminal state, no retry loop/new agent")
                print("PASS actual guarded reconnect (inert RPC/no prompts):", "; ".join(checks))
            finally:
                await browser.close()
    finally:
        rpc.abort_gate.set()
        try:
            await server.close()
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
