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
    """Return the runtime-independent skill root, not the combined catalog."""

    return Path(str(files("automata").joinpath("skills")))


def bundled_skill_roots() -> tuple[Path, ...]:
    """Preserve the bundled Pi catalog while keeping its sources separate."""

    return (
        bundled_skill_root(),
        Path(str(files("automata").joinpath("runtimes", "pi", "skills"))),
    )


def skill_sources(source_root: str | Path | None = None) -> dict[str, Path]:
    """Resolve a unique catalog; an explicit source never adds bundled skills.

    Reject collisions across the shared and Pi roots rather than silently choosing
    a runtime override. Callers resolve their complete selection before writing.
    """

    roots = (
        (resolve_source_root(source_root),)
        if source_root is not None
        else tuple(resolve_source_root(root) for root in bundled_skill_roots())
    )
    sources: dict[str, Path] = {}
    for root in roots:
        for path in sorted(root.rglob("SKILL.md")):
            name = path.parent.name
            if name in sources:
                raise SkillInstallError(
                    f"Duplicate skill name found: {name}: {sources[name]} and {path.parent}"
                )
            sources[name] = path.parent
    return dict(sorted(sources.items()))


def install_skills(
    *,
    source_root: str | Path | None = None,
    target_root: str | Path,
    skill_names: tuple[str, ...] | list[str] = (),
    mode: InstallMode = "copy",
) -> tuple[SkillInstallResult, ...]:
    sources = skill_sources(source_root)
    selected_names = normalize_skill_names(skill_names) or tuple(sources)
    if not selected_names:
        raise SkillInstallError(f"No skill directories found under: {source_root}")

    # Validate every requested name before an earlier item can mutate a destination.
    for name in selected_names:
        validate_directory_name(name, kind="skill")
        if name not in sources:
            raise SkillInstallError(f"Source skill directory does not exist: {name}")

    return tuple(
        install_one(
            source=sources[name],
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
