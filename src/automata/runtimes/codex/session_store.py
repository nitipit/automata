"""Pinned read-only Codex store metadata, path/identity and dependency checks.

Only explicit roots. Never discover homes, follow parent stores, select previews or
persist message bodies. SQLite and JSONL are native-owned; this module never writes them.
"""

from __future__ import annotations

import json
import os
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path

from token_records import MAX_BYTES, MAX_LINE, VERSION, CoverageError, session_id

COLUMNS = (
    "id",
    "rollout_path",
    "cwd",
    "created_at",
    "updated_at",
    "archived",
    "cli_version",
    "source",
    "model_provider",
    "model",
    "history_mode",
    "name",
    "is_pinned",
    "project_id",
    "thread_section_id",
    "thread_source",
    "agent_role",
    "agent_nickname",
)
MAX_SESSIONS = 10_000


def absolute(path):
    path = Path(os.path.abspath(path))
    if path.resolve() != path:
        raise CoverageError("symlinked scope unsupported")
    return path


@contextmanager
def database(root, name="state_5.sqlite"):
    path = root / name
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(path) + suffix)
        if candidate.is_symlink():
            raise CoverageError("symlinked native database unsupported")
    if not path.is_file():
        raise CoverageError("native database unavailable; no implicit repair")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    try:
        yield connection
    finally:
        connection.close()


def inventory(root, cwd=None):
    root = absolute(root)
    if not root.exists():
        return [], "missing-root"
    if not (root / "state_5.sqlite").exists():
        return [], "no-native-index; unindexed history not searched"
    with database(root) as db:
        sql = "SELECT " + ",".join(COLUMNS) + " FROM threads"
        args = []
        if cwd is not None:
            sql += " WHERE cwd = ?"
            args.append(cwd)
        sql += " ORDER BY updated_at DESC, id LIMIT ?"
        rows = db.execute(sql, [*args, MAX_SESSIONS + 1]).fetchall()
        if len(rows) > MAX_SESSIONS:
            raise CoverageError("metadata scope exceeds 10000 sessions; narrow scope")
        return [dict(row) for row in rows], "native-index-only"


def directory_status(cwd):
    try:
        return (
            "exists" if Path(cwd).is_dir() else "missing" if not Path(cwd).exists() else "unknown"
        )
    except OSError:
        return "unknown"


def rollout_path(root, identity, value):
    identity = session_id(identity)
    path = Path(value)
    if not path.is_absolute() or path.resolve() != path:
        raise CoverageError("invalid rollout path")
    if not any(path.is_relative_to(root / name) for name in ("sessions", "archived_sessions")):
        raise CoverageError("rollout outside selected store")
    if path.suffix != ".jsonl" or identity not in path.name:
        raise CoverageError("unexpected rollout filename")
    return path


def identify(root, row):
    identity = session_id(row["id"])
    path = rollout_path(root, identity, row["rollout_path"])
    if row["cli_version"] != VERSION or row["history_mode"] != "paginated":
        raise CoverageError("unsupported native session version/mode")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise CoverageError("unsupported rollout file/size")
        line = stream.readline(MAX_LINE + 1)
        if len(line) > MAX_LINE or not line.endswith(b"\n"):
            raise CoverageError("invalid rollout metadata record")
        envelope = json.loads(line)
        header = envelope["payload"]
        if (
            envelope.get("type") != "session_meta"
            or header.get("id") != identity
            or header.get("cli_version") != VERSION
            or header.get("cwd") != row["cwd"]
            or header.get("history_mode") != "paginated"
        ):
            raise CoverageError("native metadata identity mismatch")
        after = os.fstat(stream.fileno())
    if before.st_mtime_ns != after.st_mtime_ns or before.st_size != after.st_size:
        raise CoverageError("rollout changed during observation")
    base = header.get("history_base")
    if base is not None and (not isinstance(base, dict) or not base.get("thread_id")):
        raise CoverageError("unsupported native history dependency metadata")
    parent = base.get("thread_id") if isinstance(base, dict) else None
    provenance = header.get("forked_from_id")
    return {
        "row": row,
        "id": identity,
        "path": str(path),
        "device": before.st_dev,
        "inode": before.st_ino,
        "size": before.st_size,
        "mtimeNs": before.st_mtime_ns,
        "directoryStatus": directory_status(row["cwd"]),
        "historyParent": session_id(parent) if parent else None,
        "forkedFromId": session_id(provenance) if provenance else None,
    }


