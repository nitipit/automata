"""Unified tool command names, lazy dependencies and copied-tool entry points."""

import subprocess
import sys
import tomllib
from pathlib import Path

from automata.install.tools import install_tools


def test_anatomy_foreground_default_and_explicit_asset_root(monkeypatch, tmp_path):
    from automata.tools.anatomy import cli, server

    calls = []
    monkeypatch.setattr(server, "serve", lambda **kwargs: calls.append(kwargs))
    for arguments in ([], ["serve", "--port", "8791", "--asset-root", str(tmp_path)]):
        try:
            cli.app(arguments)
        except SystemExit as error:
            assert error.code == 0
    assert calls == [{"port": 8766}, {"port": 8791, "asset_root": tmp_path}]


def test_core_help_does_not_load_optional_viewer_dependencies():
    script = """
import importlib.abc, sys
blocked = {'fastapi', 'jinja2', 'mistune', 'uvicorn', 'watchfiles', 'yaml',
           'shelfdb', 'dictify', 'textual'}
class NoOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in blocked:
            raise ImportError('Optional import forbidden: ' + fullname)
sys.meta_path.insert(0, NoOptional())
from automata.cli import app
app(['--help'])
assert not blocked.intersection(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "anatomy" in result.stdout
    assert "team" not in result.stdout.casefold()


def test_public_entry_points_and_optional_dependency_ownership():
    root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((root / "pyproject.toml").read_text())
    scripts = config["project"]["scripts"]
    assert scripts["automata-anatomy"] == "automata.tools.anatomy.cli:app"
    assert "automata-team" not in scripts
    assert config["project"]["dependencies"] == ["cyclopts>=4.11.1"]
    assert "fastapi>=0.115,<1" in config["project"]["optional-dependencies"]["anatomy"]
    assert "team" not in config["project"]["optional-dependencies"]


def test_copied_anatomy_launcher_is_usable(tmp_path):
    install_tools(target_root=tmp_path, tool_names=["anatomy"])
    for name, launcher, title in [
        ("anatomy", "anatomy.py", "Automata Anatomy"),
    ]:
        result = subprocess.run(
            [sys.executable, "-B", str(tmp_path / name / launcher), "--help"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert title in result.stdout
    assert not (tmp_path / "anatomy/skills").exists()
