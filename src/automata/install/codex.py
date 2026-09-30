"""Install Codex helpers directly into the selected root, without activation."""

from __future__ import annotations

import json
import shlex
import shutil
import tempfile
from importlib.resources import files
from pathlib import Path

from automata.install.directory import (
    DirectoryInstallError,
    DirectoryInstallResult,
    InstallMode,
)

ASSET_FILES = (
    "token_records.py",
    "token_awareness.py",
    "context_records.py",
    "context_awareness.py",
    "skill_records.py",
    "skill_activity.py",
    "session_native.py",
    "session_store.py",
    "session_receipts.py",
    "session_recovery.py",
    "session_operations.py",
    "session_copy.py",
    "session_management.py",
    "README.md",
    "setup.md",
)
MANAGED_FILES = (*ASSET_FILES, "hooks.json")


def install_codex(
    *, target_root: str | Path, state_root: str | Path, mode: InstallMode = "copy"
) -> DirectoryInstallResult:
    """Install only managed filenames; never remove the root or unrelated contents.

    Copy/symlink require absent managed paths, not an absent root. Replace swaps
    files or symlinks without following them; real directories are never replaced.
    Preflight and staging precede publication, which is atomic per file, not per
    bundle. A publication failure may leave a partial update. No legacy directory
    migration, backup, state creation or Codex configuration change is implicit.
    """
    if mode not in ("copy", "replace", "symlink"):
        raise DirectoryInstallError("Unsupported Codex install mode")
    source = Path(str(files("automata").joinpath("runtimes", "codex")))
    target = Path(target_root).expanduser().absolute()
    state = Path(state_root).expanduser().absolute()
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise DirectoryInstallError(f"Codex target must be a non-symlink directory: {target}")
    if state.resolve().is_relative_to(target.resolve()):
        raise DirectoryInstallError("Codex token state must be outside the installed bundle")
    if target.resolve().is_relative_to(source.resolve()) or source.resolve().is_relative_to(
        target.resolve()
    ):
        raise DirectoryInstallError("Codex target must not overlap bundled source")
    for name in ASSET_FILES:
        if not (source / name).is_file():
            raise DirectoryInstallError(f"Missing Codex source asset: {source / name}")
    for name in MANAGED_FILES:
        destination = target / name
        if destination.exists() or destination.is_symlink():
            if mode != "replace":
                raise DirectoryInstallError(f"Destination Codex file already exists: {destination}")
            if not destination.is_symlink() and not destination.is_file():
                raise DirectoryInstallError(f"Codex destination is not a file: {destination}")

    command = shlex.join(
        ["python3", str(target / "token_awareness.py"), "hook", "--state-root", str(state)]
    )
    activity_command = shlex.join(
        ["python3", str(target / "skill_activity.py"), "hook", "--state-root", str(state)]
    )
    hooks = {
        event: [
            {
                "hooks": [
                    {"type": "command", "command": command, "timeout": 10},
                    {"type": "command", "command": activity_command, "timeout": 10},
                ]
            }
        ]
        for event in ("SessionStart", "UserPromptSubmit", "PreCompact", "PostCompact")
    }
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix=".automata-codex-", dir=target) as temporary:
        staging = Path(temporary)
        for name in ASSET_FILES:
            if mode == "symlink":
                (staging / name).symlink_to((source / name).resolve())
            else:
                shutil.copy2(source / name, staging / name)
        fragment = staging / "hooks.json"
        fragment.write_text(json.dumps({"hooks": hooks}, indent=2) + "\n")
        fragment.chmod(0o600)
        for name in MANAGED_FILES:
            (staging / name).replace(target / name)
    return DirectoryInstallResult(
        source=str(source), target=str(target), name="codex", mode=mode
    )
