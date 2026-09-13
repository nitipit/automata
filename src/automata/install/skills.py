"""Install Automata skill directories into an agent skill root."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from automata.install import directory
from automata.install.directory import (
    DirectoryInstallError,
    DirectoryInstallResult,
    InstallMode,
    install_one,
    normalize_names,
    validate_directory_name,
)

SkillInstallError = DirectoryInstallError
SkillInstallResult = DirectoryInstallResult


def bundled_skill_root() -> Path:
    return Path(str(files("automata").joinpath("skills")))


def install_skills(
    *,
    source_root: str | Path | None = None,
    target_root: str | Path,
    skill_names: tuple[str, ...] | list[str] = (),
    mode: InstallMode = "copy",
) -> tuple[SkillInstallResult, ...]:
    source_path = resolve_source_root(source_root or bundled_skill_root())
    selected_names = normalize_skill_names(skill_names)
    if not selected_names:
        selected_names = list_skill_dirs(source_path)
    if not selected_names:
        raise SkillInstallError(f"No skill directories found under: {source_path}")

    return tuple(
        install_one(
            source=find_skill_dir(source_path, name),
            target=Path(target_root).expanduser() / name,
            name=name,
            mode=mode,
            kind="skill",
        )
        for name in selected_names
    )


def list_skill_dirs(source_root: Path) -> tuple[str, ...]:
    skill_dirs = sorted(
        (path.parent for path in source_root.rglob("SKILL.md")), key=lambda path: path.name
    )
    names: list[str] = []
    for skill_dir in skill_dirs:
        if skill_dir.name in names:
            raise SkillInstallError(
                f"Duplicate skill name found under: {source_root}: {skill_dir.name}"
            )
        names.append(skill_dir.name)
    return tuple(names)


def find_skill_dir(source_root: Path, skill_name: str) -> Path:
    try:
        validate_directory_name(skill_name, kind="skill")
    except DirectoryInstallError as exc:
        raise SkillInstallError(str(exc)) from exc

    matches = [
        path.parent for path in source_root.rglob("SKILL.md") if path.parent.name == skill_name
    ]
    if not matches:
        raise SkillInstallError(f"Source skill directory does not exist: {skill_name}")
    if len(matches) > 1:
        raise SkillInstallError(f"Duplicate skill name found under: {source_root}: {skill_name}")
    return matches[0]


def normalize_skill_names(skill_names: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    return normalize_names(skill_names)


def resolve_source_root(source_root: str | Path) -> Path:
    return directory.resolve_source_root(source_root, kind="skill")
