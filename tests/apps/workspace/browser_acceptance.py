"""Isolated real-Chrome acceptance with a MOCK router, not a real-agent claim.

Run from checkout root with cached dependencies:
    uv run --offline --with fastapi --with uvicorn --with shelfdb==3.0.2 \
      --with dictify==5.0.2 --with playwright \
      python tests/apps/workspace/browser_acceptance.py
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import nullcontext
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / ".agents/var/apps/workspace"
PROJECT_ROOT = "/project-northstar/"


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_for_server(url: str, process: subprocess.Popen[bytes]) -> None:
    end = time.monotonic() + 8
    while time.monotonic() < end:
        if process.poll() is not None:
            raise RuntimeError(f"Isolated Uvicorn exited with status {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=0.3):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(f"Isolated Uvicorn did not become ready: {url}")


def app(page, selector: str):
    return page.locator("wsp-root").locator(selector)


def control(page, selector: str):
    return app(page, "wsp-controls").locator(selector)


def conversation(page, selector: str):
    return app(page, "wsp-conversation").locator(selector)


def assert_layout_bounds(page) -> None:
    """Check the entire shell, not just individual controls, at the viewport edge."""
    width = page.viewport_size["width"]
    height = page.viewport_size["height"]
    surface = app(page, "main").bounding_box()
    controls = app(page, "wsp-controls").bounding_box()
    notice = control(page, ".notice").bounding_box()
    panel = app(page, "#conversation-panel").bounding_box()
    assert surface and controls and notice and panel
    for name, box in (("surface", surface), ("controls", controls), ("panel", panel)):
        assert box["x"] >= 0 and box["x"] + box["width"] <= width + 0.5, (name, box)
        assert box["y"] >= 0 and box["y"] + box["height"] <= height + 0.5, (name, box)
    assert surface["y"] + surface["height"] <= controls["y"] + 0.5
    if notice["height"]:
        assert controls["y"] <= notice["y"] < notice["y"] + notice["height"] <= (
            controls["y"] + controls["height"] + 0.5
        ), (notice, controls)
    assert panel["height"] < surface["height"] * 0.8, (panel, surface)


def test_browser(url: str, runtime: Path) -> None:
    chrome = shutil.which("google-chrome") or "/usr/bin/google-chrome"
    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, executable_path=chrome, args=["--no-sandbox"],
            env={key: value for key, value in os.environ.items()
                 if not key.startswith(("WORKSPACE_", "PI_", "AUTOMATA_MESSAGE_ROUTER",
                                        "AUTOMATA_AGENT_ROUTER"))}
        )
        context = browser.new_context()
        from automata.apps.workspace.store import WorkspaceStore
        isolated_store = WorkspaceStore(runtime / "data")
        context.expose_function("mockAgentPost", lambda value: isolated_store.post(
            value, provenance={"kind": "agent", "id": "workspace-agent",
                               "sessionId": "mock-session"}))
        context.add_init_script(path=ROOT / "tests/apps/workspace/mock_router.js")
        context.route("**/api/agent-binding", lambda route: route.fulfill(json={"binding": {
            "conversationId": "conversation-aster", "to": "workspace-agent",
            "agentId": "agent-automata", "displayName": "Automata",
            "credentials": {"wsUrl": "ws://127.0.0.1:8791/ws",
                            "participant": "mock-page", "token": "mock-only"},
        }}))
        workspace = context.new_page()
        workspace.on("pageerror", lambda error: errors.append(str(error)))
        workspace.goto(f"{url}{PROJECT_ROOT}", wait_until="networkidle")
        expect(workspace.locator("wsp-root")).to_be_visible()
        expect(app(workspace, "wsp-surface")).to_be_visible()
        panel = app(workspace, "#conversation-panel")
        expect(panel).to_be_hidden()
        toggle = control(workspace, "#conversation-toggle")
        expect(toggle).to_have_attribute("aria-expanded", "false")
        expect(toggle).to_have_attribute("aria-label", "Open conversation")
        assert workspace.locator("wsp-root").evaluate(
            "element => Boolean(element.shadowRoot)"
        )
        for tag_name in (
            "wsp-surface",
            "wsp-conversation",
            "wsp-controls",
            "wsp-composer",
        ):
            assert app(workspace, tag_name).evaluate("element => element.shadowRoot === null")
        assert control(workspace, "#page").count() == 0
        assert workspace.locator("header, nav, h1, aside, #artifact").count() == 0
        for old_path in (
            "/",
            "/projects/project-northstar/workspace",
            "/projects/project-northstar/chat",
        ):
            assert workspace.request.get(f"{url}{old_path}").status == 404, old_path

        original = workspace.request.get(f"{url}/api/state").json()["artifact"]
        workspace.add_style_tag(
            content=(
                ":root { --aui-surface: rgb(240, 241, 242); "
                "--aui-border: rgb(4, 5, 6); --aui-focus: rgb(1, 2, 3); }"
            )
        )
        surface = app(workspace, "wsp-surface").evaluate(
            "element => getComputedStyle(element).backgroundColor"
        )
        border = control(workspace, "#agent").evaluate(
            "element => getComputedStyle(element).borderTopColor"
        )
        assert surface == "rgb(240, 241, 242)" and border == "rgb(4, 5, 6)", (surface, border)

        expect(control(workspace, "#agent")).to_have_text("Automata")
        expect(control(workspace, "#connection-status")).to_contain_text("Available")
        assert control(workspace, "#connect, #disconnect").count() == 0
        assert workspace.evaluate("mockRouter.requests.length") == 0
        compose = control(workspace, "wsp-composer textarea")
        expect(compose).to_have_attribute("placeholder", "Message Automata…")
        send = control(workspace, "wsp-composer #send")
        expect(send).to_be_hidden()
        single_height = compose.bounding_box()["height"]
        compose.fill("   ")
        expect(send).to_be_hidden()
        compose.fill("Line one\nLine two\nLine three")
        expect(send).to_be_visible()
        multi_height = compose.bounding_box()["height"]
        assert single_height < multi_height < workspace.viewport_size["height"] * 0.3
        compose.fill("\n".join(f"Line {index}" for index in range(20)))
        assert 120 < compose.bounding_box()["height"] <= workspace.viewport_size["height"] * 0.3 + 1
        assert compose.evaluate("element => element.scrollHeight > element.clientHeight")
        send_box = send.bounding_box()
        compose_box = compose.bounding_box()
        agent_box = control(workspace, "#agent").bounding_box()
        assert send_box["y"] + send_box["height"] <= compose_box["y"]
        assert abs(
            agent_box["y"] + agent_box["height"] - compose_box["y"] - compose_box["height"]
        ) < 1
        compose.fill("Draft for Automata")
        assert compose.bounding_box()["height"] == single_height
        notice = control(workspace, ".notice")
        expect(notice).to_contain_text("All changes saved", timeout=5000)
        assert notice.bounding_box()["x"] >= compose.bounding_box()["x"]
        assert notice.bounding_box()["y"] < compose.bounding_box()["y"]
        expect(notice).to_be_empty(timeout=5000)
        expect(send).to_be_visible()
        toggle.focus()
        workspace.keyboard.press("Enter")
        expect(panel).to_be_visible()
        expect(toggle).to_have_attribute("aria-expanded", "true")
        expect(conversation(workspace, ".heading")).to_be_focused()
        assert_layout_bounds(workspace)
        workspace.keyboard.press("Escape")
        expect(panel).to_be_hidden()
        expect(toggle).to_have_attribute("aria-expanded", "false")
        expect(toggle).to_be_focused()
        workspace.reload(wait_until="networkidle")
        expect(control(workspace, "#agent")).to_have_text("Automata")
        expect(control(workspace, "wsp-composer textarea")).to_have_value("Draft for Automata")
        expect(control(workspace, "wsp-composer #send")).to_be_visible()
        expect(app(workspace, "#conversation-panel")).to_be_hidden()
        assert workspace.request.get(f"{url}/api/state").json()["artifact"] == original

        workspace.add_style_tag(
            content=(
                ":root { --aui-action: rgb(0, 170, 0); "
                "--aui-muted-text: rgb(12, 34, 56); --aui-danger: rgb(220, 0, 0); }"
            )
        )
        action = control(workspace, "wsp-composer #send").evaluate(
            "element => getComputedStyle(element).backgroundColor"
        )
        toggle.click()
        muted = conversation(workspace, ".empty").evaluate(
            "element => getComputedStyle(element).color"
        )
        assert (action, muted) == ("rgb(0, 170, 0)", "rgb(12, 34, 56)"), (action, muted)
        workspace.keyboard.press("Escape")
        compose = control(workspace, "wsp-composer textarea")
        compose.focus()
        focus = compose.evaluate("element => getComputedStyle(element).borderTopColor")
        assert focus == "rgb(85, 118, 162)", focus
        expect(control(workspace, "#connection-status")).to_contain_text("Available")
        assert workspace.evaluate("mockRouter.requests.length") == 0
        compose.fill("Sent while conversation is closed")
        compose.press("End")
        compose.press("Enter")  # Native Enter inserts a newline; it does not send.
        expect(compose).to_have_value("Sent while conversation is closed\n")
        expect(control(workspace, ".notice")).to_contain_text("All changes saved", timeout=5000)
        assert workspace.request.get(f"{url}/api/state").json()["conversations"][
            "conversation-aster"]["draft"] == "Sent while conversation is closed\n"
        # Reproduce the reviewed failure after autosave and multiple catch-up cycles.
        workspace.wait_for_timeout(15000)
        expect(compose).to_have_value("Sent while conversation is closed\n")
        expect(app(workspace, "#conversation-panel")).to_be_hidden()
        control(workspace, "wsp-composer #send").click()
        expect(control(workspace, "wsp-composer textarea")).to_have_value("")
        expect(control(workspace, "wsp-composer #send")).to_be_hidden()
        expect(control(workspace, ".notice")).to_contain_text(
            "agent admitted input", timeout=5000
        )
        assert workspace.request.get(f"{url}/api/state").json()["conversations"][
            "conversation-aster"]["draft"] == ""
        workspace.reload(wait_until="networkidle")
        expect(control(workspace, "wsp-composer textarea")).to_have_value("")
        assert workspace.evaluate("mockRouter.requests.length") == 0
        expect(app(workspace, "#conversation-panel")).to_be_hidden()
        expect(control(workspace, "#conversation-toggle")).to_have_attribute(
            "aria-expanded", "false"
        )
        toggle.click()
        expect(conversation(workspace, ".message.user")).to_contain_text(
            "Sent while conversation is closed"
        )
        expect(conversation(workspace, ".message.agent")).to_contain_text("Mock agent reply")
        workspace.keyboard.press("Escape")

        # Draft hydration is passive; submit is explicitly correlated and one-shot.
        toggle.click()
        title = conversation(workspace, 'aui-form input[name="title"]')
        outcome = conversation(workspace, 'aui-form input[name="outcome"]')
        title.fill("Small harmless task")
        outcome.fill("Verify structured exchange")
        compose.fill("Composer draft survives incoming posts")
        # Backend append races the unsaved debounce. CAS rebases only draft edits;
        # catch-up never replaces the form node, focus or local composer values.
        for index in (1, 2):
            isolated_store.post({"operationId": f"independent-progress-{index}",
                "context": {"projectId": "project-northstar",
                            "conversationId": "conversation-aster"},
                "content": [{"id": "text", "type": "text", "version": 1,
                             "data": {"text": f"Independent progress {index}"}}]},
                provenance={"kind": "agent", "id": "workspace-agent", "sessionId": "mock-session"})
        expect(conversation(workspace, ".message.agent")).to_have_count(3)
        expect(conversation(workspace, ".message.agent").nth(1)).to_contain_text(
            "Independent progress 1")
        expect(conversation(workspace, ".message.agent").nth(2)).to_contain_text(
            "Independent progress 2")
        expect(title).to_have_value("Small harmless task")
        expect(outcome).to_have_value("Verify structured exchange")
        expect(compose).to_have_value("Composer draft survives incoming posts")
        expect(compose).to_be_focused()
        expect(control(workspace, ".notice")).to_contain_text("All changes saved")
        workspace.reload(wait_until="networkidle")
        assert workspace.evaluate("mockRouter.requests.length") == 0
        control(workspace, "#conversation-toggle").click()
        expect(conversation(workspace, 'aui-form input[name="title"]')).to_have_value(
            "Small harmless task"
        )
        expect(conversation(workspace, ".message.agent")).to_have_count(3)
        expect(control(workspace, "wsp-composer textarea")).to_have_value(
            "Composer draft survives incoming posts")
        expect(control(workspace, "#connection-status")).to_contain_text("Available")
        conversation(workspace, "aui-form button").click()
        expect(conversation(workspace, ".message.agent").last).to_contain_text(
            "Mock acknowledgement"
        )
        expect(conversation(workspace, "aui-form button")).to_be_disabled()
        requests = workspace.evaluate("mockRouter.requests")
        assert len(requests) == 1 and requests[0]["payload"]["postTo"] == "workspace-app"
        response = requests[0]["payload"]["content"][0]
        assert response["type"] == "form-response"
        assert response["data"]["values"] == {
            "title": "Small harmless task", "outcome": "Verify structured exchange"
        }
        assert response["data"]["componentId"] == "task-form"
        assert response["data"]["messageId"]
        assert response["data"]["definition"]["title"] == "A small task"
        workspace.keyboard.press("Escape")

        stale = context.new_page()
        stale.goto(f"{url}{PROJECT_ROOT}", wait_until="networkidle")
        compose.fill("Winning draft")
        expect(control(workspace, ".notice")).to_contain_text("All changes saved", timeout=5000)
        stale_compose = control(stale, "wsp-composer textarea")
        stale_compose.fill("Stale local draft remains")
        expect(control(stale, ".notice")).to_contain_text("Conflict", timeout=5000)
        expect(stale_compose).to_have_value("Stale local draft remains")
        expect(control(stale, "#copy-recovery")).to_be_visible()
        conflict_prompts: list[str] = []
        stale.on("dialog", lambda dialog: (conflict_prompts.append(dialog.type), dialog.dismiss()))
        try:
            stale.reload(timeout=1200)
        except PlaywrightTimeoutError:
            pass
        assert "beforeunload" in conflict_prompts, conflict_prompts

        pending = context.new_page()
        pending.goto(f"{url}{PROJECT_ROOT}", wait_until="networkidle")
        pending_compose = control(pending, "wsp-composer textarea")
        pending_compose.fill("Pending debounce draft")
        prompts: list[str] = []
        pending.on("dialog", lambda dialog: (prompts.append(dialog.type), dialog.dismiss()))
        try:
            pending.reload(timeout=1200)
        except PlaywrightTimeoutError:
            pass
        assert "beforeunload" in prompts, prompts

        delivery = context.new_page()
        delivery.goto(f"{url}{PROJECT_ROOT}", wait_until="networkidle")
        delivered_compose = control(delivery, "wsp-composer textarea")
        delivered_compose.fill("Commit then lose response")
        expect(control(delivery, ".notice")).to_contain_text("All changes saved", timeout=5000)
        expect(control(delivery, "#connection-status")).to_contain_text("Available")
        delivery.evaluate("mockRouter.mode = 'disconnect'")
        control(delivery, "wsp-composer #send").click()
        expect(control(delivery, ".notice")).to_contain_text("delivery uncertain", timeout=5000)
        expect(delivered_compose).to_be_enabled()
        expect(control(delivery, "wsp-composer #send")).to_be_hidden()
        assert delivery.evaluate("mockRouter.requests.length") == 1
        expect(control(delivery, "#connection-status")).to_contain_text("Available", timeout=6000)
        assert delivery.evaluate("mockRouter.requests.length") == 1  # reconnect never replays
        expect(app(delivery, "#conversation-panel")).to_be_hidden()
        delivery_toggle = control(delivery, "#conversation-toggle")
        delivery_toggle.click()
        expect(conversation(delivery, ".message.user").nth(2)).to_contain_text(
            "Commit then lose response"
        )
        expect(conversation(delivery, ".message.user").nth(2)).to_contain_text("uncertain")
        assert delivery.evaluate("mockRouter.requests.length") == 1
        expect(conversation(delivery, ".message.user")).to_have_count(3)
        delivery.reload(wait_until="networkidle")
        assert delivery.evaluate("mockRouter.requests.length") == 0
        expect(app(delivery, "#conversation-panel")).to_be_hidden()
        delivery_toggle = control(delivery, "#conversation-toggle")
        delivery_toggle.click()
        expect(conversation(delivery, ".message.user")).to_have_count(3)
        for envelope in (
            {
                "projectId": "project-northstar",
                "conversationId": "conversation-mira",
                "agentId": "agent-b",
                "payload": {"text": "missing operation id"},
            },
            {
                "projectId": "project-northstar",
                "conversationId": "conversation-mira",
                "agentId": "agent-b",
                "clientOperationId": None,
                "payload": {"text": "null operation id"},
            },
            {
                "projectId": "project-northstar",
                "conversationId": "conversation-mira",
                "agentId": "agent-b",
                "clientOperationId": "operation-12345678",
                "payload": {"text": None},
            },
        ):
            response = delivery.request.post(
                f"{url}/api/conversations/conversation-mira/messages", data=envelope
            )
            assert response.status == 422, (response.status, response.text())

        failed = context.new_page()
        failed.set_viewport_size({"width": 375, "height": 812})
        failed.goto(f"{url}{PROJECT_ROOT}", wait_until="networkidle")
        failed.add_style_tag(content=":root { --aui-danger: rgb(220, 0, 0); }")
        failed.route(
            "**/api/state",
            lambda route: route.abort() if route.request.method == "PUT" else route.continue_(),
        )
        control(failed, "wsp-composer textarea").fill("Keep local text on failure")
        notice = control(failed, ".notice")
        expect(notice).to_contain_text("Save failed", timeout=5000)
        assert notice.evaluate("element => getComputedStyle(element).color") == "rgb(220, 0, 0)"
        for selector in ("#conversation-toggle", "#agent", "wsp-composer"):
            box = control(failed, selector).bounding_box()
            assert box and box["x"] >= 0 and box["x"] + box["width"] <= 375, (selector, box)
        toggle_mobile = control(failed, "#conversation-toggle")
        toggle_mobile.click()
        mobile_panel = app(failed, "#conversation-panel")
        control(failed, "wsp-composer textarea").fill("\n".join(["Mobile line"] * 20))
        mobile_compose_box = control(failed, "wsp-composer textarea").bounding_box()
        assert mobile_compose_box["height"] <= 812 * 0.3 + 1
        mobile_send = control(failed, "wsp-composer #send")
        expect(mobile_send).to_be_visible()
        mobile_send_box = mobile_send.bounding_box()
        assert mobile_send_box["y"] + mobile_send_box["height"] <= mobile_compose_box["y"]
        assert_layout_bounds(failed)
        panel_box = mobile_panel.bounding_box()
        workspace_box = app(failed, "main").bounding_box()
        assert panel_box and workspace_box
        assert (
            panel_box["x"] >= workspace_box["x"]
            and panel_box["y"] >= workspace_box["y"]
            and panel_box["x"] + panel_box["width"] <= workspace_box["x"] + workspace_box["width"]
            and panel_box["y"] + panel_box["height"] <= workspace_box["y"] + workspace_box["height"]
        ), (panel_box, workspace_box)

        contract = context.new_page()
        contract.goto(f"{url}{PROJECT_ROOT}", wait_until="networkidle")
        contract.route("**/connection-acceptance.js", lambda route: route.fulfill(
            path=ROOT / "tests/apps/workspace/connection_acceptance.js",
            content_type="text/javascript"))
        result = contract.evaluate(
            "async () => (await import('/connection-acceptance.js')).verifyConnection()")
        assert result["mock"] is True
        print("MOCK connection boundary checks:", result)
        for headers in ({"Origin": "http://wrong-origin.invalid"},
                        {"Sec-Fetch-Site": "cross-site"}, {}):
            response = contract.request.get(f"{url}/api/agent-binding", headers=headers)
            assert response.status == 403
            assert "credentials" not in response.text()
        response = contract.request.get(
            f"{url}/api/agent-binding", headers={"Sec-Fetch-Site": "same-origin"})
        assert response.status == 200
        assert response.json()["binding"]["agentId"] == "agent-automata"
        assert response.headers["cache-control"] == "no-store"
        assert "access-control-allow-origin" not in response.headers
        evidence_root = os.environ.get("WORKSPACE_TEST_ROOT")
        if evidence_root:
            failed.screenshot(path=str(Path(evidence_root) / "mock-mobile.png"))
            contract.screenshot(path=str(Path(evidence_root) / "mock-desktop.png"))
            (Path(evidence_root) / "mock-result.json").write_text(json.dumps(result, indent=2))
        if os.environ.get("WORKSPACE_BOARD_SEED"):
            from webboard_acceptance import verify_board
            verify_board(context, url, Path(evidence_root) if evidence_root else None)
        from post_recovery_acceptance import verify_uncertain_save
        verify_uncertain_save(context, url, control, PROJECT_ROOT)
        assert not errors, errors
        print(
            "PASS: slug-only route and parent-shadow Base styles/tokens; "
            "accessible overlay/focus/Escape, draft persistence, "
            "closed-overlay MOCK-router send and persisted correlated form submission, "
            "CAS/unload/uncertain-send safeguards, "
            "422 validation, and 375px layout bounds; no JS errors"
        )
        browser.close()


def main() -> None:
    if (
        not (RUNTIME / "web-assets/index.html").is_file()
        or not (RUNTIME / "lib/adaptive-ui.js").is_file()
    ):
        raise FileNotFoundError("Build workspace web assets and Adaptive UI before acceptance")
    port = free_port()
    retained = os.environ.get("WORKSPACE_TEST_ROOT")
    if retained:
        Path(retained).mkdir(parents=True, exist_ok=True)
    area = (nullcontext(retained) if retained
            else tempfile.TemporaryDirectory(prefix="workspace-poc-browser-"))
    with area as temporary:
        runtime = Path(temporary) / "runtime"
        subprocess.run(
            ["deno", "task", "--config",
             str(ROOT / "src/automata/apps/workspace/frontend/deno.json"), "build"],
            cwd=ROOT, env={**os.environ, "WORKSPACE_RUNTIME_ROOT": str(runtime)}, check=True,
        )
        shutil.copytree(RUNTIME / "lib", runtime / "lib")
        if seed := os.environ.get("WORKSPACE_BOARD_SEED"):
            shutil.copytree(Path(seed), runtime / "northstar/main/web")
        endpoint = runtime / "synthetic-page.json"
        endpoint.write_text(json.dumps({"kind": "page", "wsUrl": "ws://127.0.0.1:8791/ws",
                                        "participant": "mock-page", "token": "mock-only"}))
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("WORKSPACE_", "AUTOMATA_MESSAGE_ROUTER",
                                              "AUTOMATA_AGENT_ROUTER", "PI_"))}
        environment.update(
            {
                "PYTHONPATH": str(ROOT / "src"),
                "WORKSPACE_RUNTIME_ROOT": str(runtime),
                "WORKSPACE_PORT": str(port),
                "WORKSPACE_AGENT_CONFIG": "",
                "WORKSPACE_PAGE_ENDPOINT": str(endpoint),
                "WORKSPACE_AGENT_ID": "agent-automata",
                "WORKSPACE_AGENT_PARTICIPANT": "workspace-agent",
            }
        )
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "automata.apps.workspace.server:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "error",
            ],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            wait_for_server(f"http://127.0.0.1:{port}/api/state", process)
            test_browser(f"http://127.0.0.1:{port}", runtime)
        finally:
            process.terminate()
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=4)


if __name__ == "__main__":
    main()
