"""Opt-in published-v0.3.0 relay/client + actual Pi loader/routing trial; no model.

Run in a task-local environment containing the published nodalwire==0.3.0 wheel
and PyZMQ. --extension names a prepared bundle index.ts with its locked published
Node client/Edictor installed; --pi-package names installed Pi 1.4.0. This uses Pi's
real extension loader/runtime and AgentSession.sendCustomMessage, with inert
run/queue collaborators, not a full CLI/provider/LLM run. It never contacts port
5555 or reads user credentials. Only owned ephemeral relay sockets/child are closed.

The owned relay's receipt fault seam drops three selected SEND receipts AFTER
real forwarding, proving timeout/cancellation uncertainty without blind retries.
No installed relay code or shared configuration is modified.
"""
import argparse
import asyncio
import json
import os
import secrets
import socket
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from nodalwire import Node, Relay, RelayConfig
from nodalwire.config import NetworkConfig
from nodalwire.credentials import make_verifier
from nodalwire.protocol import DATA, OK


def timestamp():
    return datetime.now(UTC).isoformat()


class ReceiptFaultRelay(Relay):
    """Narrow owned-test seam: otherwise execute the installed published relay."""

    dropped_receipts = 0
    _drop_next_receipt = False

    async def _emit(self, address, *frames):
        if frames[0] == DATA:
            payload = frames[-1]
            uncertain = payload in (b"uncertain-timeout", b"uncertain-cancel")
            try:
                uncertain |= json.loads(payload).get("message", {}).get("content") == (
                    "uncertain-extension"
                )
            except (ValueError, AttributeError, TypeError, UnicodeError):
                pass
            if uncertain:
                self._drop_next_receipt = True
        elif frames[0] == OK and len(frames) == 3 and self._drop_next_receipt:
            self._drop_next_receipt = False
            self.dropped_receipts += 1
            return None
        return await super()._emit(address, *frames)


def listener_absent(endpoint):
    port = int(endpoint.rsplit(":", 1)[1])
    with socket.socket() as probe:
        probe.settimeout(0.2)
        return probe.connect_ex(("127.0.0.1", port)) != 0


async def stop_owned_child(process, suite):
    """Signal only this invocation's still-identical child; tolerate natural exit races."""
    for action in ("terminate", "kill"):
        if process.returncode is not None:
            return
        try:
            command = Path(f"/proc/{process.pid}/cmdline").read_bytes().split(b"\0")
        except FileNotFoundError:
            await process.wait()
            return
        assert str(suite.resolve()).encode() in command, "Child identity changed"
        try:
            getattr(process, action)()
        except ProcessLookupError:
            await process.wait()
            return
        try:
            await asyncio.wait_for(process.wait(), 5)
            return
        except TimeoutError:
            continue
    raise TimeoutError("Owned child did not exit after verified termination")


async def trial(extension: Path, pi_package: Path, artifacts: Path):
    assert version("nodalwire") == "0.3.0", "Install the published matching wheel"
    assert json.loads((pi_package / "package.json").read_text())["version"] == "1.4.0"
    extension = extension.resolve()
    suite = Path(__file__).parent / "nodalwire" / "live.test.mjs"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "home").mkdir(exist_ok=True)
    os.environ["NODALWIRE_ADMIN_TOKEN"] = secrets.token_urlsafe(32)
    credential = secrets.token_urlsafe(32)
    protected = NetworkConfig(join_verifier=make_verifier(credential))
    primary = ReceiptFaultRelay(RelayConfig(
        endpoint="tcp://127.0.0.1:*", admin_endpoint="tcp://127.0.0.1:*",
        allowed_names=["sdk-node", "sdk-peer", "blocked-peer", "python-peer", "pi-live"],
        deny=[["sdk-node", "blocked-peer"]],
        networks={"team": NetworkConfig(), "protected": protected},
    ))
    secondary = Relay(RelayConfig(
        endpoint="tcp://127.0.0.1:*", admin_endpoint="tcp://127.0.0.1:*",
        networks={"default": protected},
    ))
    process = None
    endpoints = []
    started = timestamp()
    result = {
        "started": started, "result": "failed",
        "scope": "published transport + Pi loader/native routing; inert collaborators, no model",
    }
    try:
        async with primary, secondary:
            endpoints = [
                primary.endpoint, primary.admin_endpoint,
                secondary.endpoint, secondary.admin_endpoint,
            ]
            assert all(not endpoint.endswith((":5555", ":5556")) for endpoint in endpoints)
            tasks = [asyncio.create_task(relay.run()) for relay in (primary, secondary)]
            echo = None
            try:
                async with await Node.connect("python-peer", primary.endpoint) as peer:
                    async def serve():
                        while True:
                            message = await peer.receive()
                            await peer.send(
                                message.sender, message.payload, network=message.network,
                            )

                    echo = asyncio.create_task(serve())
                    # Deliberately do not inherit provider/admin tokens or user Pi config.
                    env = {
                        "PATH": os.environ["PATH"], "HOME": str(artifacts / "home"),
                        "PI_CODING_AGENT_DIR": str(artifacts / "home" / ".pi"),
                        "PI_EXTENSION_TEST_ROOT": str(extension.parent),
                        "PI_TEST_PACKAGE_ROOT": str(pi_package.resolve()),
                        "NODALWIRE_TRIAL_ENDPOINT": primary.endpoint,
                        "NODALWIRE_TRIAL_PROTECTED_ENDPOINT": secondary.endpoint,
                        "NODALWIRE_TRIAL_JOIN_TOKEN": credential,
                    }
                    process = await asyncio.create_subprocess_exec(
                        "node", "--experimental-transform-types", "--test", "--test-isolation=none",
                        "--test-reporter=tap",
                        "--test-timeout=30000", str(suite.resolve()),
                        cwd=artifacts, env=env, stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    result["child_pid"] = process.pid
                    stdout, stderr = await asyncio.wait_for(process.communicate(), 40)
                    (artifacts / "live-tests.tap").write_bytes(stdout)
                    (artifacts / "live-stderr.log").write_bytes(stderr)
                    result["child_exit"] = process.returncode
                    assert process.returncode == 0, "Live suite failed; inspect retained TAP/stderr"
                    assert primary.dropped_receipts == 3, primary.dropped_receipts
            finally:
                try:
                    if process and process.returncode is None:
                        await stop_owned_child(process, suite)
                finally:
                    if echo:
                        echo.cancel()
                        await asyncio.gather(echo, return_exceptions=True)
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
        # Mark success only after peer release and both relay contexts have closed.
        result.update(result="passed", dropped_send_receipts=primary.dropped_receipts)
    finally:
        result.update(
            finished=timestamp(), python=sys.version.split()[0],
            nodalwire=version("nodalwire"), pyzmq=version("pyzmq"),
            endpoints=endpoints, listeners_absent=all(listener_absent(e) for e in endpoints),
            child_exited=process is None or process.returncode is not None,
        )
        if not result["listeners_absent"] or not result["child_exited"]:
            result["result"] = "failed"
        (artifacts / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    assert result["listeners_absent"] and result["child_exited"], "Owned cleanup incomplete"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extension", required=True, type=Path)
    parser.add_argument("--pi-package", required=True, type=Path)
    parser.add_argument("--artifacts", required=True, type=Path)
    args = parser.parse_args()
    asyncio.run(trial(args.extension, args.pi_package, args.artifacts.resolve()))
