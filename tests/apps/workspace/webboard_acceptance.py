"""Real-browser sandbox and event checks; transport/replies remain explicitly MOCK."""
import json
from pathlib import Path

from playwright.sync_api import expect


def surface(page):
    return page.locator("wsp-root").locator("wsp-surface")


def frame_for(page):
    return surface(page).locator("iframe").element_handle().content_frame()


def proposal(page, frame, **overrides):
    generation = surface(page).evaluate("element => element.generation")
    value = {"kind": "workspace.board-proposal", "version": 1,
             "generation": generation, "componentId": "test-probe",
             "operationId": "probe-operation", "text": "A bounded test proposal", **overrides}
    frame.evaluate("value => parent.postMessage(value, '*')", value)


def verify_board(context, url: str, evidence: Path | None) -> None:
    page = context.new_page()
    page.goto(f"{url}/project-northstar/", wait_until="networkidle")
    board = frame_for(page)
    expect(board.locator("h2")).to_have_text("Hello, workspace!")
    expect(board.locator("#notify")).to_be_enabled()
    before = page.request.get(f"{url}/api/state").json()
    board.locator("#add").click()
    board.locator("#add").click()
    expect(board.locator("output")).to_have_text("Count: 2")
    assert page.evaluate("mockRouter.requests.length") == 0
    board.locator("#notify").click()
    expect(surface(page).locator(".preview")).to_contain_text("counter is 2")
    assert page.evaluate("mockRouter.requests.length") == 0  # proposal is not authority
    surface(page).locator(".confirm").click()
    expect(board.locator("#reply")).to_contain_text("Mock board acknowledgement <script>")
    payload = page.evaluate("mockRouter.requests[0].payload")
    assert payload["kind"] == "workspace.webboard-event"
    assert payload["origin"] == {"projectId": "project-northstar", "webboardId": "main"}
    assert payload["actor"] == {"kind": "local-user", "id": "local-user",
                                "authority": "host-confirmed-notification"}
    assert payload["target"] == {"agentId": "agent-automata", "participant": "workspace-agent"}
    assert payload["componentId"] == "demo-counter"
    preview = surface(page).locator(".preview").inner_text()
    for reviewed in (payload["projectId"], payload["webboardId"], payload["componentId"],
                     payload["operationId"], payload["action"], payload["text"]):
        assert reviewed in preview
    assert "conversationId" not in payload
    assert page.request.get(f"{url}/api/state").json() == before
    assert board.locator("#reply script").count() == 0

    # Browser enforcement (not merely inspecting sandbox attributes).
    denial = board.evaluate("""async () => {
      const result = {};
      try { parent.document.querySelector('wsp-root'); result.parent = 'LEAK'; }
      catch { result.parent = 'blocked'; }
      try { localStorage.setItem('probe', 'x'); result.storage = 'LEAK'; }
      catch { result.storage = 'blocked'; }
      for (const path of ['/api/state', '/api/agent-binding', '/api/agent-lifecycle']) {
        try { await fetch(path, {credentials:'include'}); result[path] = 'LEAK'; }
        catch { result[path] = 'blocked'; }
      }
      try { new WebSocket('ws://127.0.0.1:9'); result.websocket = 'created'; }
      catch { result.websocket = 'blocked'; }
      result.popup = window.open('about:blank') === null ? 'blocked' : 'LEAK';
      try { top.location.href = '/api/agent-binding'; result.top = 'LEAK'; }
      catch { result.top = 'blocked'; }
      return result;
    }""")
    # Init-script mock replaces WebSocket even inside frames; do not claim a real
    # WebSocket denial from this context. A clean context below checks actual CSP.
    assert all(value == "blocked" for key, value in denial.items() if key != "websocket"), denial
    clean = context.browser.new_context()
    # Keep the unmocked browser network probe isolated too: the host must not try
    # the synthetic fixture's router URL (which could collide with a live port).
    clean.route("**/api/agent-binding", lambda route:
                route.fulfill(json={"binding": None}) if route.request.resource_type == "fetch"
                else route.continue_())
    probe = clean.new_page()
    probe.goto(f"{url}/project-northstar/", wait_until="networkidle")
    clean_board = frame_for(probe)
    websocket = clean_board.evaluate("""() => new Promise(resolve => {
      document.addEventListener('securitypolicyviolation', event => {
        if (event.effectiveDirective === 'connect-src') resolve('CSP connect-src');
      }, {once:true});
      try {
        const socket = new WebSocket('ws://127.0.0.1:9');
        socket.onopen = () => resolve('LEAK');
      } catch { /* Wait for policy violation evidence, not generic socket error. */ }
      setTimeout(() => resolve('no policy evidence'), 2000);
    })""")
    assert websocket == "CSP connect-src"
    # Forms are independently blocked; script/image/private API subresources
    # cannot read credentials even when their URL has the host's origin.
    form_requests = []
    probe.on("request", lambda request: form_requests.append(request.url)
             if request.method == "POST" else None)
    form_result = clean_board.evaluate("""() => {
      const form = document.createElement('form'); form.action='/api/agent-lifecycle/start';
      form.method='POST'; document.body.append(form); form.submit();
      return location.pathname;
    }""")
    assert form_result == "/boards/project-northstar/main/index.html"
    script_result = clean_board.evaluate("""() => new Promise(resolve => {
      const script = document.createElement('script'); script.src='/api/agent-binding';
      script.onerror=() => resolve('blocked'); script.onload=() => resolve('LEAK');
      document.head.append(script);
    })""")
    assert script_result == "blocked"
    assert not form_requests and clean_board.url.endswith("/main/index.html")
    clean.close()

    # Host rejects absent/wrong source, claimed identity, excessive JSON and replay.
    # Let the independent rate guard expire so these actually exercise validation.
    page.wait_for_function("""() => performance.now() - document.querySelector('wsp-root')
      .shadowRoot.querySelector('wsp-surface').lastProposal >= 1000""")
    page.evaluate("""() => window.postMessage({kind:'workspace.board-proposal',version:1,
      generation:document.querySelector('wsp-root').shadowRoot.querySelector('wsp-surface').generation,
      componentId:'spoof',operationId:'spoof',text:'not from board'}, '*')""")
    proposal(page, board, operationId="wrong-generation", generation="wrong")
    proposal(page, board, operationId="spoof-origin", projectId="project-other")
    proposal(page, board, operationId="oversized", text="x" * 2001)
    proposal(page, board, operationId=payload["operationId"])
    expect(surface(page).locator(".confirm")).to_be_hidden()
    assert page.evaluate("mockRouter.requests.length") == 1

    # Reload is passive; no router replay, counter resets, saved state unchanged.
    page.reload(wait_until="networkidle")
    board = frame_for(page)
    expect(board.locator("output")).to_have_text("Count: 0")
    assert page.evaluate("mockRouter.requests.length") == 0
    page.evaluate("mockRouter.mode = 'bad-board-reply'")
    board.locator("#notify").click()
    surface(page).locator(".confirm").click()
    expect(surface(page).locator(".status")).to_contain_text("Invalid correlated text-only")
    expect(board.locator("#reply")).not_to_contain_text("Rejected")

    # A proposal awaiting human confirmation loses authority on navigation too.
    page.reload(wait_until="networkidle")
    board = frame_for(page)
    board.locator("#notify").click()
    expect(surface(page).locator(".confirm")).to_be_visible()
    board.evaluate("location.href = 'about:blank'")
    expect(surface(page).locator(".confirm")).to_be_hidden()
    expect(surface(page).locator(".status")).to_contain_text("capability is revoked")
    assert page.evaluate("mockRouter.requests.length") == 0

    # A held request times out conservatively and releases in-flight state.
    # Shorten only the documented response timeout, not lifecycle/recovery timers.
    page.reload(wait_until="networkidle")
    board = frame_for(page)
    page.evaluate("""() => {
      mockRouter.mode='hold';
      const original = window.setTimeout;
      window.setTimeout = (fn, delay, ...args) =>
        original(fn, delay===120000 ? 50 : delay, ...args);
    }""")
    board.locator("#notify").click()
    surface(page).locator(".confirm").click()
    expect(surface(page).locator(".status")).to_contain_text("timed out; outcome uncertain")
    assert surface(page).evaluate(
        "element => element.inFlight === false && element.pending === null")
    assert page.evaluate("mockRouter.requests.length") == 1

    # Dismissal consumes an operation; the one-second rate guard still applies.
    page.reload(wait_until="networkidle")
    board = frame_for(page)
    board.locator("#notify").click()
    operation = surface(page).evaluate("element => element.pending.operationId")
    surface(page).locator(".dismiss").click()
    proposal(page, board, operationId="too-fast")
    expect(surface(page).locator(".confirm")).to_be_hidden()
    assert surface(page).evaluate("element => element.used.size") == 1
    page.wait_for_function("""() => performance.now() - document.querySelector('wsp-root')
      .shadowRoot.querySelector('wsp-surface').lastProposal >= 1000""")
    proposal(page, board, operationId=operation)
    expect(surface(page).locator(".confirm")).to_be_hidden()
    proposal(page, board, operationId="new-explicit-action")
    expect(surface(page).locator(".confirm")).to_be_visible()
    page.evaluate("mockRouter.mode='disconnect'")
    surface(page).locator(".confirm").click()
    expect(surface(page).locator(".status")).to_contain_text("uncertain")
    assert surface(page).evaluate("element => element.inFlight === false")
    assert page.evaluate("mockRouter.requests.length") == 1

    # During a held operation, extra proposals are ignored. Navigation revokes
    # the generation; a late authenticated terminal reply must not enter new frame.
    page.reload(wait_until="networkidle")
    board = frame_for(page)
    page.evaluate("mockRouter.mode = 'hold'")
    board.locator("#notify").click()
    surface(page).locator(".confirm").click()
    proposal(page, board, operationId="extra-inflight")
    expect(surface(page).locator(".confirm")).to_be_hidden()
    assert page.evaluate("mockRouter.requests.length") == 1
    generation = surface(page).evaluate("element => element.generation")
    # Bypass this context's bootstrap mock for the security probe: the actual
    # server, not route.fulfill(), must decide whether to disclose credentials.
    page.route("**/api/agent-binding", lambda route: route.continue_())
    board.evaluate("location.href = '/api/agent-binding'")
    expect(surface(page).locator(".status")).to_contain_text("capability is revoked")
    assert "credentials" not in board.locator("body").inner_text()
    proposal(page, board, generation=generation, operationId="navigated")
    page.evaluate("""() => {
      const request = mockRouter.requests[0];
      mockRouter.socket.emit({type:'response',id:'mock-route-1',requestId:request.requestId,
        final:true,from:{kind:'agent',id:'workspace-agent',sessionId:'mock-session'},
        payload:{kind:'workspace.webboard-result',version:1,
          operationId:request.payload.operationId,text:'LATE SECRET'}});
    }""")
    expect(surface(page).locator(".status")).to_contain_text("capability is revoked")
    assert "LATE SECRET" not in board.locator("body").inner_text()
    assert page.evaluate("mockRouter.requests.length") == 1

    # HTTP metadata defense remains even if browser CSP is unavailable/relaxed.
    for path in ("/api/state", "/api/agent-binding", "/api/agent-lifecycle"):
        for headers in ({"Origin": "null", "Sec-Fetch-Site": "same-origin"},
                        {"Sec-Fetch-Dest": "iframe", "Sec-Fetch-Site": "same-origin"},
                        {"Sec-Fetch-Dest": "script", "Sec-Fetch-Site": "same-origin"}):
            response = page.request.get(url + path, headers=headers)
            assert response.status == 403, (path, headers, response.status)
    for path in ("/api/state", "/api/agent-lifecycle/start",
                 "/api/conversations/conversation-aster/messages"):
        method = "PUT" if path.endswith("state") else "POST"
        response = page.request.fetch(url + path, method=method, data={},
                                      headers={"Origin": "null"})
        assert response.status == 403
    for path in ("/boards/project-northstar/main/private.json",
                 "/boards/project-northstar/main/%2e%2e%2fprivate.json",
                 "/boards/project-other/main/index.html", "/modules/demo-card.js"):
        assert page.request.get(url + path).status == 404, path

    page.reload(wait_until="networkidle")
    page.set_viewport_size({"width": 375, "height": 812})
    board = frame_for(page)
    expect(board.locator("#notify")).to_be_visible()
    assert board.evaluate("document.documentElement.scrollWidth <= innerWidth")
    board.locator("#add").focus()
    page.keyboard.press("Enter")
    expect(board.locator("output")).to_have_text("Count: 1")
    board.locator("#notify").click()
    box = surface(page).locator(".confirm").bounding_box()
    assert box and box["x"] >= 0 and box["x"] + box["width"] <= 375
    assert page.request.get(f"{url}/api/state").json() == before
    # Maximum accepted text remains scrollable rather than pushing controls off
    # a mobile viewport. A large response cannot introduce executable elements.
    mobile = context.new_page()
    mobile.set_viewport_size({"width": 375, "height": 667})
    mobile.goto(f"{url}/project-northstar/", wait_until="networkidle")
    proposal(mobile, frame_for(mobile), operationId="max-text", text="x" * 2000)
    expect(surface(mobile).locator(".confirm")).to_be_visible()
    assert surface(mobile).locator("section").evaluate(
        "element => element.scrollHeight > element.clientHeight")
    bounds = surface(mobile).bounding_box()
    review = surface(mobile).locator("section").bounding_box()
    assert review["height"] <= bounds["height"] * 0.55 + 1
    surface(mobile).locator(".dismiss").click()
    mobile.close()
    result = {"transport": "mock", "browser": "real isolated Chrome", "payload": payload,
              "sandbox": denial, "cleanWebSocket": websocket,
              "checks": ["host-confirmed notification", "text-only correlated reply",
                         "no state/history changes", "source/schema/replay rejection",
                         "navigation revocation and stale reply", "API/asset guards",
                         "375px keyboard UI and bounded long-text review",
                         "confirmation payload/source", "pending-navigation revocation",
                         "rate/replay/in-flight limits", "timeout/error releases in-flight"],
              "limit": "Sandbox does not prevent all iframe self-navigation/network egress"}
    if evidence:
        page.screenshot(path=str(evidence / "webboard-mobile.png"))
        page.set_viewport_size({"width": 1280, "height": 900})
        page.screenshot(path=str(evidence / "webboard-desktop.png"))
        (evidence / "webboard-result.json").write_text(json.dumps(result, indent=2))
    print("PASS: real-browser webboard isolation/events/mobile; MOCK router only")
    page.close()
