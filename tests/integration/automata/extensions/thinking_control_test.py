"""Native Pi/local-stub thinking effort and next-request boundary tests."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_thinking_control_native(tmp_path: Path) -> None:
    package = os.environ.get("AGENT_BROWSER_BRIDGE_NATIVE_PI_PACKAGE")
    node = shutil.which("node")
    if not package or not node:
        pytest.skip("Set AGENT_BROWSER_BRIDGE_NATIVE_PI_PACKAGE to an installed Pi package")
    extensions = Path(__file__).parents[4] / "src/automata/runtimes/pi/extensions"
    shutil.copytree(extensions / "thinking-control", tmp_path / "thinking-control")
    modules = tmp_path / "node_modules"
    (modules / "@earendil-works").mkdir(parents=True)
    pkg = Path(package)
    for name in ("pi-coding-agent", "pi-ai"):
        (modules / "@earendil-works" / name).symlink_to(pkg.parent / name)
    (modules / "typebox").symlink_to(pkg.parent.parent / "typebox")
    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_suffix(".mjs"))],
        env={**os.environ, "THINKING_TEST_ROOT": str(tmp_path), "PI_OFFLINE": "1"},
        capture_output=True, text=True, timeout=50, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
