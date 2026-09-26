"""Neutral installation and CLI contracts; no real LINE profile or network use."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from automata.install.skills import install_skills
from automata.install.tools import install_tools

SOURCE = Path(__file__).parents[5] / "src/automata/tools/line"


def test_install_is_code_only_and_skill_mapping_is_neutral(tmp_path):
    tools = tmp_path / "tools"
    skills = tmp_path / "skills"
    install_tools(target_root=tools, tool_names=["line"])
    install_skills(target_root=skills, skill_names=["automata-line-use"])
    assert {p.name for p in (tools / "line").iterdir()} == {
        "line_cli.py",
        "line_runtime.py",
        "line_schemas.py",
        "line_send.py",
        "reading_api.py",
        "reading_state.py",
        "sticker_api.py",
        "sticker_ui.py",
    }
    assert not (tmp_path / ".agents").exists()
    text = (skills / "automata-line-use/SKILL.md").read_text()
    assert ".agents/tools/line/line_cli.py" in text
    for path in [*(tools / "line").rglob("*"), *(skills / "automata-line-use").rglob("*")]:
        if path.is_file():
            contents = path.read_text()
            assert "nitipit" not in contents.casefold()
            assert "PTA IT" not in contents
    assert not list(tmp_path.rglob("checkpoints.json"))
    assert not list(tmp_path.rglob("draft.json"))


def load_tool(path=SOURCE / "line_runtime.py"):
    spec = importlib.util.spec_from_file_location("line_scope_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_paths_follow_calling_workspace_not_install_location(tmp_path, monkeypatch):
    install = tmp_path / "global-tools"
    install_tools(target_root=install, tool_names=["line"])
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.delenv("AUTOMATA_LINE_PROFILE", raising=False)
    tool = load_tool(install / "line/line_runtime.py")
    assert tool.ROOT == workspace
    assert tool.PROFILE == workspace / ".agents/var/browser/line"
    assert tool.STATE == workspace / ".agents/var/tools/line"
    assert not (install / ".agents").exists()
    assert not (workspace / ".agents").exists()


def test_explicit_isolated_profile_and_scope_binding(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    isolated = tmp_path / "isolated"
    monkeypatch.setenv("AUTOMATA_LINE_PROFILE", str(isolated))
    tool = load_tool()
    assert tool.PROFILE == isolated
    tool.check_profile_scope()
    tool.STATE.mkdir(parents=True)
    (tool.STATE / "profile.json").write_text(json.dumps({"version": 1, "profile": str(isolated)}))
    tool.check_profile_scope()
    monkeypatch.setattr(tool, "PROFILE", tmp_path / "another-profile")
    with pytest.raises(RuntimeError, match="another profile"):
        tool.check_profile_scope()


def test_personal_profile_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("AUTOMATA_LINE_PROFILE", str(tmp_path / "config/google-chrome"))
    with pytest.raises(RuntimeError, match="Personal/default"):
        load_tool().check_profile_scope()


def test_installed_cli_is_json_and_does_not_create_profile(tmp_path):
    pytest.importorskip("dictify")
    pytest.importorskip("playwright")
    install_tools(target_root=tmp_path / "tools", tool_names=["line"])
    script = tmp_path / "tools/line/line_cli.py"
    env = dict(
        os.environ, AUTOMATA_LINE_TIMEZONE="UTC", AUTOMATA_LINE_PROFILE=str(tmp_path / "isolated")
    )
    help_contracts = {
        "": ["LINE Chrome extension", "already-running isolated profile"],
        "status": ["without reading messages"],
        "open-chat": ["may mark messages read", "--chat-id"],
        "chats": ["List stable chat IDs", "--search"],
        "read": [
            "never save",
            "--after",
            "--before",
            "--until",
            "oldest-first",
            "Maximum messages returned",
            "Stable chat ID",
        ],
        "send": [
            "before dispatch",
            "Never retry",
            "--confirm",
            "--draft",
            "--image",
            "Exact text",
            "One local PNG",
        ],
        "stickers": ["clicks can send", "--package-id"],
    }
    for command, expected in help_contracts.items():
        args = [command, "--help"] if command else ["--help"]
        process = subprocess.run(
            [sys.executable, str(script), *args],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert process.returncode == 0, process.stderr
        rendered = " ".join(process.stdout.split())
        for fragment in expected:
            assert fragment in rendered, (command, fragment, process.stdout)
    # Reading help must not launch a browser or initialize workspace state.
    assert not (tmp_path / ".agents").exists()
    assert not (tmp_path / "isolated").exists()
    process = subprocess.run(
        [sys.executable, str(script), "read"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert process.returncode == 2
    assert json.loads(process.stderr)["code"] == "INVALID_ARGUMENT"
    process = subprocess.run(
        [sys.executable, str(script), "state"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert process.returncode == 2
    assert json.loads(process.stderr)["code"] == "INVALID_ARGUMENT"
    assert not (tmp_path / "isolated").exists()
    assert not (tmp_path / "tools/.agents").exists()
    assert not (tmp_path / "LINE.md").exists()


def test_timezone_is_configurable_and_defaults_to_utc(tmp_path):
    pytest.importorskip("dictify")
    env = dict(os.environ, PYTHONPATH=str(SOURCE))
    env.pop("AUTOMATA_LINE_TIMEZONE", None)
    code = "import reading_api; print(reading_api.TIMEZONE)"
    default = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert default.stdout.strip() == "UTC", default.stderr
    selected = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=dict(env, AUTOMATA_LINE_TIMEZONE="Europe/London"),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert selected.stdout.strip() == "Europe/London", selected.stderr
