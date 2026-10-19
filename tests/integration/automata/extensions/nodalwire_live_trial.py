"""Opt-in native relay → isolated Pi RPC → Python trial (uses a real model).

Run with a Python environment containing nodalwire and pyzmq. Supply a prepared
copy of the extension with its published @devcapsule/nodalwire-client installed.
No global configuration is changed. Only processes created here are stopped.
"""
import argparse
import asyncio
import contextlib
import json
import uuid
from pathlib import Path

from nodalwire import Node, Relay, RelayConfig


async def trial(extension: Path, artifacts: Path):
    artifacts.mkdir(parents=True, exist_ok=True)
    nonce = uuid.uuid4().hex[:12]
    pi_name, python_name = f"pi-trial-{nonce}", f"python-trial-{nonce}"
    expected = [f"pong-{nonce}-1", f"pong-{nonce}-2"]
    relay = Relay(RelayConfig(endpoint="tcp://127.0.0.1:*"))
    endpoint = await relay.start()
    relay_task = asyncio.create_task(relay.run())
    peer = process = reader_task = None
    ready = asyncio.get_running_loop().create_future()
    settled = asyncio.Event()
    settled_count = 0
    with (artifacts / "rpc.jsonl").open("wb") as transcript, (
        artifacts / "stderr.log"
    ).open("wb") as stderr:
        try:
            peer = await Node.connect(python_name, endpoint)
            process = await asyncio.create_subprocess_exec(
                "pi", "--mode", "rpc", "--no-session", "--no-extensions", "--no-mcp",
                "--no-skills", "--no-prompt-templates", "--no-themes", "--no-context-files",
                "--no-builtin-tools", "--offline", "--extension", str(extension.resolve()),
                "--nodalwire-name", pi_name, "--nodalwire-endpoint", endpoint,
                "--system-prompt", "This is an isolated messaging interoperability test. "
                "For each external message, you are authorized to reply once to its sender using "
                "nodalwire_send, with exactly the reply text it requests. Do not do other work.",
                cwd=artifacts,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=stderr,
            )

            async def read_records():
                nonlocal settled_count
                async for line in process.stdout:
                    transcript.write(line)
                    transcript.flush()
                    record = json.loads(line)
                    if record.get("id") == "ready" and not ready.done():
                        ready.set_result(record)
                    if record.get("type") == "agent_settled":
                        settled_count += 1
                        if settled_count >= len(expected):
                            settled.set()
                if not ready.done():
                    ready.set_exception(RuntimeError("Pi exited before RPC readiness"))

            reader_task = asyncio.create_task(read_records())
            process.stdin.write(b'{"id":"ready","type":"get_state"}\n')
            await process.stdin.drain()
            state = await asyncio.wait_for(ready, 30)
            assert state.get("success"), state
            for text in expected:
                request = {
                    "version": 1, "type": "message",
                    "text": f"Reply to {python_name} using nodalwire_send. "
                    f"Set text exactly: {text}",
                }
                await peer.send(pi_name, json.dumps(request).encode())
            replies = []
            for text in expected:
                response = await asyncio.wait_for(peer.receive(), 120)
                assert response.sender == pi_name, response.sender
                body = json.loads(response.payload)
                assert body == {"version": 1, "type": "message", "text": text}, body
                replies.append(body)
            await asyncio.wait_for(settled.wait(), 60)
            result = {
                "result": "passed", "endpoint": endpoint, "pi_node": pi_name,
                "python_node": python_name, "replies": replies,
                "model": state["data"].get("model"),
                "scope": "isolated real Pi/model + native NodalWire round trip; "
                "no global installation",
            }
        finally:
            if process:
                process.stdin.close()
                try:
                    await asyncio.wait_for(process.wait(), 15)
                except TimeoutError:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), 5)
                    except TimeoutError:
                        process.kill()
                        await process.wait()
            if reader_task:
                reader_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await reader_task
            if peer:
                with contextlib.suppress(Exception):
                    await peer.close(timeout=1)
            relay_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await relay_task
            await relay.close()
    assert process.returncode == 0, f"Pi did not shut down cleanly: {process.returncode}"
    result["pi_exit_code"] = process.returncode
    (artifacts / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extension", required=True, type=Path)
    parser.add_argument("--artifacts", required=True, type=Path)
    arguments = parser.parse_args()
    asyncio.run(trial(arguments.extension, arguments.artifacts.resolve()))
