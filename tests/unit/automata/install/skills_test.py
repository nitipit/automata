from importlib import import_module
from pathlib import Path

import pytest

from automata.install.skills import (
    SkillInstallError,
    bundled_skill_roots,
    install_skills,
    list_skill_dirs,
    resolve_source_root,
    skill_sources,
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


def test_default_sources_include_shared_and_pi_skills_without_shadowing() -> None:
    shared, pi = bundled_skill_roots()
    sources = skill_sources()
    assert shared.name == "skills" and pi.name == "skills"
    assert sources["automata-storage"].is_relative_to(shared)
    assert sources["automata-context-status"] == pi / "automata-context-status"
    assert len(sources) == len(set(sources))


def test_install_skills_selects_shared_and_pi_skills_together(tmp_path: Path) -> None:
    target = tmp_path / "skills"
    results = install_skills(
        target_root=target,
        skill_names=["automata-storage", "automata-context-status"],
    )
    assert [result.name for result in results] == ["automata-storage", "automata-context-status"]
    for name in ("automata-storage", "automata-context-status"):
        assert (target / name / "SKILL.md").is_file()


def test_explicit_skill_source_is_exclusive_and_recurses(tmp_path: Path) -> None:
    source = tmp_path / "custom"
    make_grouped_skill(source, "nested", "automata-storage")
    assert skill_sources(source)["automata-storage"] == source / "nested" / "automata-storage"
    assert "automata-context-status" not in skill_sources(source)
    target = tmp_path / "dest"
    with pytest.raises(SkillInstallError, match="automata-context-status"):
        install_skills(
            source_root=source,
            target_root=target,
            skill_names=["automata-storage", "automata-context-status"],
        )
    assert not target.exists()


def test_missing_default_selection_does_not_partially_install(tmp_path: Path) -> None:
    target = tmp_path / "dest"
    with pytest.raises(SkillInstallError, match="does-not-exist"):
        install_skills(
            target_root=target, skill_names=["automata-storage", "does-not-exist"]
        )
    assert not target.exists()


def test_invalid_selection_does_not_partially_install(tmp_path: Path) -> None:
    target = tmp_path / "dest"
    with pytest.raises(SkillInstallError, match="Invalid skill name"):
        install_skills(target_root=target, skill_names=["automata-storage", "../escape"])
    assert not target.exists()


def test_duplicate_names_across_bundled_roots_fail_before_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared, pi = tmp_path / "shared", tmp_path / "pi"
    make_skill(shared / "same-skill")
    make_skill(pi / "same-skill")
    skills_module = import_module("automata.install.skills")
    monkeypatch.setattr(skills_module, "bundled_skill_roots", lambda: (shared, pi))
    target = tmp_path / "dest"
    with pytest.raises(SkillInstallError, match="Duplicate skill name"):
        install_skills(target_root=target, skill_names=["same-skill"])
    assert not target.exists()


def test_install_skills_copies_bundled_storage_skill(tmp_path: Path) -> None:
    target_root = tmp_path / "dest"

    results = install_skills(target_root=target_root, skill_names=["automata-storage"])

    assert [result.name for result in results] == ["automata-storage"]
    assert (target_root / "automata-storage" / "SKILL.md").is_file()
    assert not (target_root / "automata-agent-data").exists()


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
