"""Stable timestamps through pure transforms and installed Pi conversion; no model calls."""
import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest

PI_LINK_ROOT = Path.home() / ".local/share/pnpm/store/v11/links/@earendil-works/pi-coding-agent"


def test_message_timestamps(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js with TypeScript stripping required")
    (tmp_path / "message-timestamps.ts").write_text(
        files("automata").joinpath("runtimes/pi/extensions/message-timestamps.ts").read_text()
    )
    candidates = sorted(PI_LINK_ROOT.glob("*/*/node_modules/@earendil-works/pi-coding-agent"))
    override = os.environ.get("PI_TEST_PACKAGE_ROOT")
    package = Path(override) if override else (candidates[-1] if candidates else None)
    env = {**os.environ, "CONTEXT_TEST_ROOT": str(tmp_path)}
    if package is not None:
        env["TIMESTAMP_PI_PACKAGE"] = str(package)
    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_suffix(".mjs"))], env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
