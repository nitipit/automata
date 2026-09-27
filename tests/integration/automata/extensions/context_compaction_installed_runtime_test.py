"""Exercise the extension against the installed Pi runtime without provider I/O."""

import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest

PI_LINK_ROOT = Path.home() / ".local/share/pnpm/store/v11/links/@earendil-works/pi-coding-agent"


def installed_package() -> Path | None:
    candidates = sorted(
        PI_LINK_ROOT.glob("*/*/node_modules/@earendil-works/pi-coding-agent"),
        key=str,
    )
    return candidates[-1] if candidates else None


def test_context_compaction_installed_runtime_offline(tmp_path: Path) -> None:
    node = shutil.which("node")
    package = installed_package()
    if node is None or package is None:
        pytest.skip("Node.js and the installed Pi coding-agent package are required")

    (tmp_path / "context-compaction.ts").write_text(
        files("automata")
        .joinpath("runtimes", "pi", "extensions", "context-compaction.ts")
        .read_text()
    )
    typebox = tmp_path / "node_modules" / "typebox"
    typebox.mkdir(parents=True)
    (typebox / "package.json").write_text('{"type":"module","exports":"./index.js"}')
    (typebox / "index.js").write_text(
        "export const Type = {"
        "String: options => ({type: 'string', ...options}),"
        "Optional: schema => schema,"
        "Object: (properties, options) => ({type: 'object', properties, ...options})"
        "};"
    )
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
