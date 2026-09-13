"""Install bundled or local Pi extension files into a Pi extension root."""

from __future__ import annotations

import shutil
from importlib.resources import files
from pathlib import Path

from automata.install.directory import (
    DirectoryInstallError,
    DirectoryInstallResult,
    InstallMode,
    normalize_names,
    remove_existing,
    resolve_source_root,
    validate_directory_name,
)

PiExtensionInstallError = DirectoryInstallError
PiExtensionInstallResult = DirectoryInstallResult


def bundled_pi_extension_root() -> Path:
    return Path(str(files("automata").joinpath("extensions")))


def install_pi_extensions(
    *,
    target_root: str | Path,
    source_root: str | Path | None = None,
    extension_names: tuple[str, ...] | list[str] = (),
    mode: InstallMode = "copy",
) -> tuple[PiExtensionInstallResult, ...]:
    source_path = resolve_source_root(
        source_root or bundled_pi_extension_root(), kind="Pi extension"
    )
    selected_names = tuple(extension_names) or list_pi_extensions(source_path)

    if not selected_names:
        raise PiExtensionInstallError(f"No Pi extension files found under: {source_path}")

    for name in selected_names:
        validate_directory_name(name, kind="Pi extension")

    return tuple(
        install_pi_extension(
            source=source_path / f"{name}.ts",
            target=Path(target_root).expanduser() / f"{name}.ts",
            name=name,
            mode=mode,
        )
        for name in selected_names
    )


def list_pi_extensions(source_root: Path) -> tuple[str, ...]:
    return tuple(sorted(path.stem for path in source_root.glob("*.ts") if path.is_file()))


def install_pi_extension(
    *,
    source: Path,
    target: Path,
    name: str,
    mode: InstallMode,
) -> PiExtensionInstallResult:
    if not source.is_file():
        raise PiExtensionInstallError(f"Source Pi extension file does not exist: {source}")

    if target.exists() or target.is_symlink():
        if mode != "replace":
            raise PiExtensionInstallError(f"Destination Pi extension already exists: {target}")
        remove_existing(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == "symlink":
        target.symlink_to(source.resolve())
    else:
        shutil.copy2(source, target)

    return PiExtensionInstallResult(
        source=str(source),
        target=str(target),
        name=name,
        mode=mode,
    )


def normalize_pi_extension_names(
    extension_names: tuple[str, ...] | list[str] | None,
) -> tuple[str, ...]:
    return normalize_names(extension_names)
