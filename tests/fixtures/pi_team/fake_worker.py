#!/usr/bin/env python3
"""Deterministic, model-free Pi RPC subprocess for independent pi-team tests.

Read fake-worker.json from CWD. Accept ordinary Pi launch flags without invoking Pi.
Write observed commands/timestamps to fake-worker-trace.jsonl for black-box assertions.
Only LF frames stdout; literal U+2028/U+2029 intentionally remain inside JSON strings.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path.cwd()
CONFIG = json.loads((ROOT / "fake-worker.json").read_text())
TRACE = ROOT / "fake-worker-trace.jsonl"


def trace(event, **fields):
    with TRACE.open("a") as stream:
        stream.write(json.dumps({"event": event, "at": time.monotonic(), "pid": os.getpid(),
                                 **fields}) + "\n")


def emit(record):
    sys.stdout.buffer.write(json.dumps(record, ensure_ascii=False).encode() + b"\n")
    sys.stdout.buffer.flush()


def flag(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def reply(command, *, success=True, data=None, error=None):
    record = {"id": command.get("id"), "type": "response", "command": command["type"],
              "success": success}
    if data is not None:
        record["data"] = data
    if error:
        record["error"] = error
    emit(record)


def message(reason="stop", text="PRIVATE_RESULT\u2028line\u2029paragraph"):
    result = {"role": "assistant", "content": [{"type": "text", "text": text}],
              "stopReason": reason, "timestamp": int(time.time() * 1000)}
    if reason == "error":
        result["errorMessage"] = "injected provider failure"
    return result


def finish(reason="stop"):
    final = message(reason)
    emit({"type": "message_end", "message": final})
    emit({"type": "agent_end", "messages": [final], "willRetry": False})
    emit({"type": "agent_settled", "aborted": reason == "aborted"})
    trace("settled", reason=reason)


def main():
    trace("spawn", argv=sys.argv[1:])
    time.sleep(CONFIG.get("startup_delay", 0))
    if CONFIG.get("startup_exit"):
        return 7
    for raw in sys.stdin.buffer:
        command = json.loads(raw)
        kind = command["type"]
        trace("command", command=command)
        if kind == "get_state":
            model = flag("--model", "fake/model")
            provider, _, model_id = model.partition("/")
            state = {
                "model": {"provider": flag("--provider", provider), "id": model_id or model},
                "thinkingLevel": flag("--thinking", "medium"),
                "sessionId": flag("--session-id", f"fake-session-{os.getpid()}"),
                "sessionFile": str(Path(flag("--session-dir", str(ROOT))) / "fake-session.jsonl"),
                "isStreaming": False, "isCompacting": False,
                "messageCount": 0, "pendingMessageCount": 0,
            }
            state.update(CONFIG.get("state", {}))
            reply(command, data=state)
        elif kind == "prompt":
            scenario = CONFIG.get("scenario", "success")
            if scenario == "reject":
                reply(command, success=False, error="injected prompt rejection")
                continue
            if scenario == "handled":
                reply(command, data={"disposition": "handled"})
                continue
            if scenario == "wrong-id":
                reply({**command, "id": "unrelated-request"}, data={"disposition": "started"})
                continue
            reply(command, data={"disposition": "started"})
            emit({"type": "agent_start"})
            if scenario == "exit":
                return 9
            if scenario in {"descendant", "orphan-descendant"}:
                child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
                trace("descendant", child_pid=child.pid)
                if scenario == "orphan-descendant":
                    return 9
                continue
            if scenario == "hang":
                continue
            if scenario == "noise":
                # Both total volume and individual records exceed typical pipe capacity.
                sys.stderr.buffer.write(b"d" * CONFIG.get("noise_size", 262144) + b"\n")
                sys.stderr.buffer.flush()
                emit({"type": "message_update", "assistantMessageEvent": {
                    "type": "text_delta", "contentIndex": 0,
                    "delta": "x" * CONFIG.get("noise_size", 262144)}})
            if scenario == "continuation":
                emit({"type": "agent_end", "messages": [message(text="INTERMEDIATE")],
                      "willRetry": False})
                trace("intermediate_end")
                time.sleep(CONFIG.get("continuation_delay", 0.3))
                emit({"type": "agent_start"})
            if scenario == "no-final":
                emit({"type": "agent_end", "messages": [], "willRetry": False})
                emit({"type": "agent_settled", "aborted": False})
            else:
                time.sleep(CONFIG.get("settle_delay", 0))
                finish(scenario if scenario in {"error", "aborted", "length"} else "stop")
        elif kind == "get_messages":
            reply(command, data={"messages": [message()]})
        elif kind == "get_last_assistant_text":
            reply(command, data={"text": "PRIVATE_RESULT\u2028line\u2029paragraph"})
        elif kind == "clear_queue":
            reply(command, data={"steering": [], "followUp": []})
        elif kind == "abort":
            reply(command)
            finish("aborted")
        else:
            reply(command)
    trace("stdin_closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
