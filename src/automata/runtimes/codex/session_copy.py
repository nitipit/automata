"""Independent copy by bounded destination materialization, never source rewriting.

Native 0.159.0 generates identity/cwd/provenance in a private copied-source store.
Only the destination's reference backing is replaced: native fresh header at
ordinal zero + exact original complete record tail. Source-free native hydration
and full canonical history digest verification are mandatory before publication.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from session_native import NativeClient
from session_operations import native
from session_receipts import claim, locked
from session_recovery import signature, sync_directory
from session_store import absolute, ensure_recoverable_subset, recheck, rollout_path
from token_awareness import atomic_write
from token_records import CoverageError, scan, session_id


def copy_sessions(state_root, store_root, binary, receipt, ids, target_cwd, current):
    target = absolute(target_cwd)
    if not target.is_dir():
        raise CoverageError("destination must be an existing authorized directory")
    with locked(state_root, store_root) as (root, receipt_path):
        if target.is_relative_to(root) or root.is_relative_to(target):
            raise CoverageError("destination cannot contain or be within native store")
        selected = claim(receipt_path, root, "copy", receipt, ids, current)
        for candidate in selected:
            if candidate["historyParent"] or str(target) == candidate["row"]["cwd"]:
                raise CoverageError(
                    "copy requires materialized source and different destination cwd"
                )
            ensure_recoverable_subset(root, candidate)
        results = []
        for index, candidate in enumerate(selected):
            new_id, published = None, False
            try:
                recheck(root, candidate)
                raw = Path(candidate["path"]).read_bytes()
                first, tail = raw.split(b"\n", 1)
                source_meta = json.loads(first)
                if source_meta["ordinal"] != 0 or not raw.endswith(b"\n"):
                    raise CoverageError("copy requires complete standalone ordinal-zero rollout")
                # Validate every record before copying, not just the first header.
                scan(Path(candidate["path"]), source_meta["payload"]["session_id"])
                with native(binary, root, state_root, candidate) as client:
                    expected = signature(client, candidate["id"])
                recheck(root, candidate)
                scratch = Path(state_root) / "copy-work"
                scratch.mkdir(exist_ok=True, mode=0o700)
                with tempfile.TemporaryDirectory(prefix="copy-", dir=scratch) as directory:
                    private = Path(directory)
                    imported = private / "import"
                    snapshot = imported / Path(candidate["path"]).relative_to(root)
                    snapshot.parent.mkdir(parents=True)
                    snapshot.write_bytes(raw)
                    params = {
                        "provider": candidate["row"]["model_provider"],
                        "model": candidate["row"]["model"] or "gpt-5.1-codex",
                    }
                    cwds = [candidate["row"]["cwd"], str(target)]
                    with NativeClient(
                        binary, imported, private / "native", cwds, **params
                    ) as client:
                        client.request(
                            "thread/resume",
                            {
                                "threadId": candidate["id"],
                                "path": str(snapshot),
                                "excludeTurns": True,
                                "modelProvider": candidate["row"]["model_provider"],
                            },
                        )
                        child = client.request(
                            "thread/fork",
                            {
                                "threadId": candidate["id"],
                                "cwd": str(target),
                                "runtimeWorkspaceRoots": [str(target)],
                                "excludeTurns": True,
                                "deferGoalContinuation": True,
                                "modelProvider": candidate["row"]["model_provider"],
                            },
                        )["thread"]
                    new_id = session_id(child["id"])
                    if new_id == candidate["id"] or child["forkedFromId"] != candidate["id"]:
                        raise CoverageError("native fresh identity/provenance unavailable")
                    generated = rollout_path(imported, new_id, child["path"])
                    header = json.loads(generated.open().readline())
                    payload = header["payload"]
                    if (
                        payload["id"] != new_id
                        or payload["cwd"] != str(target)
                        or payload["history_mode"] != "paginated"
                        or payload["forked_from_id"] != candidate["id"]
                    ):
                        raise CoverageError("unsupported native destination header")
                    payload.pop("history_base", None)
                    payload.pop("forked_from_ordinal_exclusive", None)
                    header["ordinal"] = 0
                    materialized = json.dumps(header, separators=(",", ":")).encode() + b"\n" + tail
                    validation = private / "validation"
                    relative = generated.relative_to(imported)
                    only_child = validation / relative
                    only_child.parent.mkdir(parents=True)
                    only_child.write_bytes(materialized)
                    with NativeClient(
                        binary, validation, private / "native", cwds, **params
                    ) as client:
                        client.request(
                            "thread/resume",
                            {
                                "threadId": new_id,
                                "path": str(only_child),
                                "excludeTurns": True,
                                "cwd": str(target),
                                "runtimeWorkspaceRoots": [str(target)],
                                "modelProvider": candidate["row"]["model_provider"],
                            },
                        )
                        if signature(client, new_id) != expected:
                            raise CoverageError("source-free copied history digest mismatch")
                    recheck(root, candidate)
                    destination = rollout_path(root, new_id, str(root / relative))
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    descriptor = os.open(
                        destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                    )
                    with os.fdopen(descriptor, "wb") as stream:
                        published = True
                        stream.write(materialized)
                        stream.flush()
                        os.fsync(stream.fileno())
                    sync_directory(destination.parent)
                    with native(binary, root, state_root, candidate, [str(target)]) as client:
                        copied = client.request(
                            "thread/resume",
                            {
                                "threadId": new_id,
                                "path": str(destination),
                                "excludeTurns": True,
                                "cwd": str(target),
                                "runtimeWorkspaceRoots": [str(target)],
                                "modelProvider": candidate["row"]["model_provider"],
                            },
                        )["thread"]
                        if copied["id"] != new_id or copied["cwd"] != str(target):
                            raise CoverageError("published copy identity mismatch")
                        if candidate["row"]["name"] is not None:
                            client.request(
                                "thread/name/set",
                                {"threadId": new_id, "name": candidate["row"]["name"]},
                            )
                        if signature(client, new_id) != expected:
                            raise CoverageError("published copy history mismatch")
                    recheck(root, candidate)
                    provenance = Path(state_root) / "copies"
                    provenance.mkdir(exist_ok=True, mode=0o700)
                    atomic_write(
                        provenance / (new_id + ".json"),
                        {
                            "version": 1,
                            "runtime": "codex",
                            "sourceId": candidate["id"],
                            "id": new_id,
                            "storeRoot": str(root),
                            "targetCwd": str(target),
                            "independentCopy": True,
                            "method": "native-header-and-exact-tail-materialization",
                            "historyDigest": expected,
                        },
                    )
                    results.append(
                        {
                            "sourceId": candidate["id"],
                            "id": new_id,
                            "status": "copied",
                            "cwd": str(target),
                            "independentCopy": True,
                        }
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
                results.append(
                    {
                        "sourceId": candidate["id"],
                        "id": new_id,
                        "status": "failed",
                        "destinationMayContainCopy": published,
                        "automaticRetrySafe": False,
                    }
                )
                results += [
                    {"sourceId": c["id"], "status": "not_attempted"} for c in selected[index + 1 :]
                ]
                break
        return {
            "runtime": "codex",
            "action": "independent-copy",
            "results": results,
            "status": "copied" if all(r["status"] == "copied" for r in results) else "incomplete",
            "warning": "Version-pinned destination materialization, not plain native fork. Sources "
            "and historical paths unchanged. No project files, external assets, operational "
            "state or unsupported ancillary rows copied. Fresh native cwd applies going forward.",
        }
