"""Bundled project creation and source-dependency contracts."""

import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).parents[3]
SKILL = ROOT / "src/automata/skills/automata-web-design/skills/automata-web-app"


def test_create_webapp_from_skill(tmp_path):
    output = tmp_path / "project with spaces"
    command = [sys.executable, str(SKILL / "scripts/create.py"), "--output", str(output)]
    created = subprocess.run(command, capture_output=True, text=True)
    assert created.returncode == 0, created.stderr
    config = json.loads((output / "deno.json").read_text())
    for name, value in config["imports"].items():
        if name.startswith("@adaptive/"):
            assert Path(unquote(urlparse(value).path)).is_file()
    assert (output / "app/main.py").is_file()
    assert (output / "uv.lock").is_file()
    assert not (output / ".venv").exists()
    assert not (output / "browser").exists()
    repeated = subprocess.run(command, capture_output=True, text=True)
    assert repeated.returncode != 0
    assert "Destination already exists" in repeated.stderr


def test_missing_adaptive_source_does_not_create_project(tmp_path):
    output = tmp_path / "project"
    result = subprocess.run(
        [
            sys.executable,
            str(SKILL / "scripts/create.py"),
            "--output",
            str(output),
            "--adaptive-ui",
            str(tmp_path / "absent"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Missing Adaptive UI source" in result.stderr
    assert not output.exists()
