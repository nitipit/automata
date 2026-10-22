"""Offline agent-team RPC/controller checks. Requires installed Pi, never calls models."""
import json
import os
import re
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest


def _pi_package():
    if override := os.environ.get("PI_TEST_PACKAGE_ROOT"):
        return Path(override)
    if not (launcher := shutil.which("pi")):
        return None
    entry = Path(launcher).resolve()
    try:
        match = re.search(r"^# cmd-shim-target=(.+)$", entry.read_text(), re.MULTILINE)
        if match:
            entry = Path(match.group(1)).resolve()
    except (OSError, UnicodeDecodeError):
        pass
    for parent in entry.parents:
        manifest = parent / "package.json"
        if manifest.is_file():
            if json.loads(manifest.read_text()).get("name") == "@earendil-works/pi-coding-agent":
                return parent
    return None


def test_agent_team_extension(tmp_path):
    node, package = shutil.which("node"), _pi_package()
    if node is None or package is None:
        pytest.skip("Node.js 24 and installed Pi required")
    source = files("automata").joinpath("runtimes/pi/extensions/agent-team")
    for name in ("index.ts", "worker.ts", "capture.ts"):
        (tmp_path / name).write_text(source.joinpath(name).read_text())
    modules = tmp_path / "node_modules"
    modules.mkdir()
    (modules / "typebox").symlink_to(package.resolve().parents[1] / "typebox")
    result = subprocess.run(
        [node, "--experimental-transform-types", "--test", "--test-timeout=10000",
         str(Path(__file__).with_suffix(".mjs")),
         str(Path(__file__).with_name("agent_team_native_test.mjs"))],
        env={**os.environ, "AGENT_TEAM_TEST_ROOT": str(tmp_path),
             "AUTOMATA_AGENT_TEAM_WORKER": "",
             "PI_TEST_PACKAGE_ROOT": str(package.resolve())},
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout)
