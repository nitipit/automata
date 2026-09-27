"""Exercise the TypeScript tools with isolated Pi and trash adapters."""

import json
import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest


def test_pi_sessions_runtime_boundaries(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js 22.18+ is required for TypeScript runtime tests")

    extension = tmp_path / "pi-sessions.ts"
    extension.write_text(
        files("automata").joinpath("runtimes", "pi", "extensions", "pi-sessions.ts").read_text()
    )
    adapters = {
        "@earendil-works/pi-coding-agent": "export const SessionManager = {};",
        "typebox": "export const Type = new Proxy({}, {get: () => (...args) => args});",
    }
    for name, source in adapters.items():
        package = tmp_path / "node_modules" / name
        package.mkdir(parents=True)
        (package / "package.json").write_text(
            json.dumps({"type": "module", "exports": "./index.js"})
        )
        (package / "index.js").write_text(source)

    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_name("pi_sessions_test.mjs"))],
        env={**os.environ, "SESSION_TEST_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_pi_session_copy_native_sdk(tmp_path: Path) -> None:
    sdk = os.environ.get("PI_SESSIONS_NATIVE_SDK")
    node = shutil.which("node")
    if not sdk or not node:
        pytest.skip("Set PI_SESSIONS_NATIVE_SDK to installed Pi dist/index.js for native coverage")
    sdk_path = Path(sdk).resolve()
    assert sdk_path.is_file()
    (tmp_path / "pi-sessions.ts").write_text(
        files("automata").joinpath("runtimes", "pi", "extensions", "pi-sessions.ts").read_text()
    )
    adapters = {
        "@earendil-works/pi-coding-agent":
            f"export {{ SessionManager }} from {json.dumps(sdk_path.as_uri())};",
        "typebox": "export const Type = new Proxy({}, {get: () => (...args) => args});",
    }
    for name, source in adapters.items():
        package = tmp_path / "node_modules" / name
        package.mkdir(parents=True)
        (package / "package.json").write_text(
            json.dumps({"type": "module", "exports": "./index.js"})
        )
        (package / "index.js").write_text(source)
    result = subprocess.run(
        [node, str(Path(__file__).with_name("pi_sessions_native_test.mjs"))],
        env={
            **os.environ,
            "SESSION_TEST_ROOT": str(tmp_path),
            "PI_SESSIONS_NATIVE_SDK": str(sdk_path),
            "PI_CODING_AGENT_DIR": str(tmp_path / "isolated-agent"),
        },
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
