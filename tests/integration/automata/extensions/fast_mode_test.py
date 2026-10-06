"""Fast-mode native hooks/session/stream checks; no user state or live requests."""
import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest

PI_LINK_ROOT = Path.home() / ".local/share/pnpm/store/v11/links/@earendil-works/pi-coding-agent"


def test_fast_mode(tmp_path):
    node = shutil.which("node")
    candidates = sorted(PI_LINK_ROOT.glob("*/*/node_modules/@earendil-works/pi-coding-agent"))
    override = os.environ.get("PI_TEST_PACKAGE_ROOT")
    package = Path(override) if override else (candidates[-1] if candidates else None)
    if node is None or package is None:
        pytest.skip("Node.js TypeScript stripping and installed Pi required")
    source = files("automata").joinpath("runtimes/pi/extensions/fast-mode/index.ts")
    (tmp_path / "index.ts").write_text(source.read_text())
    home = tmp_path / "home"
    home.mkdir()
    result = subprocess.run(
        [node, "--test", "--test-timeout=5000", str(Path(__file__).with_suffix(".mjs"))],
        env={**os.environ, "FAST_TEST_ROOT": str(tmp_path),
             "FAST_PI_PACKAGE": str(package.resolve()), "HOME": str(home),
             "PI_CODING_AGENT_DIR": str(home / "agent")},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout)
