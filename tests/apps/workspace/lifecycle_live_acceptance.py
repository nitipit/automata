"""Opt-in ONE-session real lifecycle proof. Requires explicit parent envelope.

Runs only isolated router8792/app8790; starts then resumes the exact owned session.
At most two startup prompts and two harmless page messages. Never rerun against an
existing evidence root: failed evidence is retained for operator review, not replay.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from browser_acceptance import ROOT, app, control, wait_for_server
from playwright.sync_api import expect, sync_playwright


def wait(predicate, seconds=120):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.1)
    raise TimeoutError("Bounded lifecycle acceptance deadline exceeded")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-one-owned-test-session", action="store_true", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    area = args.evidence_root.resolve()
    if area.exists():
        raise ValueError("Evidence root must be fresh; never replay a prior test")
    for port in (8790, 8792):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
    area.mkdir(parents=True, mode=0o700)
    runtime = area / "runtime"
    router_config = area / "router.json"
    endpoints = area / "endpoints"
    router_command = ["uv", "run", "--offline", "--no-project", "--script",
                      str(ROOT / ".agents/tools/message-router/message_router.py")]
    subprocess.run([*router_command, "setup", "--config-file", str(router_config),
                    "--page", "workspace-page", "--agent", "workspace-agent",
                    "--allow", "workspace-page:workspace-agent"], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["deno", "task", "--config", str(
        ROOT / "src/automata/apps/workspace/frontend/deno.json"), "build"], check=True,
        env={**os.environ, "WORKSPACE_RUNTIME_ROOT": str(runtime)})
    shutil.copytree(ROOT / ".agents/var/apps/workspace/lib", runtime / "lib")
    router_log = (area / "router.log").open("wb")
    router = subprocess.Popen([*router_command, "serve", "--config-file", str(router_config),
                               "--endpoint-dir", str(endpoints), "--port", "8792",
                               "--origin", "http://127.0.0.1:8790"],
                              stdout=router_log, stderr=subprocess.STDOUT)
    server = None
    server_logs = []
    try:
        endpoint = endpoints / "participants/workspace-agent.json"
        wait(lambda: endpoint.is_file(), seconds=10)
        config = area / "agent-config.json"
        config.write_text(json.dumps({
            "agentId": "agent-automata", "participant": "workspace-agent", "cwd": str(ROOT),
            "endpoint": str(endpoint), "executable": shutil.which("pi"),
            "extension": str(ROOT / "src/automata/runtimes/pi/extensions/message-router"),
            "provider": "openai-codex", "model": "gpt-6-astra", "thinking": "medium",
            "startupPolicy": "Restricted acceptance only. On startup open the supplied endpoint "
                             "and stop. For each later Workspace text request return a short "
                             "text acknowledging the lifecycle check. No forms, task execution, "
                             "delegation, filesystem reads, commands, or other effects. "
                             "Only message_router is available. Never close the binding yourself.",
        }))
        config.chmod(0o600)
        environment = {**os.environ, "PYTHONPATH": str(ROOT / "src"),
                       "WORKSPACE_RUNTIME_ROOT": str(runtime), "WORKSPACE_PORT": "8790",
                       "WORKSPACE_PAGE_ENDPOINT": str(
                           endpoints / "participants/workspace-page.json"),
                       "WORKSPACE_AGENT_ID": "agent-automata",
                       "WORKSPACE_AGENT_PARTICIPANT": "workspace-agent",
                       "WORKSPACE_AGENT_CONFIG": str(config)}

        def start_server(index):
            log = (area / f"app-{index}.log").open("wb")
            server_logs.append(log)
            process = subprocess.Popen([sys.executable, "-m", "uvicorn",
                "automata.apps.workspace.server:app", "--host", "127.0.0.1", "--port", "8790",
                "--log-level", "warning"], env=environment, stdout=log, stderr=subprocess.STDOUT)
            wait_for_server("http://127.0.0.1:8790/api/state", process)
            return process

        record_path = runtime / "agents/agent-automata/lifecycle.json"
        proof_path = runtime / "agents/agent-automata/verified-state.json"
        proofs = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True,
                executable_path=shutil.which("google-chrome"), args=["--no-sandbox"])
            context = browser.new_context()
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            for index, action in enumerate(("start", "resume")):
                server = start_server(index)
                page.goto("http://127.0.0.1:8790/project-northstar/", wait_until="networkidle")
                button = control(page, "#start-agent")
                expect(button).to_have_text("Start agent" if action == "start" else "Resume agent")
                expect(control(page, "#connection-status")).to_contain_text("Offline")
                if index == 0:
                    assert not record_path.exists(), "Opening page must not start Pi"
                else:
                    saved_id = json.loads(record_path.read_text())["sessionId"]
                    assert saved_id == proofs[0]["sessionId"]
                button.click()  # The sole explicit launch/resume action for this pass.
                wait(lambda: record_path.exists())
                record = json.loads(record_path.read_text())
                (area / f"reserved-{index}.json").write_text(json.dumps(record, indent=2))
                wait(lambda: json.loads(record_path.read_text())["phase"] in {"running", "failed"})
                record = json.loads(record_path.read_text())
                if record["phase"] != "running":
                    raise RuntimeError("Real startup failed; no automatic retry: "
                                       + record.get("detail", ""))
                proof = json.loads(proof_path.read_text())
                proofs.append(proof)
                (area / f"verified-{index}.json").write_text(json.dumps(proof, indent=2))
                expect(control(page, "#connection-status")).to_contain_text(
                    "Available", timeout=15000)
                assert control(page, "#connect, #disconnect").count() == 0
                expect(button).to_be_hidden()
                # Reload must neither start another Pi nor send history/work.
                page.reload(wait_until="networkidle")
                expect(control(page, "#connection-status")).to_contain_text("Available")
                assert json.loads(record_path.read_text())["pid"] == record["pid"]
                text = f"Harmless lifecycle {action} acceptance. Acknowledge only; execute no task."
                control(page, "wsp-composer textarea").fill(text)
                control(page, "wsp-composer #send").click()  # Exactly one new operation per pass.
                control(page, "#conversation-toggle").click()
                expect(app(page, "wsp-conversation .message.agent")).to_have_count(
                    index + 1, timeout=120000)
                expect(control(page, ".notice")).to_contain_text(
                    "real agent reply received", timeout=10000)
                state = page.request.get("http://127.0.0.1:8790/api/state").json()
                messages = state["conversations"]["conversation-aster"]["messages"]
                assert messages[-1]["author"]["sessionId"] == proof["sessionId"]
                (area / f"state-{index}.json").write_text(json.dumps(state, indent=2))
                page.screenshot(path=str(area / f"live-{action}.png"))
                server.terminate()  # Owned app closes RPC stdin and waits; no process-name killing.
                server.wait(timeout=15)
                server = None
                wait(lambda: json.loads(record_path.read_text())["phase"] == "offline", seconds=5)
                (area / f"stopped-{index}.json").write_text(record_path.read_text())
            assert proofs[0]["sessionId"] == proofs[1]["sessionId"]
            assert proofs[0]["sessionFile"] == proofs[1]["sessionFile"]
            assert proofs[0]["pid"] != proofs[1]["pid"]
            assert not errors, errors
            browser.close()
        (area / "result.json").write_text(json.dumps({
            "real": True, "startupPrompts": 2, "harmlessPageRequests": 2,
            "exactSameSession": True, "proofs": proofs, "errors": errors,
        }, indent=2))
        print("PASS real start + exact owned resume; two startup prompts/two harmless replies")
    finally:
        if server and server.poll() is None:
            server.terminate()
            server.wait(timeout=15)
        router.terminate()
        router.wait(timeout=10)
        for stream in server_logs:
            stream.close()
        router_log.close()


if __name__ == "__main__":
    main()
