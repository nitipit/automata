"""Install selected child directories from one root into another."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlparse

InstallMode = Literal["copy", "replace", "symlink"]
CopyIgnore = Callable[[str, list[str]], Iterable[str]]
CopyIgnoreFactory = Callable[[Path], CopyIgnore | None]


class DirectoryInstallError(RuntimeError):
    """Raised when a directory install cannot proceed."""


@dataclass(frozen=True)
class DirectoryInstallResult:
    source: str
    target: str
    name: str
    mode: str


def install_directories(
    *,
    source_root: str | Path,
    target_root: str | Path,
    names: tuple[str, ...] | list[str] = (),
    mode: InstallMode = "copy",
    kind: str = "directory",
    copy_ignore_factory: CopyIgnoreFactory | None = None,
) -> tuple[DirectoryInstallResult, ...]:
    source_path = resolve_source_root(source_root, kind=kind)
    target_path = Path(target_root).expanduser()
    selected_names = tuple(names) or list_directories(source_path)

    if not selected_names:
        raise DirectoryInstallError(f"No {kind} directories found under: {source_path}")

    for name in selected_names:
        validate_directory_name(name, kind=kind)

    return tuple(
        install_one(
            source=source_path / name,
            target=target_path / name,
            name=name,
            mode=mode,
            kind=kind,
            copy_ignore=(
                copy_ignore_factory(source_path / name)
                if copy_ignore_factory and mode != "symlink"
                else None
            ),
        )
        for name in selected_names
    )


def install_one(
    *,
    source: Path,
    target: Path,
    name: str,
    mode: InstallMode,
    kind: str,
    copy_ignore: CopyIgnore | None = None,
) -> DirectoryInstallResult:
    if not source.is_dir():
        raise DirectoryInstallError(f"Source {kind} directory does not exist: {source}")

    if target.exists() or target.is_symlink():
        if mode != "replace":
            raise DirectoryInstallError(f"Destination {kind} already exists: {target}")
        remove_existing(target)

    target.parent.mkdir(parents=True, exist_ok=True)

    if mode == "symlink":
        target.symlink_to(source.resolve(), target_is_directory=True)
    else:
        shutil.copytree(source, target, ignore=copy_ignore)

    return DirectoryInstallResult(
        source=str(source),
        target=str(target),
        name=name,
        mode=mode,
    )


def list_directories(source_root: Path) -> tuple[str, ...]:
    return tuple(sorted(path.name for path in source_root.iterdir() if path.is_dir()))


def normalize_names(values: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    if not values:
        return ()

    names: list[str] = []
    for value in values:
        names.extend(name.strip() for name in value.split(",") if name.strip())
    return tuple(names)


def validate_directory_name(name: str, *, kind: str) -> None:
    path = Path(name)
    if path.name != name or name in {"", ".", ".."}:
        raise DirectoryInstallError(f"Invalid {kind} name: {name}")


def resolve_source_root(source_root: str | Path, *, kind: str = "directory") -> Path:
    source = str(source_root)
    parsed = urlparse(source)

    if parsed.scheme == "file":
        path = Path(unquote(parsed.path)).expanduser()
    elif parsed.scheme:
        raise DirectoryInstallError(
            f"Unsupported source scheme: {parsed.scheme}. "
            f"Fetch remote {kind} directories locally first."
        )
    else:
        path = Path(source).expanduser()

    if not path.is_dir():
        raise DirectoryInstallError(f"Source root must be a directory: {path}")
    return path


def remove_existing(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)
