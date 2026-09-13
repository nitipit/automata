from pathlib import Path

import pytest

from automata.install.skills import (
    SkillInstallError,
    install_skills,
    list_skill_dirs,
    resolve_source_root,
)


def test_list_skill_dirs_finds_grouped_skills(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    make_grouped_skill(source_root, "core", "automata-core")
    make_grouped_skill(source_root, "operations", "automata-ops")

    assert list_skill_dirs(source_root) == ("automata-core", "automata-ops")


def test_install_skills_flattens_grouped_source(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / ".agents" / "skills"
    make_grouped_skill(source_root, "core", "automata-core")
    make_grouped_skill(source_root, "operations", "automata-ops")

    results = install_skills(source_root=source_root, target_root=target_root)

    assert [result.name for result in results] == ["automata-core", "automata-ops"]
    assert (target_root / "automata-core" / "SKILL.md").is_file()
    assert (target_root / "automata-ops" / "SKILL.md").is_file()
    assert not (target_root / "core").exists()
    assert not (target_root / "operations").exists()


def test_install_skills_supports_selected_nested_skill(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    make_grouped_skill(source_root, "core", "automata-core")
    make_grouped_skill(source_root, "operations", "automata-ops")

    install_skills(
        source_root=source_root,
        target_root=target_root,
        skill_names=["automata-ops"],
        mode="symlink",
    )

    assert (target_root / "automata-ops").is_symlink()
    assert (target_root / "automata-ops" / "SKILL.md").is_file()
    assert not (target_root / "automata-core").exists()


def test_list_skill_dirs_rejects_duplicate_names(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    make_grouped_skill(source_root, "core", "automata-duplicate")
    make_grouped_skill(source_root, "operations", "automata-duplicate")

    with pytest.raises(SkillInstallError, match="Duplicate skill name"):
        list_skill_dirs(source_root)


def test_install_skills_copies_bundled_agent_data_skill(tmp_path: Path) -> None:
    from automata.install.skills import install_skills

    target_root = tmp_path / "dest"

    results = install_skills(target_root=target_root, skill_names=["automata-agent-data"])

    assert [result.name for result in results] == ["automata-agent-data"]
    assert (target_root / "automata-agent-data" / "SKILL.md").is_file()


def test_install_skills_copies_bundled_agent_evaluation_support(tmp_path: Path) -> None:
    target_root = tmp_path / "dest"

    install_skills(target_root=target_root, skill_names=["automata-agent-evaluation"])

    installed = target_root / "automata-agent-evaluation"
    assert (installed / "SKILL.md").is_file()
    assert (installed / "references" / "scoring.md").is_file()
    assert (installed / "templates" / "evaluation-record.json").is_file()


def test_install_skills_copies_all_source_root_children(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    make_skill(source_root / "my-skill")
    make_skill(source_root / "other-skill")
    target_root = tmp_path / "dest"

    results = install_skills(source_root=source_root, target_root=target_root)

    assert {result.name for result in results} == {"my-skill", "other-skill"}
    assert (target_root / "my-skill" / "SKILL.md").exists()
    assert (target_root / "other-skill" / "SKILL.md").exists()


def test_install_skills_can_select_one_skill(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    make_skill(source_root / "my-skill")
    make_skill(source_root / "other-skill")
    target_root = tmp_path / "dest"

    results = install_skills(
        source_root=source_root,
        target_root=target_root,
        skill_names=["my-skill"],
    )

    assert len(results) == 1
    assert results[0].name == "my-skill"
    assert (target_root / "my-skill" / "SKILL.md").exists()
    assert not (target_root / "other-skill").exists()


def test_install_skills_supports_file_url_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    make_skill(source_root / "my-skill")

    install_skills(source_root=source_root.as_uri(), target_root=tmp_path / "dest")

    assert (tmp_path / "dest" / "my-skill" / "SKILL.md").exists()


def test_install_skills_refuses_existing_target_without_replace(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    make_skill(source_root / "my-skill")
    (tmp_path / "dest" / "my-skill").mkdir(parents=True)

    with pytest.raises(SkillInstallError, match="already exists"):
        install_skills(source_root=source_root, target_root=tmp_path / "dest")


def test_install_skills_replaces_existing_target(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    make_skill(source_root / "my-skill")
    old_file = tmp_path / "dest" / "my-skill" / "old.txt"
    old_file.parent.mkdir(parents=True)
    old_file.write_text("old\n")

    install_skills(source_root=source_root, target_root=tmp_path / "dest", mode="replace")

    assert not old_file.exists()
    assert (tmp_path / "dest" / "my-skill" / "SKILL.md").exists()


def test_install_skills_supports_symlink_mode(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source = make_skill(source_root / "my-skill")
    target = tmp_path / "dest" / "my-skill"

    install_skills(source_root=source_root, target_root=tmp_path / "dest", mode="symlink")

    assert target.is_symlink()
    assert target.resolve() == source.resolve()


def test_install_skills_rejects_remote_source_scheme() -> None:
    with pytest.raises(SkillInstallError, match="Unsupported source scheme"):
        resolve_source_root("https://example.com/skills")


def make_grouped_skill(source_root: Path, group: str, name: str) -> Path:
    skill_dir = source_root / group / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test skill\n---\n\n## Boundaries\n\nTest.\n"
    )
    return skill_dir


def make_skill(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text("# Test Skill\n")
    return path
