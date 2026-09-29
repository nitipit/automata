"""Token landmarks against installed Pi, offline and isolated from user state."""
import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest

PI_LINK_ROOT = Path.home() / ".local/share/pnpm/store/v11/links/@earendil-works/pi-coding-agent"


def test_token_awareness(tmp_path):
    node = shutil.which("node")
    candidates = sorted(PI_LINK_ROOT.glob("*/*/node_modules/@earendil-works/pi-coding-agent"))
    override = os.environ.get("PI_TEST_PACKAGE_ROOT")
    package = Path(override) if override else (candidates[-1] if candidates else None)
    if node is None or package is None:
        pytest.skip("Node.js TypeScript stripping and installed Pi required")
    package = package.resolve()
    modules = tmp_path / "node_modules"
    modules.mkdir()
    (modules / "typebox").symlink_to(package.parent.parent / "typebox", target_is_directory=True)
    for name in ("token-awareness", "message-timestamps"):
        (tmp_path / f"{name}.ts").write_text(
            files("automata").joinpath(f"runtimes/pi/extensions/{name}.ts").read_text()
        )
    home = tmp_path / "home"
    home.mkdir()
    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_suffix(".mjs"))],
        env={**os.environ, "TOKEN_TEST_ROOT": str(tmp_path), "TOKEN_PI_PACKAGE": str(package),
             "HOME": str(home), "PI_CODING_AGENT_DIR": str(home / "agent")},
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout)
