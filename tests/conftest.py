"""Shared preparation for the selected Node extension suites, not behavioral tests."""

import json
import os
import re
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest


def _pi_package() -> Path | None:
    if override := os.environ.get("PI_TEST_PACKAGE_ROOT"):
        return Path(override).expanduser().resolve()
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
            try:
                name = json.loads(manifest.read_text()).get("name")
                if name == "@earendil-works/pi-coding-agent":
                    return parent
            except (OSError, ValueError):
                continue
    return None


def _library(name: str, source: Path) -> Path | None:
    # An explicit root is authoritative, allowing units to run without Pi installed.
    if override := os.environ.get("PI_EXTENSION_TEST_NODE_MODULES"):
        candidate = Path(override).expanduser() / name
        return candidate.resolve() if candidate.is_dir() else None
    if name == "edictor" and (override := os.environ.get("NODALWIRE_TEST_NODE_MODULES")):
        candidate = Path(override).expanduser() / name
        return candidate.resolve() if candidate.is_dir() else None
    candidate = source / "node_modules" / name
    if candidate.is_dir():
        return candidate.resolve()
    # Reuse a prepared host library as a convenience, not a unit-test prerequisite.
    if name == "typebox" and (package := _pi_package()):
        candidate = package.resolve().parent.parent / name
        if candidate.is_dir():
            return candidate.resolve()
    return None


@pytest.fixture(scope="session")
def extension_node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js 24+ required for extension TypeScript tests")
    result = subprocess.run(
        [node, "--eval", "console.log(process.versions.node.split('.')[0])"],
        capture_output=True, text=True, timeout=10, check=True,
    )
    if int(result.stdout.strip()) < 24:
        pytest.skip("Node.js 24+ required for extension TypeScript tests")
    return node


@pytest.fixture
def run_extension_node(extension_node: str, tmp_path: Path):
    """Run one independent suite; missing dependencies skip only its pytest case."""
    def run(bundle: str, script: Path, *, libraries: tuple[str, ...] = (), native_pi=False):
        assert script.is_file(), script
        package = _pi_package() if native_pi else None
        if native_pi and (package is None or not (package / "dist/index.js").is_file()):
            pytest.skip("Installed Pi required; set PI_TEST_PACKAGE_ROOT to its package root")
        source = Path(str(files("automata").joinpath("runtimes/pi/extensions", bundle)))
        dependencies = {}
        for name in libraries:
            path = _library(name, source)
            if path is None:
                pytest.skip(f"Prepare {name}; set PI_EXTENSION_TEST_NODE_MODULES")
            dependencies[name] = path
        prepared = tmp_path / bundle
        prepared.mkdir()
        for path in source.glob("*.ts"):
            shutil.copy2(path, prepared / path.name)
        for name, path in dependencies.items():
            target = prepared / "node_modules" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(path, target_is_directory=True)
        env = {**os.environ, "PI_EXTENSION_TEST_ROOT": str(prepared)}
        env.pop("PI_TEST_PACKAGE_ROOT", None)
        env["AUTOMATA_AGENT_TEAM_WORKER"] = ""
        if package is not None:
            env["PI_TEST_PACKAGE_ROOT"] = str(package)
        result = subprocess.run(
            [extension_node, "--experimental-transform-types", "--test", "--test-reporter=tap",
             "--test-timeout=10000", str(script)],
            env=env, capture_output=True, text=True, timeout=60, check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        print(result.stdout)
    return run
