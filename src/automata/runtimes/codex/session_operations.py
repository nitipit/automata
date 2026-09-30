"""Receipt-selected linked forks and recoverable standalone-session trash/restore."""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import uuid
from pathlib import Path

from session_native import NativeClient
from session_receipts import claim, locked
from session_recovery import load_recovery, prefix_digest, signature, stage, sync_directory
from session_store import (
    absolute,
    database,
    effect_closure,
    ensure_recoverable_subset,
    identify,
    inventory,
    recheck,
    rollout_path,
)
from token_awareness import atomic_write
from token_records import CoverageError, session_id


def caller(current, outside_session, inactive_owned):
    actual = os.environ.get("CODEX_THREAD_ID")
    if actual:
        actual = session_id(actual)
        if outside_session or (current is not None and session_id(current) != actual):
            raise CoverageError("caller identity conflicts with native current thread")
        current = actual
    elif current is not None:
        current = session_id(current)
    elif not outside_session:
        raise CoverageError("supply --current-thread or attest --outside-session")
    if not inactive_owned:
        raise CoverageError("explicit inactive ownership attestation required")
    return current


def native(binary, root, state_root, selected, extra_cwds=()):
    row = selected["row"]
    return NativeClient(
        binary,
        root,
        Path(state_root) / "native",
        [row["cwd"], *extra_cwds],
        provider=row["model_provider"],
        model=row["model"] or "gpt-5.1-codex",
    )


def absent(root, identity, path):
    with database(root) as db:
        exists = db.execute("SELECT 1 FROM threads WHERE id=?", [identity]).fetchone()
    return not exists and not path.exists()


def fork(state_root, store_root, binary, receipt, ids, target_cwd, current):
    target = absolute(target_cwd)
    if not target.is_dir():
        raise CoverageError("destination must be an existing authorized directory")
    with locked(state_root, store_root) as (root, receipt_path):
        if target.is_relative_to(root) or root.is_relative_to(target):
            raise CoverageError("destination cannot contain or be within the store")
        selected = claim(receipt_path, root, "fork", receipt, ids, current)
        if any(str(target) == c["row"]["cwd"] for c in selected):
            raise CoverageError("choose a different destination cwd")
        results = []
        for index, candidate in enumerate(selected):
            new_id = None
            try:
                recheck(root, candidate)
                with native(binary, root, state_root, candidate, [str(target)]) as client:
                    response = client.request(
                        "thread/fork",
                        {
                            "threadId": candidate["id"],
                            "cwd": str(target),
                            "runtimeWorkspaceRoots": [str(target)],
                            "excludeTurns": True,
                            "deferGoalContinuation": True,
                            "modelProvider": candidate["row"]["model_provider"],
                        },
                    )
                    thread = response["thread"]
                    new_id = session_id(thread["id"])
                    if (
                        new_id == candidate["id"]
                        or thread["cwd"] != str(target)
                        or thread["forkedFromId"] != candidate["id"]
                    ):
                        raise CoverageError("native fork identity/provenance not verified")
                rows, _ = inventory(root, str(target))
                copied = next(row for row in rows if row["id"] == new_id)
                verified = identify(root, copied)
                if verified["forkedFromId"] != candidate["id"]:
                    raise CoverageError("saved fork provenance unavailable")
                recheck(root, candidate)
                results.append(
                    {
                        "sourceId": candidate["id"],
                        "status": "forked",
                        "id": new_id,
                        "cwd": str(target),
                        "independentCopy": False,
                    }
                )
            except (
                CoverageError,
                OSError,
                ValueError,
                KeyError,
                TypeError,
                StopIteration,
                sqlite3.Error,
                subprocess.SubprocessError,
            ):
                results.append(
                    {
                        "sourceId": candidate["id"],
                        "status": "failed",
                        "id": new_id,
                        "destinationMayContainFork": True,
                        "automaticRetrySafe": False,
                    }
                )
                results += [
                    {"sourceId": c["id"], "status": "not_attempted"} for c in selected[index + 1 :]
                ]
                break
        return {
            "runtime": "codex",
            "action": "linked-fork",
            "results": results,
            "status": "forked" if all(r["status"] == "forked" for r in results) else "incomplete",
            "warning": "Same-store native linked fork, not independent copy. Source and historical "
            "paths remain. Parent history remains a dependency; no project files copied.",
        }


