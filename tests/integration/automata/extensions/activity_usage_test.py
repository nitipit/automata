"""Exercise the standalone activity extension without a model or installation."""
import json
import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest


def test_activity_usage_runtime(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js 22.18+ is required")
    source = files("automata").joinpath("runtimes", "pi", "extensions", "activity-usage.ts")
    (tmp_path / "activity-usage.ts").write_text(source.read_text())
    package = tmp_path / "node_modules" / "typebox"
    package.mkdir(parents=True)
    (package / "package.json").write_text(json.dumps({"type": "module", "exports": "./index.js"}))
    (package / "index.js").write_text("export const Type = new Proxy({}, {get: () => (...args) => args});")
    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_suffix(".mjs"))],
        env={**os.environ, "CONTEXT_TEST_ROOT": str(tmp_path)}, capture_output=True,
        text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
