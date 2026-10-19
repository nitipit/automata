"""NodalWire extension tests with fake transport; no relay or live model required."""
import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest

PI_LINK_ROOT = Path.home() / ".local/share/pnpm/store/v11/links/@earendil-works/pi-coding-agent"


def test_nodalwire_extension(tmp_path):
    node = shutil.which("node")
    candidates = sorted(PI_LINK_ROOT.glob("*/*/node_modules/@earendil-works/pi-coding-agent"))
    override = os.environ.get("PI_TEST_PACKAGE_ROOT")
    package = Path(override) if override else (candidates[-1] if candidates else None)
    if node is None or package is None:
        pytest.skip("Node.js 24 and installed Pi required")
    source = files("automata").joinpath("runtimes/pi/extensions/nodalwire/index.ts")
    (tmp_path / "index.ts").write_text(source.read_text())
    modules = tmp_path / "node_modules"
    modules.mkdir()
    (modules / "typebox").symlink_to(package.resolve().parents[1] / "typebox")
    result = subprocess.run(
        [node, "--test", "--test-timeout=5000", str(Path(__file__).with_suffix(".mjs"))],
        env={**os.environ, "NODALWIRE_TEST_ROOT": str(tmp_path)},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout)
