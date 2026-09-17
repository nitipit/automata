"""Install standalone Pi files or native index.ts extension bundles."""

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

    # Resolve the complete selection before mutating any destination.
    sources = {name: extension_source(source_path, name) for name in selected_names}
    target_path = Path(target_root).expanduser()
    for name, source in sources.items():
        alternate = target_path / (f"{name}.ts" if source.is_dir() else name)
        if alternate.exists() or alternate.is_symlink():
            raise PiExtensionInstallError(
                f"Conflicting Pi extension layout exists: {alternate}; review migration first"
            )

    return tuple(
        install_pi_extension(
            source=sources[name],
            target=target_path / sources[name].name,
            name=name,
            mode=mode,
        )
        for name in selected_names
    )


def extension_source(source_root: Path, name: str) -> Path:
    file = source_root / f"{name}.ts"
    directory = source_root / name
    is_bundle = directory.is_dir() and (directory / "index.ts").is_file()
    if file.is_file() and is_bundle:
        raise PiExtensionInstallError(f"Ambiguous Pi extension file and bundle: {name}")
    if is_bundle:
        return directory
    if file.is_file():
        return file
    raise PiExtensionInstallError(f"Source Pi extension does not exist: {source_root / name}")


def list_pi_extensions(source_root: Path) -> tuple[str, ...]:
    names = {path.stem for path in source_root.glob("*.ts") if path.is_file()}
    names.update(
        path.name
        for path in source_root.iterdir()
        if path.is_dir() and (path / "index.ts").is_file()
    )
    return tuple(sorted(names))


def install_pi_extension(
    *,
    source: Path,
    target: Path,
    name: str,
    mode: InstallMode,
) -> PiExtensionInstallResult:
    if not source.is_file() and not (source.is_dir() and (source / "index.ts").is_file()):
        raise PiExtensionInstallError(f"Source Pi extension does not exist: {source}")

    if target.exists() or target.is_symlink():
        if mode != "replace":
            raise PiExtensionInstallError(f"Destination Pi extension already exists: {target}")
        remove_existing(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == "symlink":
        target.symlink_to(source.resolve())
    elif source.is_dir():
        shutil.copytree(source, target)
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
