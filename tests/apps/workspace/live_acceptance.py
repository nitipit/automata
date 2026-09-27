"""Bounded real-agent acceptance stages; never wait/poll for the parent reply.

The coordinator must explicitly authorize the binding and each harmless roundtrip.
Explicit ownership confirmation is required. Defaults refer to the worker-owned
isolated Chrome on CDP 34418 and app on 8790; override only with authorized targets.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

from browser_acceptance import app, control, conversation
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / ".agents/var/workspace/workspace-poc/reconnect"
URL = "http://127.0.0.1:8790/project-northstar/"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["start", "submit", "verify"])
    parser.add_argument("--confirm-owned-binding", action="store_true")
    parser.add_argument("--cdp", default="http://127.0.0.1:34418")
    parser.add_argument("--url", default=URL)
    parser.add_argument("--evidence-root", type=Path, default=EVIDENCE)
    args = parser.parse_args()
    if not args.confirm_owned_binding:
        parser.error(
            "Explicit --confirm-owned-binding is required; never target unrelated resources"
        )
    if any(urlparse(url).hostname != "127.0.0.1" for url in (args.cdp, args.url)):
        parser.error("Only explicitly owned loopback targets are supported")
    args.evidence_root.mkdir(parents=True, exist_ok=True)
    state_url = urljoin(args.url, "/api/state")
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(args.cdp)
        context = browser.contexts[0]
        page = next((page for page in context.pages if page.url == args.url), context.pages[0])
        routes = []
        cdp = context.new_cdp_session(page)
        cdp.send("Network.enable")

        def outbound(event):
            try:
                frame = json.loads(event["response"]["payloadData"])
                if frame.get("type") == "route":
                    routes.append(frame["payload"])
            except (ValueError, KeyError):
                pass

        cdp.on("Network.webSocketFrameSent", outbound)
        if args.stage == "start":
            page.add_init_script("""
                window.__workspaceErrors=[];
                window.addEventListener('error', e => __workspaceErrors.push(e.message));
                window.addEventListener('unhandledrejection',
                    e => __workspaceErrors.push(String(e.reason)));
            """)
            page.goto(args.url, wait_until="networkidle")
            expect(control(page, "#connection-status")).to_contain_text("Available")
            assert routes == [], "Initial auto-connect must not transfer history"
            assert control(page, "#connect, #disconnect").count() == 0
            expect(control(page, "#connection-status")).to_contain_text("runtime unknown")
            expect(control(page, "#agent")).to_have_text("Automata")
            expect(app(page, "#conversation-panel")).to_be_hidden()
            control(page, "textarea").fill(
                "Harmless Workspace conversation test. Please return the approved text "
                "and task-details form; do not execute any task."
            )
            control(page, "#send").click()
            expect(control(page, ".notice")).to_contain_text("awaiting", ignore_case=True)
            expect(app(page, "#conversation-panel")).to_be_hidden()
            assert len(routes) == 1 and routes[0]["kind"] == "workspace.message"
        elif args.stage == "submit":
            control(page, "#conversation-toggle").click()
            expect(conversation(page, ".message.agent")).to_have_count(1)
            expect(conversation(page, "wsp-text").last).to_contain_text("task")
            expect(conversation(page, "aui-form")).to_have_count(1)
            conversation(page, 'input[name="title"]').fill("Harmless acceptance check")
            conversation(page, 'input[name="outcome"]').fill(
                "Confirm structured values were received; execute nothing"
            )
            expect(control(page, ".notice")).to_contain_text("All changes saved")
            page.screenshot(path=str(args.evidence_root / "live-form-draft.png"))
            page.reload(wait_until="networkidle")
            expect(control(page, "#connection-status")).to_contain_text("Available")
            assert routes == [], "History hydration and auto-connect must never route"
            control(page, "#conversation-toggle").click()
            expect(conversation(page, 'input[name="title"]')).to_have_value(
                "Harmless acceptance check"
            )
            conversation(page, "aui-form button").click()
            expect(conversation(page, "aui-form button")).to_be_disabled()
            expect(control(page, ".notice")).to_contain_text("awaiting", ignore_case=True)
            assert len(routes) == 1 and routes[0]["kind"] == "workspace.form-submit"
            assert routes[0]["componentId"] == "task-form"
        else:
            expect(conversation(page, ".message.agent")).to_have_count(2)
            expect(conversation(page, ".form-status")).to_contain_text("completed")
            expect(conversation(page, "aui-form button")).to_be_disabled()
            page.screenshot(path=str(args.evidence_root / "live-acknowledgement.png"))
            before = page.request.get(state_url).json()
            page.reload(wait_until="networkidle")
            expect(control(page, "#connection-status")).to_contain_text("Available")
            assert control(page, "#connect, #disconnect").count() == 0
            expect(control(page, "#connection-status")).to_contain_text("runtime unknown")
            assert routes == [], "Completed history and reconnect must not replay"
            control(page, "#conversation-toggle").click()
            expect(conversation(page, ".message.agent")).to_have_count(2)
            expect(conversation(page, "aui-form button")).to_be_disabled()
            assert page.request.get(state_url).json() == before
            page.set_viewport_size({"width": 375, "height": 812})
            page.screenshot(path=str(args.evidence_root / "live-mobile.png"))
            assert page.locator("wsp-root").evaluate("e => e.scrollWidth <= innerWidth")
        errors = page.evaluate("window.__workspaceErrors ?? []")
        assert not errors, errors
        state = page.request.get(state_url).json()
        evidence = {"stage": args.stage, "routes": routes, "state": state, "pageErrors": errors}
        (args.evidence_root / f"live-{args.stage}.json").write_text(json.dumps(evidence, indent=2))
        print(f"PASS live {args.stage}: {len(routes)} bounded outbound request(s), "
              "no page errors; browser remains open")
        cdp.detach()
        # Exiting Playwright disconnects only; the tmux-owned Chrome survives.


if __name__ == "__main__":
    main()
