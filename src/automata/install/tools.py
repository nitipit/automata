"""Install bundled or local tools into an agent tool root."""

from __future__ import annotations

import json
import shutil
from importlib.resources import files
from pathlib import Path

from automata.install.directory import (
    CopyIgnore,
    DirectoryInstallError,
    DirectoryInstallResult,
    InstallMode,
    install_directories,
    list_directories,
    normalize_names,
    resolve_source_root,
    validate_directory_name,
)

ToolInstallError = DirectoryInstallError
ToolInstallResult = DirectoryInstallResult
TOOL_COPY_IGNORE_FILE = ".automataignore"
DEFAULT_TOOL_COPY_IGNORES = ("__pycache__", "*.pyc", "*.pyo")


def bundled_tool_root() -> Path:
    return Path(str(files("automata").joinpath("tools")))


def install_tools(
    *,
    target_root: str | Path,
    source_root: str | Path | None = None,
    tool_names: tuple[str, ...] | list[str] = (),
    mode: InstallMode = "copy",
) -> tuple[ToolInstallResult, ...]:
    source_path = resolve_source_root(source_root or bundled_tool_root(), kind="tool")
    selected = tuple(tool_names) or list_directories(source_path)
    # Preflight all manifests and entry files before any destination is replaced.
    copy_ignores = {}
    for name in selected:
        validate_directory_name(name, kind="tool")
        copy_ignores[name] = tool_copy_ignore(source_path / name)

    return install_directories(
        source_root=source_path,
        target_root=target_root,
        names=selected,
        mode=mode,
        kind="tool",
        copy_ignore_factory=lambda source: copy_ignores[source.name],
    )


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
