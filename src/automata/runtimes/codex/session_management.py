#!/usr/bin/env python3
"""Explicit-store Codex session metadata, copy/fork and recoverable trash/restore.

No global default, history discovery, chat launcher or model-turn RPC. Receipts
select exact identities; operator authorization/inactivity remain required.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
from pathlib import Path

from session_copy import copy_sessions
from session_operations import caller, fork, restore, trash
from session_receipts import list_sessions
from token_records import CoverageError, session_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["list", "copy", "fork", "trash", "restore"])
    parser.add_argument("--store-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--cwd")
    parser.add_argument("--all-projects", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--cursor")
    parser.add_argument("--receipt")
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--target-cwd", type=Path)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--current-thread")
    parser.add_argument("--outside-session", action="store_true")
    parser.add_argument("--inactive-owned", action="store_true")
    parser.add_argument("--xdg-data-home", type=Path)
    parser.add_argument("--recovery-id")
    args = parser.parse_args()
    try:
        for path in (args.store_root, args.state_root):
            if not path.is_absolute() or path == Path("/"):
                raise CoverageError("explicit absolute non-root storage directories required")
        if args.action == "list":
            if any((args.receipt, args.ids, args.target_cwd, args.recovery_id, args.xdg_data_home)):
                raise CoverageError("listing cannot carry mutation arguments")
            current = args.current_thread or os.environ.get("CODEX_THREAD_ID")
            if current:
                current = session_id(current)
            if (
                os.environ.get("CODEX_THREAD_ID")
                and args.current_thread
                and current != session_id(os.environ["CODEX_THREAD_ID"])
            ):
                raise CoverageError("current thread identity conflict")
            result = list_sessions(
                args.state_root,
                args.store_root,
                args.cwd,
                args.all_projects,
                args.limit,
                args.cursor,
                current,
            )
        else:
            if args.cwd or args.all_projects or args.cursor:
                raise CoverageError("mutation uses receipt scope, not discovery filters")
            if args.binary is None or not args.binary.is_absolute() or not args.binary.is_file():
                raise CoverageError("explicit installed native Codex binary required")
            if not args.ids:
                raise CoverageError("exact selected --ids required")
            current = caller(args.current_thread, args.outside_session, args.inactive_owned)
            if args.action in ("copy", "fork"):
                if args.target_cwd is None or args.xdg_data_home or args.recovery_id:
                    raise CoverageError("copy/fork requires only its receipt and destination")
                operation = copy_sessions if args.action == "copy" else fork
                result = operation(
                    args.state_root,
                    args.store_root,
                    args.binary,
                    args.receipt,
                    args.ids,
                    args.target_cwd,
                    current,
                )
            elif args.action == "trash":
                if args.xdg_data_home is None or args.target_cwd or args.recovery_id:
                    raise CoverageError("trash requires receipt and explicit XDG data home")
                result = trash(
                    args.state_root,
                    args.store_root,
                    args.binary,
                    args.receipt,
                    args.ids,
                    args.xdg_data_home,
                    current,
                )
            else:
                if (
                    args.recovery_id is None
                    or args.receipt
                    or args.target_cwd
                    or args.xdg_data_home
                ):
                    raise CoverageError("restore uses exact recovery ID and selected IDs")
                result = restore(
                    args.state_root,
                    args.store_root,
                    args.binary,
                    args.recovery_id,
                    args.ids,
                    current,
                )
        print(json.dumps(result))
        return 1 if result.get("status") in ("incomplete", "not-removed") else 0
    except (
        CoverageError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        sqlite3.Error,
        subprocess.SubprocessError,
    ) as error:
        reason = str(error) if isinstance(error, CoverageError) else "session operation unavailable"
        print(
            json.dumps(
                {
                    "runtime": "codex",
                    "status": "error",
                    "error": reason,
                    "warning": "No automatic retry or permanent-delete fallback.",
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
