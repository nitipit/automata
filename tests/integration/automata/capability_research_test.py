"""Capability research delivery through installation, export and Python packages."""

import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from automata.install.skills import install_skills
from automata.plugin.export import export_plugin

PROJECT = Path(__file__).parents[3]
NAME = "automata-capability-research"
RELATIVE = Path("skills/skill-ops") / NAME
SOURCE = PROJECT / "src/automata" / RELATIVE


def assert_skill_contents(skill: Path) -> None:
    assert (skill / "SKILL.md").read_bytes() == (SOURCE / "SKILL.md").read_bytes()
    assert {p.relative_to(skill) for p in skill.rglob("*")} == {Path("SKILL.md")}


def test_copy_and_replace_deliver_skill_outside_checkout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "skills"
    install_skills(target_root=target, skill_names=[NAME])
    installed = target / NAME
    assert_skill_contents(installed)
    (installed / "SKILL.md").write_text("stale installed skill")
    (installed / "references").mkdir()
    (installed / "references/goal.md").write_text("obsolete reference")
    install_skills(target_root=target, skill_names=[NAME], mode="replace")
    assert_skill_contents(installed)


def test_symlink_install_retains_source_access(tmp_path: Path) -> None:
    target = tmp_path / "skills"
    install_skills(target_root=target, skill_names=[NAME], mode="symlink")
    assert (target / NAME).is_symlink()
    assert (target / NAME).resolve() == SOURCE.resolve()
    assert_skill_contents(target / NAME)


def test_plugin_export_delivers_skill(tmp_path: Path) -> None:
    output = tmp_path / "plugin"
    export_plugin(name="research-check", output=output, skill_names=[NAME])
    assert_skill_contents(output / "skills" / NAME)


def test_sdist_and_rebuilt_wheel_deliver_skill(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required for the offline package build check")
    # uv's default build makes an sdist, then builds the wheel FROM that sdist.
    # Verify the packaged skill works independently of the original checkout.
    result = subprocess.run(
        [uv, "build", "--offline", "--out-dir", str(tmp_path)],
        cwd=PROJECT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    suffix = str(Path("automata") / RELATIVE / "SKILL.md")
    with tarfile.open(next(tmp_path.glob("*.tar.gz"))) as archive:
        member = next(m for m in archive.getmembers() if m.name.endswith(suffix))
        assert member.isfile()
        stream = archive.extractfile(member)
        assert stream is not None and stream.read() == (SOURCE / "SKILL.md").read_bytes()
    with zipfile.ZipFile(next(tmp_path.glob("*.whl"))) as archive:
        assert archive.read(suffix) == (SOURCE / "SKILL.md").read_bytes()
        archive.extractall(tmp_path / "wheel")
    # Exercise actual installer and exporter imported from the built wheel with
    # a CWD outside the checkout; no pip install or environment mutation needed.
    env = dict(os.environ, PYTHONPATH=str(tmp_path / "wheel"))
    script = (
        "from automata.install.skills import install_skills; "
        "from automata.plugin.export import export_plugin; "
        f"install_skills(target_root='installed', skill_names=['{NAME}']); "
        f"export_plugin(name='wheel-check', output='exported', skill_names=['{NAME}'])"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert_skill_contents(tmp_path / "installed" / NAME)
    assert_skill_contents(tmp_path / "exported/skills" / NAME)
