"""Install bundled or local tools into an agent tool root."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from automata.install.directory import (
    CopyIgnore,
    DirectoryInstallError,
    DirectoryInstallResult,
    InstallMode,
    install_directories,
    install_one,
    list_directories,
    normalize_names,
    resolve_source_root,
    validate_directory_name,
)

ToolInstallError = DirectoryInstallError
ToolInstallResult = DirectoryInstallResult
TOOL_COPY_IGNORE_FILE = ".automataignore"
DEFAULT_TOOL_COPY_IGNORES = ("__pycache__", "*.pyc", "*.pyo")


@dataclass(frozen=True)
class ToolSyncResult(DirectoryInstallResult):
    action: str
    backup: str | None = None
    dry_run: bool = False


def bundled_tool_root() -> Path:
    return Path(str(files("automata").joinpath("tools")))


def install_tools(
    *,
    target_root: str | Path,
    source_root: str | Path | None = None,
    tool_names: tuple[str, ...] | list[str] = (),
    mode: InstallMode = "copy",
    dry_run: bool = False,
    backup_root: str | Path | None = None,
) -> tuple[ToolInstallResult, ...]:
    source_path = resolve_source_root(source_root or bundled_tool_root(), kind="tool")
    selected = tuple(tool_names) or list_directories(source_path)
    # Preflight all manifests and entry files before any destination is replaced.
    copy_ignores = {}
    for name in selected:
        validate_directory_name(name, kind="tool")
        copy_ignores[name] = tool_copy_ignore(source_path / name)

    if dry_run or backup_root is not None:
        return _sync_tools(
            source_path,
            Path(target_root).expanduser(),
            selected,
            mode,
            dry_run,
            backup_root,
            copy_ignores,
        )

    return install_directories(
        source_root=source_path,
        target_root=target_root,
        names=selected,
        mode=mode,
        kind="tool",
        copy_ignore_factory=lambda source: copy_ignores[source.name],
    )


def _sync_tools(
    source_root: Path,
    target_root: Path,
    names: tuple[str, ...],
    mode: InstallMode,
    dry_run: bool,
    backup_root: str | Path | None,
    ignores: dict[str, CopyIgnore],
) -> tuple[ToolSyncResult, ...]:
    """Opt-in preview/recoverable replacement; preserve legacy install semantics."""
    if mode not in {"copy", "replace", "symlink"}:
        raise ToolInstallError(f"Invalid tool install mode: {mode}")
    if not names:
        raise ToolInstallError(f"No tool directories found under: {source_root}")
    if len(set(names)) != len(names):
        raise ToolInstallError("Selected tool names must be unique")
    if (target_root.exists() or target_root.is_symlink()) and not target_root.is_dir():
        raise ToolInstallError(f"Target root must be a directory: {target_root}")
    backup_root = Path(backup_root).expanduser() if backup_root is not None else None
    if (
        backup_root is not None
        and (backup_root.exists() or backup_root.is_symlink())
        and not backup_root.is_dir()
    ):
        raise ToolInstallError(f"Backup root must be a directory: {backup_root}")
    plans: list[ToolSyncResult] = []
    for name in names:
        source, target = source_root / name, target_root / name
        if not source.is_dir():
            raise ToolInstallError(f"Source tool directory does not exist: {source}")
        destination = target.parent.resolve() / target.name
        if source.resolve() == destination or (
            source.resolve() in destination.parents or destination in source.resolve().parents
        ):
            raise ToolInstallError(f"Tool destination overlaps source: {target}")
        if backup_root is not None:
            for path in (source, target):
                if backup_root.resolve() == path.resolve() or (
                    backup_root.resolve() in path.resolve().parents
                    or path.resolve() in backup_root.resolve().parents
                ):
                    raise ToolInstallError(f"Backup root overlaps selected tool: {path}")
        action = "change" if target.exists() or target.is_symlink() else "add"
        if action == "change" and not dry_run and mode != "replace":
            raise ToolInstallError(f"Destination tool already exists: {target}")
        plans.append(
            ToolSyncResult(
                str(source),
                str(target),
                name,
                mode,
                action,
                dry_run=dry_run,
            )
        )
    if dry_run:
        return tuple(plans)
    batch: Path | None = None
    results: list[ToolSyncResult] = []
    for plan in plans:
        backup = None
        try:
            if plan.action == "change":
                assert backup_root is not None
                if batch is None:
                    backup_root.mkdir(parents=True, exist_ok=True)
                    batch = Path(tempfile.mkdtemp(prefix="tools-", dir=backup_root))
                backup = batch / plan.name
            _apply_tool(plan, mode, ignores[plan.name], backup)
        except (OSError, ToolInstallError) as error:
            earlier = "\n".join(
                f"  {result.name}: {result.target}; backup: {result.backup or '(none)'}"
                for result in results
            )
            detail = f"\nEarlier installations remain applied:\n{earlier}" if earlier else ""
            raise ToolInstallError(
                f"Failed installing tool {plan.name}: {error}{detail}"
            ) from error
        results.append(
            ToolSyncResult(
                plan.source,
                plan.target,
                plan.name,
                mode,
                plan.action,
                str(backup) if backup else None,
            )
        )
    return tuple(results)


def _publish_tool(staged: Path, target: Path) -> None:
    if target.exists() or target.is_symlink():
        raise ToolInstallError(f"Destination appeared during installation: {target}")
    staged.rename(target)


def _apply_tool(
    plan: ToolSyncResult,
    mode: InstallMode,
    copy_ignore: CopyIgnore,
    backup: Path | None,
) -> None:
    """Finish copying before touching the old tool, then publish on the same filesystem."""
    target = Path(plan.target)
    phase = "staging"
    backup_moved = published = False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".tool-stage-", dir=target.parent) as directory:
            staged = Path(directory) / plan.name
            install_one(
                source=Path(plan.source),
                target=staged,
                name=plan.name,
                mode="symlink" if mode == "symlink" else "copy",
                kind="tool",
                copy_ignore=copy_ignore if mode != "symlink" else None,
            )
            if backup is not None:
                phase = "backup"
                shutil.move(str(target), str(backup))
                backup_moved = True
            phase = "publication"
            _publish_tool(staged, target)
            published = True
    except BaseException as error:
        # Also restore after a handled interrupt in the short backup/publication window.
        reason = str(error) or type(error).__name__
        if published:
            raise ToolInstallError(
                f"Tool is installed at {target}, but staging cleanup failed: {reason}. "
                f"Backup: {backup or '(none)'}"
            ) from error
        if backup_moved:
            assert backup is not None
            if target.exists() or target.is_symlink():
                raise ToolInstallError(
                    f"{reason}; existing destination {target} was not overwritten. "
                    f"Preserved backup: {backup}. Inspect the destination before manual restore."
                ) from error
            try:
                shutil.move(str(backup), str(target))
            except BaseException as restore_error:
                restore_reason = str(restore_error) or type(restore_error).__name__
                raise ToolInstallError(
                    f"{reason}; Restore failed: {restore_reason}. "
                    f"Preserved backup: {backup}. Restore it to {target}."
                ) from error
            raise ToolInstallError(
                f"{reason}; the old tool was restored at {target} from {backup} "
                "(backup moved back)."
            ) from error
        if phase == "backup":
            raise ToolInstallError(
                f"Backup move failed: {reason}. Inspect {target} and {backup}; "
                "no publication attempted."
            ) from error
        detail = "the old tool is unchanged" if plan.action == "change" else "no tool published"
        raise ToolInstallError(f"{reason}; {detail} at {target}") from error


def _package_path(source: Path, entry: object) -> Path:
    if not isinstance(entry, str) or not entry or any(c in entry for c in "*?[]{}!"):
        raise ToolInstallError(f"Package paths must be literal file/directory paths: {entry!r}")
    relative = Path(entry)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not (source / relative).resolve().is_relative_to(source.resolve())
    ):
        raise ToolInstallError(f"Invalid package path: {entry}")
    return relative


def _deno_files(source: Path) -> tuple[Path, ...] | None:
    """Read literal Deno entry/include metadata for local copies, without invoking Deno."""

    manifest = source / "deno.json"
    if not manifest.is_file():
        if (source / "deno.jsonc").is_file():
            raise ToolInstallError(f"Source installation requires strict-JSON deno.json: {source}")
        return None
    try:
        config = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ToolInstallError(f"Invalid strict-JSON deno.json in {source}: {error.msg}") from error
    if not isinstance(config, dict):
        raise ToolInstallError(f"deno.json must contain an object: {source}")

    entry = None
    if "exports" in config:
        export = config["exports"]
        if not isinstance(export, str) or not export.startswith("./"):
            raise ToolInstallError(
                f"Invalid package path for exports: expected a single './' path in {source}"
            )
        entry = _package_path(source, export)
        if not (source / entry).is_file():
            raise ToolInstallError(
                f"Missing required tool artifact: {source / entry}. "
                f"Build the source tool in {source} first, then retry installation."
            )

    publish = config.get("publish", {})
    if not isinstance(publish, dict):
        raise ToolInstallError(f"deno.json publish must be an object: {source}")
    if publish.get("exclude", []) != []:
        raise ToolInstallError(f"Source installation does not support publish.exclude: {source}")
    if "include" not in publish:
        return None
    entries = publish["include"]
    if not isinstance(entries, list):
        raise ToolInstallError(f"publish.include must be an array of literal paths: {source}")
    included = (Path("deno.json"), *(_package_path(source, item) for item in entries))
    if entry is not None and not any(entry.is_relative_to(path) for path in included):
        raise ToolInstallError(
            f"Exports entry is not included in publish.include: {source / entry}"
        )
    return included


def tool_copy_ignore(source: Path) -> CopyIgnore:
    """Exclude Python bytecode; apply Deno selection or legacy ignore declarations."""

    included = _deno_files(source)
    patterns = DEFAULT_TOOL_COPY_IGNORES
    declaration = source / TOOL_COPY_IGNORE_FILE
    if included is None and declaration.is_file():
        patterns += tuple(
            line
            for raw_line in declaration.read_text(encoding="utf-8").splitlines()
            if (line := raw_line.strip()) and not line.startswith("#")
        )
    ignore_patterns = shutil.ignore_patterns(*patterns)

    def ignore(directory: str, names: list[str]) -> list[str]:
        ignored = set(ignore_patterns(directory, names))
        relative = Path(directory).relative_to(source)
        return [
            name
            for name in names
            if name in ignored
            or (
                included is not None
                and not any(
                    (relative / name).is_relative_to(path) or path.is_relative_to(relative / name)
                    for path in included
                )
            )
        ]

    return ignore


def normalize_tool_names(tool_names: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    return normalize_names(tool_names)
