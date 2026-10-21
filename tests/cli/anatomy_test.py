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
    assert not (tmp_path / "anatomy/frontend/node_modules").exists()
    assert (tmp_path / "anatomy/frontend/package-lock.json").is_file()
    assert (tmp_path / "anatomy/frontend/build.mjs").is_file()
    # Exercise the copy's Python/template roots, not the checkout's server module.
    script = """
import runpy, sys
from pathlib import Path
from fastapi.testclient import TestClient
launcher = Path(sys.argv[1])
sys.argv = [str(launcher), '--help']
try:
    runpy.run_path(str(launcher), run_name='__main__')
except SystemExit as error:
    assert error.code == 0
from automata.tools.anatomy import config, server
assert config.ROOT == Path.cwd()
assert config.TEMPLATES == launcher.parent / 'templates'
assert not config.SKILLS.is_relative_to(launcher.parent)
with TestClient(server.create_app(), base_url='http://127.0.0.1:8766') as client:
    for path in ('/', '/skills/', '/tools/', '/activity/', '/skills/automata-workplan/',
                 '/lib/adaptive-ui.js', '/shared/components/live-refresh.js'):
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code)
    assert client.get('/lib/echarts.js').status_code == 503
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, str(tmp_path / "anatomy/anatomy.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
