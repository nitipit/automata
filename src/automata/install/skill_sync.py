"""Preview and apply explicit skill package changes, with recoverable backups."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from automata.install.directory import DirectoryInstallError, InstallMode, install_one


@dataclass(frozen=True)
class SkillInstallResult:
    source: str
    target: str
    name: str
    mode: str
    action: str
    backup: str | None = None
    dry_run: bool = False


def copied_entries(root: Path) -> dict[Path, Path]:
    """Follow package links just as the established copytree operation does."""
    entries: dict[Path, Path] = {}
    for directory, dirs, files in os.walk(root, followlinks=True):
        for name in [*dirs, *files]:
            path = Path(directory) / name
            entries[path.relative_to(root)] = path
    return entries


def same_content(source: Path, target: Path) -> bool:
    """Compare copied bytes and permission modes, ignoring timestamps."""
    if not source.is_dir() or not target.is_dir():
        return False
    if source.stat().st_mode & 0o777 != target.stat().st_mode & 0o777:
        return False
    left, right = copied_entries(source), copied_entries(target)
    if left.keys() != right.keys():
        return False
    for relative, path in left.items():
        other = right[relative]
        if path.is_dir() != other.is_dir() or path.is_file() != other.is_file():
            return False
        if path.stat().st_mode & 0o777 != other.stat().st_mode & 0o777:
            return False
        if path.is_file() and path.read_bytes() != other.read_bytes():
            return False
    return True


def sync_skills(
    *,
    sources: dict[str, Path],
    targets: dict[str, Path],
    retirements: dict[str, Path],
    mode: InstallMode,
    dry_run: bool,
    backup_root: Path | None,
) -> tuple[SkillInstallResult, ...]:
    """Preflight the complete selection; only changes need backups or writes."""
    if mode not in {"copy", "replace", "symlink"}:
        raise DirectoryInstallError(f"Invalid skill install mode: {mode}")
    results: list[SkillInstallResult] = []
    for name, source in sources.items():
        target = targets[name]
        exists = target.exists() or target.is_symlink()
        unchanged = (
            target.is_symlink() and target.resolve() == source.resolve()
            if mode == "symlink"
            else not target.is_symlink() and same_content(source, target)
        )
        action = "unchanged" if unchanged else "change" if exists else "add"
        if action == "change" and mode != "replace" and not dry_run:
            raise DirectoryInstallError(f"Destination skill already exists: {target}")
        # Never replace a source or write an installation into its own package.
        destination = target.parent.resolve() / target.name
        if source.resolve() == destination or (
            source.resolve() in destination.parents or destination in source.resolve().parents
        ):
            if not unchanged:
                raise DirectoryInstallError(f"Skill destination overlaps source: {target}")
        results.append(SkillInstallResult(
            str(source), str(target), name, mode, action, dry_run=dry_run,
        ))
    for name, target in retirements.items():
        action = "retire" if target.exists() or target.is_symlink() else "unchanged"
        results.append(SkillInstallResult("", str(target), name, mode, action, dry_run=dry_run))

    paths = [Path(result.target).parent.resolve() / Path(result.target).name for result in results]
    for index, path in enumerate(paths):
        if any(path == other or path in other.parents or other in path.parents
               for other in paths[index + 1:]):
            raise DirectoryInstallError(f"Selected skill destinations overlap: {path}")
    destructive = [result for result in results if result.action in {"change", "retire"}]
    if destructive and backup_root is None and not dry_run:
        raise DirectoryInstallError("Use --backup-root for changed or retired skill directories")
    if backup_root is not None:
        backup_root = backup_root.expanduser()
        for path in [*sources.values(), *targets.values(), *retirements.values()]:
            if backup_root.resolve() == path.resolve() or (
                backup_root.resolve() in path.resolve().parents
                or path.resolve() in backup_root.resolve().parents
            ):
                raise DirectoryInstallError(f"Backup root overlaps a selected skill: {path}")
    if dry_run:
        return tuple(results)

    backup_batch: Path | None = None
    applied: list[SkillInstallResult] = []
    for result in results:
        target = Path(result.target)
        backup: Path | None = None
        if result.action in {"change", "retire"}:
            assert backup_root is not None
            if backup_batch is None:
                backup_root.mkdir(parents=True, exist_ok=True)
                backup_batch = Path(tempfile.mkdtemp(prefix="skills-", dir=backup_root))
            backup = backup_batch / result.name
            # Move the directory/link itself: symlink referents are never removed.
            shutil.move(str(target), str(backup))
        if result.action in {"add", "change"}:
            install_one(
                source=Path(result.source), target=target, name=result.name,
                mode=mode, kind="skill",
            )
        applied.append(SkillInstallResult(
            result.source, result.target, result.name, result.mode, result.action,
            str(backup) if backup else None,
        ))
    return tuple(applied)
