#!/usr/bin/env python3
"""Harmless RPC process fixture; no model, router, network, or task execution."""
import json
import os
import signal
import sys
import time
from pathlib import Path

args = sys.argv[1:]
path = Path(args[args.index("--session") + 1])
header = json.loads(path.read_text().splitlines()[0])
mode = os.environ.get("WORKSPACE_FAKE_MODE", "ok")
if mode == "stubborn":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
if mode == "secret-stderr":
    print("fake-secret", file=sys.stderr, flush=True)


def emit(value):
    print(json.dumps(value), flush=True)


for line in sys.stdin:
    request = json.loads(line)
    result = {"id": request["id"], "type": "response", "command": request["type"], "success": True}
    if request["type"] == "get_state":
        result["data"] = {"sessionId": header["id"], "sessionFile": str(path),
                          "model": {"provider": "openai-codex", "id": "gpt-6-astra"},
                          "thinkingLevel": "high" if mode == "mismatch" else "medium"}
    emit(result)
    if request["type"] == "prompt":
        if mode == "crash":
            sys.exit(7)
        if mode == "timeout":
            time.sleep(3)
            continue
        if mode != "no-open":
            emit({"type": "tool_execution_end", "toolName": "message_router", "result": {
                "details": {"status": "open", "participant": "workspace-agent",
                            "sessionId": header["id"]}}})
        emit({"type": "agent_settled"})

if mode == "stubborn":
    while True:
        time.sleep(1)
