"""Installed metadata/fork/trash/restore proof with meaningful native tool history."""

import hashlib
import http.server
import json
import shutil
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

import sequence_probe as base


class Provider(base.Provider):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        base.Provider.requests.append(body)
        sequence = len(base.Provider.requests)
        if sequence % 2:
            item = {
                "type": "function_call",
                "id": f"fc_{sequence}",
                "call_id": f"call_{sequence}",
                "name": "exec_command",
                "arguments": json.dumps(
                    {"cmd": "printf 'owned tool payload\\n'", "yield_time_ms": 1000}
                ),
            }
        else:
            item = {
                "type": "message",
                "id": f"msg_{sequence}",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": "Meaningful owned assistant payload."}],
            }
        response = {
            "id": f"resp_{sequence}",
            "object": "response",
            "status": "completed",
            "output": [item],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
                "input_tokens_details": {"cached_tokens": 0},
            },
        }
        events = [
            {"type": "response.created", "response": {"id": response["id"]}},
            {"type": "response.output_item.added", "output_index": 0, "item": item},
            {"type": "response.output_item.done", "output_index": 0, "item": item},
            {"type": "response.completed", "response": response},
        ]
        payload = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def control(action, *arguments, success=True):
    command = [
        "python3",
        "/probe/integration/token-awareness/session_management.py",
        action,
        "--store-root",
        "/probe/codex",
        "--state-root",
        "/probe/management",
        *arguments,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    output = json.loads(result.stdout)
    assert (result.returncode == 0) == success, (result.returncode, output, result.stderr)
    return output


def unselected_snapshot(client, identities):
    snapshot = {}
    for identity in identities:
        thread = client.request("thread/read", {"threadId": identity, "includeTurns": True})[
            "thread"
        ]
        with sqlite3.connect("/probe/codex/state_5.sqlite") as db:
            db.row_factory = sqlite3.Row
            row = dict(db.execute("SELECT * FROM threads WHERE id=?", [identity]).fetchone())
        snapshot[identity] = {
            "row": row,
            "turns": thread["turns"],
            "rolloutSha256": hashlib.sha256(Path(thread["path"]).read_bytes()).hexdigest(),
        }
    return snapshot


def child():
    root = Path("/probe")
    (root / "destination").mkdir()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    (root / "codex/config.toml").write_text(
        'model="gpt-5.1-codex"\nmodel_provider="fixture"\n'
        'approval_policy="never"\nsandbox_mode="read-only"\n'
        '[model_providers.fixture]\nname="Fixture"\nwire_api="responses"\n'
        f'base_url="http://127.0.0.1:{server.server_port}/v1"\nrequires_openai_auth=false\n'
        "[analytics]\nenabled=false\n[feedback]\nenabled=false\n"
        "[features]\nmemories=false\nweb_search=false\n"
    )
    client = base.Client()
    evidence = {}
    try:
        sources = []
        for index in range(2):
            thread = client.request("thread/start", {"cwd": "/probe/project"})["thread"]
            client.turn(
                thread["id"], f"Owned user payload {index}; execute the fixture printf once."
            )
            client.request("thread/name/set", {"threadId": thread["id"], "name": f"owned-{index}"})
            sources.append(
                client.request("thread/read", {"threadId": thread["id"], "includeTurns": True})[
                    "thread"
                ]
            )
        evidence["before"] = sources
        evidence["initialRequests"] = len(base.Provider.requests)
        client.close()
        flags = ["--binary", "/codex", "--outside-session", "--inactive-owned"]
        source, target = sources
        listing = control("list", "--cwd", "/probe/project")
        evidence["listing"] = listing
        source_bytes = Path(source["path"]).read_bytes()
        evidence["fork"] = control(
            "fork",
            "--receipt",
            listing["forkReceipt"],
            "--ids",
            source["id"],
            "--target-cwd",
            "/probe/destination",
            *flags,
        )
        assert Path(source["path"]).read_bytes() == source_bytes
        unselected = [source["id"], evidence["fork"]["results"][0]["id"]]
        client = base.Client()
        evidence["unselectedBefore"] = unselected_snapshot(client, unselected)
        client.close()
        listing = control("list", "--cwd", "/probe/project")
        evidence["dependencyReject"] = control(
            "trash",
            "--receipt",
            listing["trashReceipt"],
            "--ids",
            source["id"],
            "--xdg-data-home",
            "/probe/xdg",
            *flags,
            success=False,
        )
        assert Path(source["path"]).read_bytes() == source_bytes
        listing = control("list", "--cwd", "/probe/project")
        trashed = control(
            "trash",
            "--receipt",
            listing["trashReceipt"],
            "--ids",
            target["id"],
            "--xdg-data-home",
            "/probe/xdg",
            *flags,
        )
        evidence["trash"] = trashed
        assert not Path(target["path"]).exists()
        evidence["afterTrash"] = control("list", "--cwd", "/probe/project")
        evidence["restore"] = control(
            "restore", "--recovery-id", trashed["recoveryId"], "--ids", target["id"], *flags
        )
        evidence["afterRestore"] = control("list", "--cwd", "/probe/project")
        listing = control("list", "--cwd", "/probe/project")
        copy_source_bytes = Path(target["path"]).read_bytes()
        evidence["copy"] = control(
            "copy",
            "--receipt",
            listing["copyReceipt"],
            "--ids",
            target["id"],
            "--target-cwd",
            "/probe/destination",
            *flags,
        )
        assert Path(target["path"]).read_bytes() == copy_source_bytes
        client = base.Client()
        forked = client.request(
            "thread/read", {"threadId": evidence["copy"]["results"][0]["id"], "includeTurns": True}
        )["thread"]
        evidence["copied"] = forked
        sys.path.insert(0, "/probe/integration/token-awareness")
        from session_native import NativeClient
        from session_recovery import signature

        validation = root / "copy-validation"
        (validation / "sessions").mkdir(parents=True)
        copied = validation / "sessions" / Path(forked["path"]).name
        shutil.copyfile(forked["path"], copied)
        evidence["materializedMeta"] = {
            k: v
            for k, v in json.loads(copied.open().readline())["payload"].items()
            if k not in ["base_instructions"]
        }
        with NativeClient(
            "/codex", validation, root / "copy-scratch", ["/probe/destination"], provider="fixture"
        ) as isolated:
            evidence["independentResume"] = isolated.request(
                "thread/resume",
                {
                    "threadId": forked["id"],
                    "path": str(copied),
                    "excludeTurns": True,
                    "modelProvider": "fixture",
                    "cwd": "/probe/destination",
                    "runtimeWorkspaceRoots": ["/probe/destination"],
                },
            )["thread"]
            evidence["independentDigest"] = signature(isolated, forked["id"])
        evidence["restored"] = client.request(
            "thread/read", {"threadId": target["id"], "includeTurns": True}
        )["thread"]
        evidence["unselectedAfter"] = unselected_snapshot(client, unselected)
        assert evidence["unselectedBefore"] == evidence["unselectedAfter"]
        evidence["finalRequests"] = len(base.Provider.requests)
        (root / "requests.json").write_text(json.dumps(base.Provider.requests, indent=2))
    finally:
        (root / "management-evidence.json").write_text(json.dumps(evidence, indent=2))
        client.close()
        server.shutdown()


if __name__ == "__main__":
    base.main(child, Path(__file__), [Path(base.__file__)])