def trash(state_root, store_root, binary, receipt, ids, xdg_home, current):
    with locked(state_root, store_root) as (root, receipt_path):
        selected = claim(receipt_path, root, "trash", receipt, ids, current)
        effect_closure(root, ids)
        for candidate in selected:
            ensure_recoverable_subset(root, candidate)
        # Native read hydrates only the selected histories; it does not resume them.
        signatures = {}
        for candidate in selected:
            with native(binary, root, state_root, candidate) as client:
                signatures[candidate["id"]] = signature(client, candidate["id"])
        recovery = str(uuid.uuid4())
        try:
            recovery_path, journal = stage(
                Path(state_root), root, selected, signatures, xdg_home, recovery
            )
        except (
            CoverageError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            sqlite3.Error,
            subprocess.SubprocessError,
        ):
            return {
                "runtime": "codex",
                "status": "not-removed",
                "recoveryId": recovery,
                "packageMayRemain": True,
                "nativeDeleteAttempted": False,
                "error": "Recovery package/trash verification failed; no deletion fallback.",
            }
        results = []
        for index, candidate in enumerate(selected):
            attempted = False
            try:
                effect_closure(root, ids[index:])
                recheck(root, candidate)
                ensure_recoverable_subset(root, candidate)
                journal["entries"][index]["status"] = "native-removal-requested"
                atomic_write(recovery_path, journal)
                with native(binary, root, state_root, candidate) as client:
                    attempted = True
                    client.request("thread/delete", {"threadId": candidate["id"]})
                if not absent(root, candidate["id"], Path(candidate["path"])):
                    raise CoverageError("native removal not verified")
                journal["entries"][index]["status"] = "trashed"
                atomic_write(recovery_path, journal)
                results.append({"id": candidate["id"], "status": "trashed"})
            except (
                CoverageError,
                OSError,
                ValueError,
                KeyError,
                TypeError,
                sqlite3.Error,
                subprocess.SubprocessError,
            ):
                results.append(
                    {
                        "id": candidate["id"],
                        "status": "failed",
                        "nativeRemovalMayHaveOccurred": attempted,
                    }
                )
                results += [
                    {"id": c["id"], "status": "not_attempted"} for c in selected[index + 1 :]
                ]
                break
        journal["phase"] = "native-removal-finished"
        atomic_write(recovery_path, journal)
        return {
            "runtime": "codex",
            "action": "recoverable-trash",
            "recoveryId": recovery,
            "results": results,
            "status": "trashed" if all(r["status"] == "trashed" for r in results) else "incomplete",
            "warning": "Verified freedesktop recovery bundle precedes native permanent removal. "
            "Use explicit restore; no automatic retry or package deletion.",
        }


def restore(state_root, store_root, binary, recovery, ids, current):
    with locked(state_root, store_root) as (root, _receipt_path):
        journal_path, journal, package = load_recovery(state_root, root, recovery)
        entries = {entry["candidate"]["id"]: entry for entry in journal["entries"]}
        ids = [session_id(value) for value in ids]
        if not ids or len(ids) != len(set(ids)) or not set(ids) <= entries.keys() or current in ids:
            raise CoverageError("select distinct authorized recovery IDs, excluding current thread")
        for identity in ids:
            entry = entries[identity]
            candidate = entry["candidate"]
            path = rollout_path(root, identity, candidate["path"])
            if candidate["historyParent"]:
                raise CoverageError("linked recovery unsupported")
            if not absent(root, identity, path):
                raise CoverageError(
                    "restore collision; existing native identity/file never overwritten"
                )
        results = []
        for index, identity in enumerate(ids):
            entry, copied = entries[identity], False
            candidate = entry["candidate"]
            try:
                path = rollout_path(root, identity, candidate["path"])
                if not absent(root, identity, path):
                    raise CoverageError("restore collision after preflight")
                entry["status"] = "restore-started"
                atomic_write(journal_path, journal)
                path.parent.mkdir(parents=True, exist_ok=True)
                # O_EXCL semantics: never overwrite a concurrently created session.
                descriptor = os.open(
                    path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                )
                with (
                    os.fdopen(descriptor, "wb") as destination,
                    (package / entry["filename"]).open("rb") as source,
                ):
                    copied = True
                    shutil.copyfileobj(source, destination)
                    destination.flush()
                    os.fsync(destination.fileno())
                sync_directory(path.parent)
                with native(binary, root, state_root, candidate) as client:
                    thread = client.request(
                        "thread/resume",
                        {
                            "threadId": identity,
                            "path": str(path),
                            "excludeTurns": True,
                            "modelProvider": candidate["row"]["model_provider"],
                        },
                    )["thread"]
                    if thread["id"] != identity or thread["cwd"] != candidate["row"]["cwd"]:
                        raise CoverageError("restored native identity mismatch")
                    if candidate["row"]["name"] is not None:
                        client.request(
                            "thread/name/set",
                            {"threadId": identity, "name": candidate["row"]["name"]},
                        )
                    if signature(client, identity) != entry["signature"]:
                        raise CoverageError("restored native history not verified")
                if prefix_digest(path, candidate["size"]) != entry["sha256"]:
                    raise CoverageError("restored original rollout prefix changed")
                entry["status"] = "restored"
                atomic_write(journal_path, journal)
                results.append({"id": identity, "status": "restored"})
            except (
                CoverageError,
                OSError,
                ValueError,
                KeyError,
                TypeError,
                sqlite3.Error,
                subprocess.SubprocessError,
            ):
                results.append(
                    {"id": identity, "status": "failed", "partialRestoreMayExist": copied}
                )
                results += [
                    {"id": remaining, "status": "not_attempted"} for remaining in ids[index + 1 :]
                ]
                break
        return {
            "runtime": "codex",
            "action": "restore",
            "recoveryId": recovery,
            "results": results,
            "status": "restored"
            if all(r["status"] == "restored" for r in results)
            else "incomplete",
            "warning": "Recovery bundle retained. Native resume rebuilt projections without "
            "a model turn; history paths unchanged. Operational logs/caches are not restored.",
        }
