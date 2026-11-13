"""Opt-in published-v0.3.0 relay/client + actual Pi loader/routing trial; no model.

Use the prepared Python environment containing nodalwire==0.3.0 and PyZMQ.
--extension names a task-local bundle index.ts made from current repository source
with prepared published Node client/Edictor dependencies. --pi-package names the
installed Pi package; explicitly select --expected-pi-version (currently 1.5.2).
This uses the real extension loader/runtime and AgentSession.sendCustomMessage
with inert run/queue collaborators, not a full CLI/provider/LLM run.

Only owned ephemeral relay sockets/child are closed. No user credentials, shared
relay or provider configuration is used. An owned relay seam suppresses selected
SEND receipts AFTER forwarding; all other relay behavior is the published code.
Generated join credentials exist only for this invocation and are never artifacts.
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

# Must correspond exactly to cases in live.test.mjs. Match by native request ID,
# not "the next OK", so unrelated concurrent operations cannot lose a receipt.
FAULT_MARKERS = frozenset({
    "uncertain-timeout", "uncertain-cancel", "uncertain-extension", "uncertain-reply",
    "Please reply: missing request receipt",
})


def timestamp():
    return datetime.now(UTC).isoformat()


class ReceiptFaultRelay(Relay):
    """Narrow owned-test seam: otherwise execute the installed published relay."""

    def __init__(self, config):
        super().__init__(config)
        self.dropped_markers = []
        self._receipts_to_drop = {}

    async def _emit(self, address, *frames):
        if frames[0] == DATA:
            payload = frames[-1]
            try:
                marker = payload.decode("utf-8")
                try:
                    marker = json.loads(marker).get("message", {}).get("content")
                except (ValueError, AttributeError, TypeError):
                    pass
            except UnicodeError:
                marker = None
            result = await super()._emit(address, *frames)
            if result is None and isinstance(marker, str) and marker in FAULT_MARKERS:
                self._receipts_to_drop[frames[2]] = marker
            return result
        if frames[0] == OK and len(frames) == 3:
            marker = self._receipts_to_drop.pop(frames[2], None)
            if marker is not None:
                self.dropped_markers.append(marker)
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


async def trial(extension: Path, pi_package: Path, artifacts: Path, expected_pi_version: str):
    extension = extension.resolve()
    pi_package = pi_package.resolve()
    suite = Path(__file__).parent / "nodalwire" / "live.test.mjs"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "home").mkdir(exist_ok=True)
    process = None
    endpoints = []
    primary = None
    result = {
        "started": timestamp(), "result": "failed", "expected_pi": expected_pi_version,
        "scope": "published transport + Pi loader/native routing; inert collaborators, no model",
    }
    try:
        assert version("nodalwire") == "0.3.0", "Prepared published matching wheel required"
        actual_pi = json.loads((pi_package / "package.json").read_text())["version"]
        result["pi"] = actual_pi
        assert actual_pi == expected_pi_version, (
            "Installed Pi differs from explicitly selected version"
        )
        assert extension.is_file(), "Prepared repository-source bundle required"
        credential = secrets.token_urlsafe(32)
        # Explicit fixture verifiers avoid consulting or mutating administrator env.
        admin_verifier = make_verifier(secrets.token_urlsafe(32))
        protected = NetworkConfig(join_verifier=make_verifier(credential))
        primary = ReceiptFaultRelay(RelayConfig(
            endpoint="tcp://127.0.0.1:*", admin_endpoint="tcp://127.0.0.1:*",
            admin_verifier=admin_verifier,
            allowed_names=["sdk-node", "sdk-peer", "blocked-peer", "python-peer", "pi-live"],
            deny=[["sdk-node", "blocked-peer"]],
            networks={"team": NetworkConfig(), "other": NetworkConfig(), "protected": protected},
        ))
        secondary = Relay(RelayConfig(
            endpoint="tcp://127.0.0.1:*", admin_endpoint="tcp://127.0.0.1:*",
            admin_verifier=admin_verifier, networks={"default": protected},
        ))
        async with primary, secondary:
            endpoints = [
                primary.endpoint, primary.admin_endpoint,
                secondary.endpoint, secondary.admin_endpoint,
            ]
            assert all(not endpoint.endswith((":5555", ":5556")) for endpoint in endpoints)
            tasks = [asyncio.create_task(relay.run()) for relay in (primary, secondary)]
            echo = None
            try:
                # Contains only exact route bindings and allowlisted env names,
                # never credential values. Relative path exercises ctx.cwd handling.
                aliases = {
                    "protected-primary": {
                        "endpoint": primary.endpoint, "network": "protected",
                        "env": "NODALWIRE_TRIAL_JOIN_TOKEN",
                    },
                    "protected-default": {
                        "endpoint": secondary.endpoint, "network": "default",
                        "env": "NODALWIRE_TRIAL_JOIN_TOKEN",
                    },
                    "wrong-primary": {
                        "endpoint": primary.endpoint, "network": "protected",
                        "env": "NODALWIRE_TRIAL_WRONG_TOKEN",
                    },
                    "wrong-default": {
                        "endpoint": secondary.endpoint, "network": "default",
                        "env": "NODALWIRE_TRIAL_WRONG_TOKEN",
                    },
                }
                alias_path = artifacts / "join-aliases.json"
                # O_EXCL prevents following or replacing any pre-existing symlink.
                fd = os.open(alias_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as output:
                    json.dump({"aliases": aliases}, output)
                async with await Node.connect("python-peer", primary.endpoint) as peer:
                    async def serve():
                        while True:
                            message = await peer.receive()
                            await peer.reply(message, message.payload)

                    echo = asyncio.create_task(serve())
                    # Deliberately do not inherit provider/admin tokens or user Pi config.
                    env = {
                        "PATH": os.environ["PATH"], "HOME": str(artifacts / "home"),
                        "PI_CODING_AGENT_DIR": str(artifacts / "home" / ".pi"),
                        "PI_EXTENSION_TEST_ROOT": str(extension.parent),
                        "PI_TEST_PACKAGE_ROOT": str(pi_package),
                        "PI_TEST_EXPECTED_VERSION": expected_pi_version,
                        "NODALWIRE_TRIAL_ENDPOINT": primary.endpoint,
                        "NODALWIRE_TRIAL_PROTECTED_ENDPOINT": secondary.endpoint,
                        "NODALWIRE_TRIAL_JOIN_TOKEN": credential,
                        "NODALWIRE_TRIAL_WRONG_TOKEN": secrets.token_urlsafe(32),
                        "NODALWIRE_TRIAL_CREDENTIALS_CONFIG": alias_path.name,
                    }
                    process = await asyncio.create_subprocess_exec(
                        "node", "--experimental-transform-types", "--test", "--test-isolation=none",
                        "--test-reporter=tap", "--test-timeout=90000", str(suite.resolve()),
                        cwd=artifacts, env=env, stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    result["child_pid"] = process.pid
                    stdout, stderr = await asyncio.wait_for(process.communicate(), 100)
                    # Do not persist accidental raw credentials even when a test fails.
                    assert all(token.encode() not in stdout + stderr for token in (
                        credential, env["NODALWIRE_TRIAL_WRONG_TOKEN"],
                    )), "Generated credential leaked in child output; output withheld"
                    (artifacts / "live-tests.tap").write_bytes(stdout)
                    (artifacts / "live-stderr.log").write_bytes(stderr)
                    result["child_exit"] = process.returncode
                    assert process.returncode == 0, "Live suite failed; inspect retained TAP/stderr"
                    assert sorted(primary.dropped_markers) == sorted(FAULT_MARKERS), (
                        "Receipt fault cases incomplete"
                    )
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
        result.update(result="passed")
    finally:
        result.update(
            finished=timestamp(), python=sys.version.split()[0],
            nodalwire=version("nodalwire"), pyzmq=version("pyzmq"),
            dropped_send_receipts=len(primary.dropped_markers) if primary else 0,
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
    parser.add_argument(
        "--expected-pi-version", required=True, help="Explicit tested Pi version, currently 1.5.2",
    )
    parser.add_argument(
        "--artifacts", required=True, type=Path, help="Fresh owned artifact directory",
    )
    args = parser.parse_args()
    asyncio.run(trial(
        args.extension, args.pi_package, args.artifacts.resolve(), args.expected_pi_version,
    ))
