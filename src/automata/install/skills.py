"""Install Automata skill directories into an agent skill root."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from automata.install import directory
from automata.install.directory import (
    DirectoryInstallError,
    InstallMode,
    normalize_names,
    validate_directory_name,
)
from automata.install.skill_sync import SkillInstallResult, sync_skills

SkillInstallError = DirectoryInstallError


def bundled_skill_root() -> Path:
    """Return the single bundled catalog shared by viewer and installer."""

    return Path(str(files("automata").joinpath("skills")))


def bundled_skill_roots() -> tuple[Path, ...]:
    """Compatibility accessor for callers expecting a sequence of roots."""

    return (bundled_skill_root(),)


def skill_sources(source_root: str | Path | None = None) -> dict[str, Path]:
    """Discover one bundled catalog or an isolated explicit custom source."""

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
    dry_run: bool = False,
    backup_root: str | Path | None = None,
    retire_names: tuple[str, ...] | list[str] = (),
) -> tuple[SkillInstallResult, ...]:
    sources = skill_sources(source_root)
    retired = tuple(dict.fromkeys(normalize_skill_names(retire_names)))
    requested = normalize_skill_names(skill_names)
    selected_names = requested or (() if retired else tuple(outer_skill_sources(sources)))
    if not selected_names and not retired:
        raise SkillInstallError(f"No skill directories found under: {source_root}")
    selected = select_skill_sources(sources, selected_names)
    target = Path(target_root).expanduser()
    targets = {
        name: target / skill_relative_path(path, source_root) for name, path in selected.items()
    }
    installed: list[Path] = []
    if retired and target.is_dir():
        # Include symlinked roots without following their nested contents. Legacy
        # flat exposures may coexist with same-name children inside a parent.
        installed = [
            path
            for path in sorted(target.rglob("*"))
            if path.is_dir() and (path / "SKILL.md").is_file()
        ]
    outer_sources = outer_skill_sources(sources)
    retirements: dict[str, Path] = {}
    for name in retired:
        validate_directory_name(name, kind="skill")
        if name in selected:
            raise SkillInstallError(f"Cannot install and retire the same skill: {name}")
        flat = target / name
        if flat.exists() or flat.is_symlink() or (name in sources and name not in outer_sources):
            # --retire names destinations, not source installation units. A
            # catalog child can have an obsolete flat exposure; never retire its
            # embedded copy, including on a repeated retirement of the flat one.
            destination = flat
        else:
            matches = [path for path in installed if path.name == name]
            if len(matches) > 1:
                raise SkillInstallError(f"Duplicate installed skill name: {name}")
            destination = (
                matches[0]
                if matches
                else (
                    target / skill_relative_path(sources[name], source_root)
                    if name in sources
                    else flat
                )
            )
        parents = [path for path in installed if path in destination.parents]
        if parents:
            parent = min(parents, key=lambda path: len(path.parts))
            raise SkillInstallError(
                f"Nested skill {name} cannot be retired inside its package; "
                f"select outer parent {parent.name}"
            )
        retirements[name] = destination
    for path in retirements.values():
        destination = path.parent.resolve() / path.name
        if any(
            destination == source.resolve()
            or destination in source.resolve().parents
            or source.resolve() in destination.parents
            for source in sources.values()
        ):
            raise SkillInstallError(f"Retirement overlaps a skill source: {path}")
    return sync_skills(
        sources=selected,
        targets=targets,
        retirements=retirements,
        mode=mode,
        dry_run=dry_run,
        backup_root=Path(backup_root) if backup_root is not None else None,
    )


def outer_skill_sources(sources: dict[str, Path]) -> dict[str, Path]:
    """Keep a selected parent once: its package already contains nested skills.

    Results describe copied/exposed roots, not every skill inside those roots.
    Explicit selections must additionally pass select_skill_sources.
    """
    return {
        name: path
        for name, path in sources.items()
        if not any(parent in path.parents for parent in sources.values())
    }


def select_skill_sources(
    sources: dict[str, Path],
    names: tuple[str, ...] | list[str],
) -> dict[str, Path]:
    """Only outer parents are installation units, even for explicit selections."""
    outer = outer_skill_sources(sources)
    selected: dict[str, Path] = {}
    for name in names:
        validate_directory_name(name, kind="skill")
        if name not in sources:
            raise SkillInstallError(f"Source skill directory does not exist: {name}")
        if name not in outer:
            parent = next(parent for parent, path in outer.items() if path in sources[name].parents)
            raise SkillInstallError(
                f"Nested skill {name} is not an installation unit; select outer parent {parent}"
            )
        selected[name] = sources[name]
    return selected


def skill_relative_path(source: Path, source_root: str | Path | None = None) -> Path:
    """Retain grouping directories as well as the nested package layout."""
    roots = (
        (resolve_source_root(source_root),) if source_root is not None else bundled_skill_roots()
    )
    for root in roots:
        if source == root or root in source.parents:
            relative = source.relative_to(root)
            return relative if relative != Path(".") else Path(source.name)
    raise SkillInstallError(f"Skill is outside its source catalog: {source}")


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