def summary(candidate, current=None):
    row = candidate["row"]
    return {
        "runtime": "codex",
        "id": candidate["id"],
        "cwd": row["cwd"],
        "name": row["name"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "archived": bool(row["archived"]),
        "historyMode": row["history_mode"],
        "forkedFromId": candidate["forkedFromId"],
        "historyParent": candidate["historyParent"],
        "directoryStatus": candidate["directoryStatus"],
        "current": row["id"] == current,
        "selectable": row["id"] != current,
        "activity": "unknown outside this operation; caller must establish inactivity",
    }


def recheck(root, expected):
    with database(root) as db:
        row = db.execute(
            "SELECT " + ",".join(COLUMNS) + " FROM threads WHERE id=?", [expected["id"]]
        ).fetchone()
    if row is None or identify(root, dict(row)) != expected:
        raise CoverageError("selected session changed; receipt stale")
    return expected


def effect_closure(root, ids):
    """Enumerate metadata dependencies only inside the authorized store.

    Native removal can cascade spawned descendants. Linked forks can retain source
    history references without spawn edges. Both incoming and outgoing lineage is
    conservatively checked; unknown metadata blocks destructive actions.
    """
    rows, _ = inventory(root)
    nodes = {row["id"]: identify(root, row) for row in rows}
    if not set(ids) <= nodes.keys():
        raise CoverageError("selected dependency node unavailable")
    edges = set()
    for identity, node in nodes.items():
        parent = node["historyParent"]
        if parent:
            edges.add((parent, identity))
    with database(root) as db:
        edges.update(
            tuple(row)
            for row in db.execute(
                "SELECT parent_thread_id, child_thread_id FROM thread_spawn_edges"
            )
        )
    closure = set(ids)
    while True:
        expanded = closure | {child for parent, child in edges if parent in closure}
        if expanded == closure:
            break
        closure = expanded
    if closure - set(ids):
        raise CoverageError(
            "unselected spawned/history dependents; parent receipt grants no authority"
        )
    # Initial trash contract intentionally excludes even selected dependency groups:
    # restoring nested native projections/ancillary state has not been certified.
    if any(parent in closure or child in closure for parent, child in edges):
        raise CoverageError("linked/spawned recovery groups unsupported; no mutation")
    return sorted(closure)


def ensure_recoverable_subset(root, candidate):
    row = candidate["row"]
    if row["archived"] or any(
        row[key]
        for key in (
            "is_pinned",
            "project_id",
            "thread_section_id",
            "thread_source",
            "agent_role",
            "agent_nickname",
        )
    ):
        raise CoverageError("archived or enriched thread recovery unsupported")
    checks = {
        "state_5.sqlite": [
            ("thread_dynamic_tools", "thread_id"),
            ("thread_attachments", "thread_id"),
        ],
        "goals_1.sqlite": [
            ("thread_goals", "thread_id"),
            ("thread_goal_continuation_deferrals", "thread_id"),
        ],
        "queue_1.sqlite": [("queued_items", "thread_id")],
        "memories_1.sqlite": [("stage1_outputs", "thread_id"), ("jobs", "job_key")],
    }
    for name, tables in checks.items():
        if not (root / name).exists():
            continue
        with database(root, name) as db:
            for table, column in tables:
                if db.execute(
                    f"SELECT 1 FROM {table} WHERE {column}=? LIMIT 1", [candidate["id"]]
                ).fetchone():
                    raise CoverageError("ancillary native state lacks certified recovery")
