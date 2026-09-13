"""Build self-contained Agent Plugin packages from Automata assets."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from automata.install.directory import CopyIgnore, DirectoryInstallError, validate_directory_name
from automata.install.skills import bundled_skill_root, find_skill_dir
from automata.install.tools import bundled_tool_root, tool_copy_ignore
from automata.plugin.profiles import PluginProfile, get_profile

PLUGIN_SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
AUTOMATA_EXTENSION_NAMESPACE = "me.umlab.automata"
_PLUGIN_NAME_PATTERN = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")


class PluginExportError(RuntimeError):
    """Raised when a plugin package cannot be exported safely."""


@dataclass(frozen=True)
class PluginExportResult:
    """Summary of a completed plugin export."""

    output: str
    name: str
    version: str
    profile: str | None
    skills: tuple[str, ...]
    tools: tuple[str, ...]


def export_plugin(
    *,
    name: str,
    output: str | Path,
    profile: str | None = None,
    skill_names: Sequence[str] = (),
    tool_names: Sequence[str] = (),
    version: str = "0.1.0",
    description: str | None = None,
    replace: bool = False,
    skill_source_root: str | Path | None = None,
    tool_source_root: str | Path | None = None,
) -> PluginExportResult:
    """Export selected Automata skills and tools as an Agent Plugin package."""

    validate_plugin_name(name)
    if not version.strip():
        raise PluginExportError("Plugin version must not be empty")

    selected_profile: PluginProfile | None = None
    if profile is not None:
        try:
            selected_profile = get_profile(profile)
        except ValueError as exc:
            raise PluginExportError(str(exc)) from exc

    selected_skills = merge_names(
        selected_profile.skills if selected_profile else (),
        skill_names,
    )
    selected_tools = merge_names(
        selected_profile.tools if selected_profile else (),
        tool_names,
    )
    if not selected_skills and not selected_tools:
        raise PluginExportError("Select a profile, skill, or tool before exporting")

    skill_root = Path(skill_source_root) if skill_source_root else bundled_skill_root()
    tool_root = Path(tool_source_root) if tool_source_root else bundled_tool_root()
    validate_selected_assets(skill_root, selected_skills, kind="skill")
    validate_selected_assets(tool_root, selected_tools, kind="tool")

    output_path = Path(output).expanduser()
    if output_path.exists() and not replace:
        raise PluginExportError(
            f"Output already exists: {output_path}. Use --replace to overwrite it."
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    staging_path = Path(tempfile.mkdtemp(prefix=f".{output_path.name}.", dir=output_path.parent))
    try:
        if selected_skills:
            copy_selected_skill_assets(
                source_root=skill_root,
                target_root=staging_path / "skills",
                names=selected_skills,
            )
        if selected_tools:
            copy_selected_assets(
                source_root=tool_root,
                target_root=staging_path / AUTOMATA_EXTENSION_NAMESPACE / "tools",
                names=selected_tools,
            )

        manifest = build_manifest(
            name=name,
            version=version,
            description=description or (selected_profile.description if selected_profile else None),
            tools=selected_tools,
        )
        (staging_path / "plugin.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        if output_path.exists() or output_path.is_symlink():
            remove_path(output_path)
        staging_path.replace(output_path)
    except Exception:
        remove_path(staging_path)
        raise

    return PluginExportResult(
        output=str(output_path),
        name=name,
        version=version,
        profile=profile,
        skills=selected_skills,
        tools=selected_tools,
    )


def copy_selected_skill_assets(
    *,
    source_root: Path,
    target_root: Path,
    names: Sequence[str],
) -> None:
    """Copy selected skills from grouped sources into a flat package directory."""

    target_root.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")
    for name in names:
        shutil.copytree(find_skill_dir(source_root, name), target_root / name, ignore=ignore)


def copy_selected_assets(
    *,
    source_root: Path,
    target_root: Path,
    names: Sequence[str],
) -> None:
    """Copy selected direct-child package directories without runtime caches."""

    target_root.mkdir(parents=True, exist_ok=True)
    for name in names:
        source = source_root / name
        shutil.copytree(
            source,
            target_root / name,
            ignore=plugin_tool_copy_ignore(source),
        )


def plugin_tool_copy_ignore(source: Path) -> CopyIgnore:
    """Combine package-cache exclusions with a tool's declared exclusions."""

    cache_ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")
    declared_ignore = tool_copy_ignore(source)

    def ignore(path: str, entries: list[str]) -> set[str]:
        ignored = set(cache_ignore(path, entries))
        if declared_ignore:
            ignored.update(declared_ignore(path, entries))
        return ignored

    return ignore


def build_manifest(
    *,
    name: str,
    version: str,
    description: str | None,
    tools: Sequence[str],
) -> dict[str, object]:
    """Build the portable manifest and optional Automata extension metadata."""

    manifest: dict[str, object] = {
        "$schema": PLUGIN_SCHEMA_URL,
        "name": name,
        "version": version,
    }
    if description:
        manifest["description"] = description
    if tools:
        manifest["extensions"] = {
            AUTOMATA_EXTENSION_NAMESPACE: {
                "tools": list(tools),
                "toolRoot": f"{AUTOMATA_EXTENSION_NAMESPACE}/tools",
            }
        }
    return manifest


def merge_names(*groups: Sequence[str]) -> tuple[str, ...]:
    """Merge selections while preserving the first occurrence of each name."""

    merged: list[str] = []
    for group in groups:
        for name in group:
            if name and name not in merged:
                merged.append(name)
    return tuple(merged)


def validate_plugin_name(name: str) -> None:
    """Validate a plugin name using the Agent Plugins v1 constraints."""

    if not 1 <= len(name) <= 64 or not _PLUGIN_NAME_PATTERN.fullmatch(name):
        raise PluginExportError(
            "Plugin name must be 1-64 lowercase characters using letters, numbers, "
            "hyphens, and periods; it must start and end alphanumerically."
        )


def validate_selected_assets(source_root: Path, names: Sequence[str], *, kind: str) -> None:
    """Reject missing or malformed selected source directories before writing output."""

    if not names:
        return
    if not source_root.is_dir():
        raise PluginExportError(f"{kind.capitalize()} source root does not exist: {source_root}")

    for name in names:
        try:
            validate_directory_name(name, kind=kind)
        except DirectoryInstallError as exc:
            raise PluginExportError(str(exc)) from exc
        if kind == "skill":
            try:
                find_skill_dir(source_root, name)
            except DirectoryInstallError as exc:
                raise PluginExportError(str(exc)) from exc
            continue

        source = source_root / name
        if not source.is_dir():
            raise PluginExportError(f"Selected {kind} does not exist: {name}")


def remove_path(path: Path) -> None:
    """Remove a file, symlink, or directory when cleaning an export staging path."""

    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
