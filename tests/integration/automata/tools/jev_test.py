"""Installed CLI, export and wheel checks; no live inference or credential access."""

import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from automata.install.skills import install_skills
from automata.install.tools import install_tools
from automata.plugin.export import export_plugin

PROJECT = Path(__file__).parents[4]
TOOL = PROJECT / "src/automata/tools/jev"
SKILL = "automata-jev"


def invoke(entry, *args, cwd, stdin=None):
    env = {k: v for k, v in os.environ.items() if k != "TYPESAFE_API_KEY"}
    return subprocess.run(
        [sys.executable, str(entry), *args],
        cwd=cwd,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.fixture
def installed(tmp_path):
    install_tools(target_root=tmp_path / "tools", tool_names=["jev"])
    return tmp_path / "tools/jev/jev.py"


def example(entry, cwd):
    result = invoke(entry, "schema", cwd=cwd)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["example"]


def test_installed_help_and_offline_stdin(installed, tmp_path):
    for args in (("--help",), ("judge", "--help")):
        result = invoke(installed, *args, cwd=tmp_path)
        assert result.returncode == 0 and "--execute" in result.stdout
    data = example(installed, tmp_path)
    result = invoke(installed, "judge", "-", cwd=tmp_path, stdin=json.dumps(data))
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["status"] == "validated" and parsed["network_requests"] == 0
    assert parsed["plan"]["maximum_requests"] == 1
    assert not (tmp_path / ".agents").exists()


def test_schema_does_not_require_key(installed, tmp_path):
    data = example(installed, tmp_path)
    result = invoke(
        installed, "judge", "-", "--key-file", "nonexistent", cwd=tmp_path, stdin=json.dumps(data)
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "args,code",
    [
        (["--execute"], "budget_required"),
        (["--execute", "--max-cost-usd", "0.0001"], "budget_too_small"),
        (["--execute", "--max-cost-usd", "0.005"], "credential_format"),
        (["--execute", "--max-cost-usd", "0.005", "--key-file", "absent"], "credential_read"),
    ],
)
def test_execute_preconditions_do_not_send(installed, tmp_path, args, code):
    data = example(installed, tmp_path)
    result = invoke(installed, "judge", "-", *args, cwd=tmp_path, stdin=json.dumps(data))
    assert result.returncode == 2
    assert not result.stdout
    error = json.loads(result.stderr)
    assert error["code"] == code and error["outcome"] == "not_sent"
    assert error["automatic_retry"] is False


@pytest.mark.parametrize(
    "text",
    ["SECRET_INVALID_JSON", '{"secret":"DO_NOT_ECHO"}', "x" * 16385],
    ids=["invalid-json", "unknown-fields", "oversized"],
)
def test_bad_inputs_never_echo_content(installed, tmp_path, text):
    result = invoke(installed, "judge", "-", cwd=tmp_path, stdin=text)
    assert result.returncode == 2
    assert "SECRET_INVALID_JSON" not in result.stderr
    assert "DO_NOT_ECHO" not in result.stderr
    assert "Traceback" not in result.stderr
    assert not result.stdout


def test_skill_mapping_replace_and_plugin(tmp_path):
    install_tools(target_root=tmp_path / "tools", tool_names=["jev"])
    (tmp_path / "tools/jev/stale").write_text("obsolete")
    install_tools(target_root=tmp_path / "tools", tool_names=["jev"], mode="replace")
    assert not (tmp_path / "tools/jev/stale").exists()
    assert not (tmp_path / "tools/jev/__pycache__").exists()
    install_skills(target_root=tmp_path / "skills", skill_names=[SKILL])
    text = (tmp_path / "skills" / SKILL / "SKILL.md").read_text()
    assert ".agents/tools/jev/jev.py" in text
    export_plugin(
        name="jev-check", output=tmp_path / "export", skill_names=[SKILL], tool_names=["jev"]
    )
    exported = list((tmp_path / "export").rglob("jev.py"))
    assert len(exported) == 1
    assert example(exported[0], tmp_path)["model"] == "jev-1.13.0"


def test_sdist_wheel_installer_outside_checkout(tmp_path):
    uv = shutil.which("uv")
    if not uv:
        pytest.skip("uv required for offline build")
    result = subprocess.run(
        [uv, "build", "--offline", "--out-dir", str(tmp_path)],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    required = [
        "automata/tools/jev/jev.py",
        "automata/tools/jev/jev_contract.py",
        "automata/skills/operations/automata-jev/SKILL.md",
    ]
    with tarfile.open(next(tmp_path.glob("*.tar.gz"))) as archive:
        for suffix in required:
            member = next(m for m in archive.getmembers() if m.name.endswith(suffix))
            assert member.isfile()
    with zipfile.ZipFile(next(tmp_path.glob("*.whl"))) as archive:
        for suffix in required:
            assert suffix in archive.namelist()
        assert not any("__pycache__" in p or p.endswith(".apikey") for p in archive.namelist())
        archive.extractall(tmp_path / "wheel")
    env = {**os.environ, "PYTHONPATH": str(tmp_path / "wheel")}
    script = (
        "from automata.install.tools import install_tools; "
        "from automata.install.skills import install_skills; "
        "install_tools(target_root='installed/tools', tool_names=['jev']); "
        "install_skills(target_root='installed/skills', skill_names=['automata-jev'])"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    entry = tmp_path / "installed/tools/jev/jev.py"
    data = example(entry, tmp_path)
    result = invoke(entry, "judge", "-", cwd=tmp_path, stdin=json.dumps(data))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["network_requests"] == 0
