"""Install pinned awareness hooks/session controls without activating trust/config."""

from __future__ import annotations

import json
import shlex
import shutil
from importlib.resources import files
from pathlib import Path

from automata.install.directory import (
    DirectoryInstallError,
    DirectoryInstallResult,
    InstallMode,
    remove_existing,
)


def install_codex(
    *, target_root: str | Path, state_root: str | Path, mode: InstallMode = "copy"
) -> DirectoryInstallResult:
    """Place reviewed files + hooks fragment; never edit Codex's configuration.

    State is external to the replaceable bundle. Explicit activation authorizes
    session-local transcript reading; native hook trust remains a separate step.
    """
    if mode not in ("copy", "replace", "symlink"):
        raise DirectoryInstallError("Unsupported Codex install mode")
    source = Path(str(files("automata").joinpath("runtimes", "codex")))
    target = Path(target_root).expanduser().absolute() / "token-awareness"
    state = Path(state_root).expanduser().absolute()
    if state.resolve().is_relative_to(target.resolve()):
        raise DirectoryInstallError("Codex token state must be outside the installed bundle")
    if target.exists() or target.is_symlink():
        if mode != "replace":
            raise DirectoryInstallError(f"Destination Codex integration already exists: {target}")
        remove_existing(target)
    target.mkdir(parents=True)
    for name in (
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
    ):
        if mode == "symlink":
            (target / name).symlink_to((source / name).resolve())
        else:
            shutil.copy2(source / name, target / name)
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
    (target / "hooks.json").write_text(json.dumps({"hooks": hooks}, indent=2) + "\n")
    return DirectoryInstallResult(
        source=str(source), target=str(target), name="token-awareness", mode=mode
    )
