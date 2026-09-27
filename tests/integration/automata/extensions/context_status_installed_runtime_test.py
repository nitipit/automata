"""Validate native Pi context transformation and model-message conversion offline."""

import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest

PI_LINK_ROOT = Path.home() / ".local/share/pnpm/store/v11/links/@earendil-works/pi-coding-agent"


def test_context_status_installed_runtime_offline(tmp_path: Path) -> None:
    node = shutil.which("node")
    candidates = sorted(
        PI_LINK_ROOT.glob("*/*/node_modules/@earendil-works/pi-coding-agent"), key=str
    )
    override = os.environ.get("PI_TEST_PACKAGE_ROOT")
    package = Path(override) if override else (candidates[-1] if candidates else None)
    if node is None or package is None:
        pytest.skip("Node.js and the installed Pi coding-agent package are required")
    assert (package / "dist/core/extensions/runner.js").is_file(), package

    (tmp_path / "context-status.ts").write_text(
        files("automata").joinpath("runtimes", "pi", "extensions", "context-status.ts").read_text()
    )
    typebox = tmp_path / "node_modules" / "typebox"
    typebox.mkdir(parents=True)
    (typebox / "package.json").write_text('{"type":"module","exports":"./index.js"}')
    (typebox / "index.js").write_text("export const Type = {Object: () => ({})};")
    pi_package = tmp_path / "node_modules" / "@earendil-works" / "pi-coding-agent"
    pi_package.parent.mkdir(parents=True)
    pi_package.symlink_to(package, target_is_directory=True)

    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_suffix(".mjs"))],
        env={**os.environ, "CONTEXT_TEST_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
