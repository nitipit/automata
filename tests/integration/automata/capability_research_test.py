"""Goal delivery across checkout, skill installation, plugin and Python packages."""

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
GOAL = PROJECT / "goal/main.md"


def assert_self_contained(skill: Path) -> None:
    reference = skill / "references/goal.md"
    assert reference.is_file()
    assert not reference.is_symlink()
    assert reference.read_bytes() == GOAL.read_bytes()
    assert "(references/goal.md)" in (skill / "SKILL.md").read_text()


def test_checkout_reference_has_one_canonical_owner() -> None:
    reference = SOURCE / "references/goal.md"
    assert reference.is_symlink()
    assert not Path(os.readlink(reference)).is_absolute()
    assert reference.resolve() == GOAL.resolve()


def test_copy_and_replace_deliver_goal_outside_checkout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "skills"
    install_skills(target_root=target, skill_names=[NAME])
    installed = target / NAME
    assert_self_contained(installed)
    (installed / "references/goal.md").write_text("stale installed goal")
    install_skills(target_root=target, skill_names=[NAME], mode="replace")
    assert_self_contained(installed)


def test_symlink_install_retains_source_goal_access(tmp_path: Path) -> None:
    target = tmp_path / "skills"
    install_skills(target_root=target, skill_names=[NAME], mode="symlink")
    assert (target / NAME).is_symlink()
    assert (target / NAME / "references/goal.md").resolve() == GOAL.resolve()


def test_plugin_export_materializes_goal(tmp_path: Path) -> None:
    output = tmp_path / "plugin"
    export_plugin(name="research-check", output=output, skill_names=[NAME])
    assert_self_contained(output / "skills" / NAME)


def test_sdist_and_rebuilt_wheel_materialize_goal(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required for the offline package build check")
    # uv's default build makes an sdist, then builds the wheel FROM that sdist.
    # This catches references accidentally depending on the original checkout.
    result = subprocess.run(
        [uv, "build", "--offline", "--out-dir", str(tmp_path)],
        cwd=PROJECT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    suffix = str(Path("automata") / RELATIVE / "references/goal.md")
    with tarfile.open(next(tmp_path.glob("*.tar.gz"))) as archive:
        member = next(m for m in archive.getmembers() if m.name.endswith(suffix))
        assert member.isfile(), "sdist must not depend on an external symlink target"
        stream = archive.extractfile(member)
        assert stream is not None and stream.read() == GOAL.read_bytes()
    with zipfile.ZipFile(next(tmp_path.glob("*.whl"))) as archive:
        assert archive.read(suffix) == GOAL.read_bytes()
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
    assert_self_contained(tmp_path / "installed" / NAME)
    assert_self_contained(tmp_path / "exported/skills" / NAME)
