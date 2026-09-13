"""Test the compaction wrapper with isolated Pi/TypeBox adapters, without model calls."""

import json
import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest


def test_context_compaction_runtime_boundaries(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js 22.18+ is required for TypeScript runtime tests")

    extension = tmp_path / "context-compaction.ts"
    extension.write_text(
        files("automata").joinpath("extensions", "context-compaction.ts").read_text()
    )
    package = tmp_path / "node_modules" / "typebox"
    package.mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps({"type": "module", "exports": "./index.js"})
    )
    (package / "index.js").write_text(
        "export const Type = {"
        "String: options => ({type: 'string', ...options}),"
        "Optional: schema => schema,"
        "Object: (properties, options) => ({type: 'object', properties, ...options})"
        "};"
    )

    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_suffix(".mjs"))],
        env={**os.environ, "CONTEXT_TEST_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
