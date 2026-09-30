"""Opt-in native selected-skill evidence fixture; isolated as sequence_probe."""

import http.server
import json
import subprocess
import threading
from pathlib import Path

import sequence_probe as base


def activity_control(thread, action="list"):
    identity = (
        ["--thread", thread["id"]]
        if action == "saved"
        else ["--transcript", thread["path"], "--session", thread["sessionId"]]
    )
    output = subprocess.check_output(
        [
            "python3",
            "/probe/integration/token-awareness/skill_activity.py",
            action,
            "--state-root",
            "/probe/token-state",
            *identity,
        ],
        text=True,
    )
    return json.loads(output)


def child():
    root = Path("/probe")
    skill = root / "project/.agents/skills/fixture-skill/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: fixture-skill\ndescription: Fixture only.\n---\nFixture instructions.\n"
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), base.Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    config = (
        'model = "gpt-5.1-codex"\nmodel_provider = "fixture"\n'
        'approval_policy = "on-request"\nsandbox_mode = "read-only"\n'
        '[model_providers.fixture]\nname = "Fixture"\nwire_api = "responses"\n'
        f'base_url = "http://127.0.0.1:{server.server_port}/v1"\n'
        "[analytics]\nenabled = false\n[feedback]\nenabled = false\n"
        "[features]\nmemories = false\nweb_search = false\n"
    )
    (root / "codex/config.toml").write_text(config)
    (root / "codex/hooks.json").write_text(
        (root / "integration/token-awareness/hooks.json").read_text()
    )
    client = base.Client()
    listing = client.request("hooks/list", {"cwds": ["/probe/project"]})
    client.close()
    for group in listing["data"]:
        for hook in group.get("hooks", []):
            config += f"\n[hooks.state.{json.dumps(hook['key'])}]\n"
            config += f"trusted_hash = {json.dumps(hook['currentHash'])}\n"
    (root / "codex/config.toml").write_text(config)
    client = base.Client()
    try:
        thread = client.request(
            "thread/start",
            {
                "cwd": "/probe/project",
                "model": "gpt-5.1-codex",
                "experimentalRawEvents": True,
            },
        )["thread"]
        client.turn(thread["id"], "Discovery-only fixture. Say ready.")
        thread = client.request("thread/read", {"threadId": thread["id"]})["thread"]
        checks = {"discovery": activity_control(thread)}
        client.turn(thread["id"], "Use $fixture-skill for this fixture.")
        client.turn(thread["id"], "Observe previous selected skill; say done.")
        checks["inserted"] = activity_control(thread)
        checks["repeatInspect"] = activity_control(thread)
        events = list(client.events)
        client.close()
        client = base.Client()
        thread = client.request("thread/resume", {"threadId": thread["id"]})["thread"]
        client.turn(thread["id"], "After restart, do not select any skill.")
        checks["resumed"] = activity_control(thread)
        # Native selection cannot inject a now-missing skill file. No manual
        # activity reporting or inferred shell event is involved.
        skill.unlink()
        client.turn(thread["id"], "Use $fixture-skill; if unavailable just say unavailable.")
        checks["missing"] = activity_control(thread)
        skill.write_text(
            "---\nname: fixture-skill\ndescription: Fixture only.\n---\nFixture instructions.\n"
        )
        events += client.events
        client.close()
        client = base.Client()
        thread = client.request("thread/resume", {"threadId": thread["id"]})["thread"]
        client.turn(thread["id"], "Use $fixture-skill once more for this fixture.")
        checks["secondInsertion"] = activity_control(thread)
        checks["disabled"] = activity_control(thread, "disable")
        client.turn(thread["id"], "Use $fixture-skill while activity is disabled.")
        checks["enabled"] = activity_control(thread, "enable")
        checks["final"] = activity_control(thread)
        checks["saved"] = activity_control(thread, "saved")
        (root / "activity-controls.json").write_text(json.dumps(checks, indent=2))
        (root / "thread.json").write_text(json.dumps(thread, indent=2))
        (root / "protocol.json").write_text(json.dumps(events + client.events, indent=2))
        (root / "requests.json").write_text(json.dumps(base.Provider.requests, indent=2))
    finally:
        client.close()
        server.shutdown()


if __name__ == "__main__":
    base.main(child, Path(__file__), [Path(base.__file__)])
