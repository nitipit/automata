"""NodalWire extension tests with fake transport; no relay or live model required."""
import json
import os
import re
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest


def pi_package():
    override = os.environ.get("PI_TEST_PACKAGE_ROOT")
    if override:
        return Path(override)
    launcher = shutil.which("pi")
    if not launcher:
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


def test_nodalwire_extension(tmp_path):
    node = shutil.which("node")
    package = pi_package()
    if node is None or package is None:
        pytest.skip("Node.js 24 and installed Pi required")
    source = files("automata").joinpath("runtimes/pi/extensions/nodalwire")
    dependency_root = Path(os.environ.get("NODALWIRE_TEST_NODE_MODULES", source / "node_modules"))
    edictor = dependency_root / "edictor"
    if not edictor.is_dir():
        pytest.skip("Prepare the pinned Edictor dependency; set NODALWIRE_TEST_NODE_MODULES")
    for name in ("index.ts", "protocol.ts"):
        (tmp_path / name).write_text(source.joinpath(name).read_text())
    modules = tmp_path / "node_modules"
    modules.mkdir()
    (modules / "typebox").symlink_to(package.resolve().parents[1] / "typebox")
    (modules / "edictor").symlink_to(edictor.resolve())
    result = subprocess.run(
        [node, "--test", "--test-timeout=10000", str(Path(__file__).with_suffix(".mjs")),
         str(Path(__file__).with_name("nodalwire_protocol_test.mjs"))],
        env={**os.environ, "NODALWIRE_TEST_ROOT": str(tmp_path),
             "PI_TEST_PACKAGE_ROOT": str(package.resolve())},
        capture_output=True, text=True, timeout=40,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout)
