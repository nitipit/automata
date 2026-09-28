"""Explicit example provisioning must not replace existing project content."""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "src/automata/apps/workspace/provision_webboard.py"
spec = importlib.util.spec_from_file_location("provision_webboard", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_copy_assets_only_and_refuse_overwrite(tmp_path):
    target = tmp_path / "northstar/main/web"
    module.provision(target)
    assert {p.name for p in target.iterdir()} == set(module.ASSETS)
    for name in module.ASSETS:
        assert (target / name).read_bytes() == (module.EXAMPLE / name).read_bytes()
    (target / "board.js").write_text("user content")
    with pytest.raises(ValueError, match="overwrite"):
        module.provision(target)
    assert (target / "board.js").read_text() == "user content"


def test_reject_relative_and_parent_paths(tmp_path):
    for target in (Path("relative/web"), tmp_path / "child/../web"):
        with pytest.raises(ValueError, match="absolute"):
            module.provision(target)


@pytest.mark.parametrize("dangling", [False, True])
def test_reject_symlink_ancestor_and_target(tmp_path, dangling):
    actual = tmp_path / "actual"
    if not dangling:
        actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    for target in (link, link / "main/web"):
        with pytest.raises(ValueError, match="symlink"):
            module.provision(target)
    assert not (actual / "main").exists()


def test_cli_explicit_target(tmp_path):
    target = tmp_path / "web"
    first = subprocess.run([sys.executable, str(SCRIPT), str(target)], capture_output=True)
    assert first.returncode == 0
    second = subprocess.run([sys.executable, str(SCRIPT), str(target)], capture_output=True)
    assert second.returncode == 1
    assert b"overwrite" in second.stderr
