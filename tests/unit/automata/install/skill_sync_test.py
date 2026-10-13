"""Disposable filesystem checks for parent-only, recoverable synchronization."""

import shutil
from pathlib import Path

import pytest

from automata.install.skills import SkillInstallError, install_skills


def skill(path: Path, text: str = "source") -> Path:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(text)
    return path


def snapshot(root: Path) -> dict[str, tuple[bytes | None, int]]:
    return {str(path.relative_to(root)): (path.read_bytes() if path.is_file() else None,
                                         path.stat().st_mtime_ns)
            for path in root.rglob("*")}


@pytest.mark.parametrize("mode", ["copy", "replace", "symlink"])
def test_parent_includes_children_without_extra_exposures(tmp_path: Path, mode: str) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    parent = skill(source / "group" / "parent")
    skill(parent / "skills" / "child")
    results = install_skills(source_root=source, target_root=target, mode=mode)
    assert [result.name for result in results] == ["parent"]
    assert (target / "group/parent/skills/child/SKILL.md").read_text() == "source"
    assert not (target / "child").exists()
    assert not (target / "parent").exists()


@pytest.mark.parametrize("names", [["child"], ["parent", "child"]])
def test_explicit_child_rejected_before_writes(tmp_path: Path, names: list[str]) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    parent = skill(source / "parent")
    skill(parent / "skills" / "child")
    with pytest.raises(SkillInstallError, match="select outer parent parent"):
        install_skills(source_root=source, target_root=target, skill_names=names)
    assert not target.exists()


def test_preview_all_actions_is_read_only_and_apply_is_recoverable(tmp_path: Path) -> None:
    source, target, backups = tmp_path / "source", tmp_path / "target", tmp_path / "backups"
    skill(source / "add")
    skill(source / "change", "new")
    skill(source / "same")
    skill(target / "change", "old")
    skill(target / "same")
    skill(target / "retired", "retired content")
    skill(target / "custom", "custom content")
    (target / "custom/data.txt").write_text("custom data")
    before = snapshot(target)
    arguments = dict(source_root=source, target_root=target, mode="replace",
                     skill_names=["add,change,same"], retire_names=["retired"])
    preview = install_skills(**arguments, dry_run=True, backup_root=backups)
    assert [result.action for result in preview] == ["add", "change", "unchanged", "retire"]
    assert all(result.dry_run for result in preview)
    assert snapshot(target) == before
    assert not backups.exists()
    with pytest.raises(SkillInstallError, match="--backup-root"):
        install_skills(**arguments)
    assert snapshot(target) == before
    results = install_skills(**arguments, backup_root=backups)
    assert snapshot(target)["same/SKILL.md"] == before["same/SKILL.md"]
    assert snapshot(target)["custom/data.txt"] == before["custom/data.txt"]
    assert not (target / "retired").exists()
    assert (target / "change/SKILL.md").read_text() == "new"
    for result in results:
        if result.backup:
            if Path(result.target).exists():
                shutil.rmtree(result.target)
            shutil.copytree(result.backup, result.target)
    assert (target / "change/SKILL.md").read_text() == "old"
    assert (target / "retired/SKILL.md").read_text() == "retired content"


@pytest.mark.parametrize("mode", ["copy", "replace", "symlink"])
def test_unchanged_skips_writes_and_backups(tmp_path: Path, mode: str) -> None:
    source, target, backups = tmp_path / "source", tmp_path / "target", tmp_path / "backups"
    skill(source / "same")
    install_skills(source_root=source, target_root=target, mode=mode)
    before = snapshot(target)
    stat = (target / "same").lstat()
    result, = install_skills(source_root=source, target_root=target, mode=mode, backup_root=backups)
    assert result.action == "unchanged"
    assert result.backup is None
    assert (target / "same").lstat() == stat
    assert snapshot(target) == before
    assert not backups.exists()


def test_retirement_only_preserves_unselected_and_backs_up_symlink(tmp_path: Path) -> None:
    source, target, backups = tmp_path / "source", tmp_path / "target", tmp_path / "backups"
    package = skill(source / "present")
    target.mkdir()
    (target / "legacy").symlink_to(package, target_is_directory=True)
    skill(target / "custom")
    results = install_skills(source_root=source, target_root=target,
                             retire_names=["legacy,absent"], backup_root=backups)
    assert [result.action for result in results] == ["retire", "unchanged"]
    assert Path(results[0].backup).is_symlink()
    assert (package / "SKILL.md").is_file()
    assert not (target / "legacy").exists()
    assert not (target / "present").exists()
    assert (target / "custom/SKILL.md").is_file()


def test_nested_installed_retirement_rejected(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    skill(source / "new")
    parent = skill(target / "old-parent")
    skill(parent / "skills" / "old-child")
    before = snapshot(target)
    with pytest.raises(SkillInstallError, match="select outer parent old-parent"):
        install_skills(source_root=source, target_root=target, retire_names=["old-child"])
    assert snapshot(target) == before


def test_backup_root_must_not_be_inside_selected_package(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    skill(source / "same", "new")
    skill(target / "same", "old")
    with pytest.raises(SkillInstallError, match="Backup root overlaps"):
        install_skills(source_root=source, target_root=target, mode="replace",
                       backup_root=target / "same/backups")
    assert (target / "same/SKILL.md").read_text() == "old"


def test_replace_symlink_backs_up_link_not_referent(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    package = skill(source / "same")
    install_skills(source_root=source, target_root=target, mode="symlink")
    result, = install_skills(source_root=source, target_root=target, mode="replace",
                             backup_root=tmp_path / "backups")
    assert result.action == "change"
    assert Path(result.backup).is_symlink()
    assert not (target / "same").is_symlink()
    assert (package / "SKILL.md").read_text() == "source"


def test_conflict_late_in_selection_does_not_partially_install(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    skill(source / "add")
    skill(source / "conflict")
    skill(target / "conflict", "different")
    with pytest.raises(SkillInstallError, match="already exists"):
        install_skills(source_root=source, target_root=target)
    assert not (target / "add").exists()


def test_retire_grouped_link_absent_from_catalog(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    skill(source / "new")
    old = skill(tmp_path / "external/old")
    (target / "group").mkdir(parents=True)
    (target / "group/old").symlink_to(old, target_is_directory=True)
    result, = install_skills(source_root=source, target_root=target, retire_names=["old"],
                             backup_root=tmp_path / "backups")
    assert result.action == "retire"
    assert Path(result.backup).is_symlink()
    assert (old / "SKILL.md").is_file()
    assert not (target / "group/old").exists()


def test_executable_mode_change_is_not_unchanged(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    skill(source / "same")
    install_skills(source_root=source, target_root=target)
    (source / "same/SKILL.md").chmod(0o755)
    result, = install_skills(source_root=source, target_root=target, dry_run=True)
    assert result.action == "change"


def test_source_cannot_be_retired_as_its_own_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    skill(source / "same")
    with pytest.raises(SkillInstallError, match="Retirement overlaps"):
        install_skills(source_root=source, target_root=source, retire_names=["same"],
                       backup_root=tmp_path / "backups")
    assert (source / "same/SKILL.md").is_file()


def test_copied_directory_links_are_unchanged_on_second_sync(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    package = skill(source / "same")
    external = tmp_path / "external"
    external.mkdir()
    (external / "asset.txt").write_text("asset")
    (package / "assets").symlink_to(external, target_is_directory=True)
    install_skills(source_root=source, target_root=target)
    assert not (target / "same/assets").is_symlink()
    result, = install_skills(source_root=source, target_root=target, mode="replace")
    assert result.action == "unchanged"
