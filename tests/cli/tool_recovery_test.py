"""Tool preview/backup arguments and actionable CLI failure messages."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from automata.cli import app


@pytest.fixture
def paths(tmp_path):
    source = tmp_path / "source" / "demo"
    source.mkdir(parents=True)
    (source / "main.py").write_text("new\n")
    return source.parent, tmp_path / "tools", tmp_path / "backups"


def command(paths):
    source, target, _ = paths
    return [
        "tools",
        "install",
        "--source-root",
        str(source),
        "--tool",
        "demo",
        "--target-root",
        str(target),
        "--json",
    ]


def test_cli_preview_and_backed_up_replacement(paths, capsys):
    _, target, backups = paths
    with pytest.raises(SystemExit) as exit:
        app([*command(paths), "--dry-run"])
    assert exit.value.code == 0
    preview = json.loads(capsys.readouterr().out)[0]
    assert preview["action"] == "add" and preview["dry_run"]
    assert not target.exists()
    with pytest.raises(SystemExit) as exit:
        app(command(paths))
    assert exit.value.code == 0
    capsys.readouterr()
    (target / "demo/custom.txt").write_text("retain")
    with pytest.raises(SystemExit) as exit:
        app([*command(paths), "--mode", "replace", "--backup-root", str(backups)])
    assert exit.value.code == 0
    result = json.loads(capsys.readouterr().out)[0]
    assert result["action"] == "change"
    assert (Path(result["backup"]) / "custom.txt").read_text() == "retain"
    assert not (target / "demo/custom.txt").exists()


def test_cli_failure_reports_restoration_without_traceback(paths):
    _, target, backups = paths
    installed = target / "demo"
    installed.mkdir(parents=True)
    (installed / "main.py").write_text("old\n")
    script = """
import sys
from automata.cli import app
from automata.install import tools
def fail_publish(staged, target):
    raise OSError("injected publication failure")
tools._publish_tool = fail_publish
app(sys.argv[1:])
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            *command(paths),
            "--mode",
            "replace",
            "--backup-root",
            str(backups),
        ],
        env=os.environ | {"PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "old tool was restored" in result.stderr
    assert str(installed) in result.stderr
    assert "Traceback" not in result.stderr
    assert not result.stdout
    assert (installed / "main.py").read_text() == "old\n"
