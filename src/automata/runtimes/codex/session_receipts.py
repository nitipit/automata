"""Private metadata snapshots and fresh, one-use session selection receipts."""

from __future__ import annotations

import fcntl
import hashlib
import json
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from session_store import absolute, identify, inventory, recheck, summary
from token_awareness import atomic_write
from token_records import CoverageError, session_id

TTL = 300


def token():
    return str(uuid.uuid4())


def root_identity(root):
    if not root.exists():
        return None
    info = root.stat()
    if not root.is_dir():
        raise CoverageError("store root must be a directory")
    return [info.st_dev, info.st_ino]


@contextmanager
def locked(state_root, store_root):
    store = absolute(store_root)
    state = absolute(state_root)
    if state == store or state.is_relative_to(store):
        raise CoverageError("management state must be outside native store")
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = hashlib.sha256(str(store).encode()).hexdigest()
    path = state / f"{key}.json"
    lock_path = state / f"{key}.lock"
    if path.is_symlink() or lock_path.is_symlink():
        raise CoverageError("symlinked management state unsupported")
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield store, path


def load(path, root):
    if not path.exists() or path.stat().st_size > 128 * 1024 * 1024:
        raise CoverageError("receipt snapshot unavailable")
    value = json.loads(path.read_text())
    if (
        value["version"] != 1
        or value["storeRoot"] != str(root)
        or value["rootIdentity"] != root_identity(root)
        or not value["createdAt"] <= time.time() <= value["expiresAt"]
    ):
        raise CoverageError("receipt expired or root identity changed")
    return value


def page(state, current):
    offset, limit = state["offset"], state["limit"]
    candidates = state["candidates"][offset : offset + limit]
    available = []
    for candidate in candidates:
        try:
            available.append(recheck(Path(state["storeRoot"]), candidate))
        except (CoverageError, OSError, ValueError, KeyError, TypeError):
            continue
    state["pageIds"] = [c["id"] for c in available if c["id"] != current]
    state["copyReceipt"], state["forkReceipt"], state["trashReceipt"] = token(), token(), token()
    state["offset"] += len(candidates)
    state["nextCursor"] = token() if state["offset"] < len(state["candidates"]) else None
    return {
        "runtime": "codex",
        "storeRoot": state["storeRoot"],
        "scope": state["scope"],
        "cwd": state["cwd"],
        "coverage": state["coverage"],
        "sessions": [summary(c, current) for c in available],
        "totalCount": len(state["candidates"]),
        "unavailableCount": state["unavailableCount"] + len(candidates) - len(available),
        "nextCursor": state["nextCursor"],
        "copyReceipt": state["copyReceipt"],
        "forkReceipt": state["forkReceipt"],
        "trashReceipt": state["trashReceipt"],
        "expiresAt": state["expiresAt"],
        "warning": "Metadata snapshot, not inactivity or permission. Receipts cover only "
        "this page. Unindexed rollouts and other roots are not searched. "
        "Fork is linked, not independent copy.",
    }


def list_sessions(
    state_root, store_root, cwd=None, all_projects=False, limit=20, cursor=None, current=None
):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise CoverageError("limit must be from 1 to 100")
    if current:
        current = session_id(current)
    with locked(state_root, store_root) as (root, path):
        if cursor:
            if cwd is not None or all_projects:
                raise CoverageError("cursor cannot change scope")
            state = load(path, root)
            if state["nextCursor"] != cursor or state["current"] != current:
                raise CoverageError("unknown/superseded cursor or changed caller")
        else:
            if (cwd is None) == (not all_projects):
                raise CoverageError("choose exact --cwd or explicit --all-projects")
            if cwd is not None:
                cwd = str(Path(cwd))
                if not Path(cwd).is_absolute():
                    raise CoverageError("cwd must be exact absolute path")
            rows, coverage = inventory(root, cwd)
            candidates, unavailable = [], 0
            for row in rows:
                try:
                    candidates.append(identify(root, row))
                except (CoverageError, OSError, ValueError, KeyError, TypeError):
                    unavailable += 1
            now = time.time()
            state = {
                "version": 1,
                "storeRoot": str(root),
                "rootIdentity": root_identity(root),
                "createdAt": now,
                "expiresAt": now + TTL,
                "scope": "all-projects-in-selected-store" if all_projects else "exact-cwd",
                "cwd": cwd,
                "limit": limit,
                "offset": 0,
                "current": current,
                "candidates": candidates,
                "unavailableCount": unavailable,
                "coverage": coverage,
            }
        output = page(state, current)
        atomic_write(path, state)
        return output


def claim(path, root, action, receipt, ids, current):
    """Preflight every selection before consuming; callers keep the namespace lock."""
    if not ids or len(ids) > 100 or len(ids) != len(set(ids)):
        raise CoverageError("select 1-100 unique full session IDs")
    ids = [session_id(value) for value in ids]
    state = load(path, root)
    key = {"copy": "copyReceipt", "fork": "forkReceipt", "trash": "trashReceipt"}[action]
    if not receipt or receipt != state.get(key) or current != state["current"]:
        raise CoverageError("receipt unknown/consumed or caller changed")
    if not set(ids) <= set(state["pageIds"]) or current in ids:
        raise CoverageError("IDs not selectable on this receipt page; current session rejected")
    selected = {c["id"]: c for c in state["candidates"] if c["id"] in ids}
    for identity in ids:
        recheck(root, selected[identity])
    state[key] = None
    atomic_write(path, state)
    return [selected[identity] for identity in ids]
