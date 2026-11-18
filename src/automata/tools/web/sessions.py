"""Project-scoped picker metadata and cooperative Web Chat ownership."""

from __future__ import annotations

import fcntl
import json
import os
import stat
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

PAGE_SIZE = 50
_MAX_LINE = 4 * 1024 * 1024
_MAX_PREVIEW_BYTES = 64 * 1024 * 1024
_MAX_PREVIEW_ENTRIES = 50_000


def _header(stream) -> dict:
    entry = json.loads(stream.readline(_MAX_LINE + 1))
    if not isinstance(entry, dict) or entry.get("type") != "session":
        raise ValueError("Missing Pi session header")
    return entry


def recorded_project(path: Path) -> Path:
    with path.open("rb") as stream:
        cwd = _header(stream).get("cwd")
    if not isinstance(cwd, str) or not Path(cwd).is_absolute():
        raise ValueError("Session has no absolute project directory")
    return Path(os.path.normpath(cwd))


def _label(value) -> str:
    if not isinstance(value, str):
        return ""
    # Collapse whitespace and prevent unpaired UTF-16 surrogates in browser JSON.
    value = " ".join(value.encode("utf-8", "replace").decode().split())
    return value[:64] + ("…" if len(value) > 64 else "")


def _message_text(message, limit: int) -> str:
    content = message.get("content")
    if isinstance(content, str):
        text = content.strip()[: limit + 1]
    elif isinstance(content, list):
        parts, length = [], 0
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "text":
                continue
            value = part.get("text")
            if not isinstance(value, str) or not (value := value.strip()):
                continue
            parts.append(value[: limit + 1 - length])
            length += len(value) + 1
            if length > limit:
                break
        text = "\n".join(parts)
    else:
        return ""
    text = text.encode("utf-8", "replace").decode()
    return text[:limit] + ("…" if len(text) > limit else "")


@dataclass(frozen=True)
class SessionRow:
    path: Path
    id: str
    label: str
    snippet: str
    revision: tuple[int, int, int, int, int]

    @property
    def modified(self) -> str:
        return datetime.fromtimestamp(self.revision[3] / 1e9, UTC).isoformat()

    def unchanged(self) -> bool:
        try:
            return _revision(self.path.lstat()) == self.revision
        except OSError:
            return False


def _revision(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


@contextmanager
def _open_revision(path: Path, revision: tuple[int, int, int, int, int]):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or _revision(info) != revision:
            raise ValueError("Session revision changed")
        yield stream
        if _revision(path.lstat()) != revision:
            raise ValueError("Session revision changed")


def read_row(path: Path, project: Path) -> SessionRow | None:
    """Read display metadata only; Pi remains authoritative for actual history."""
    try:
        revision = _revision(path.lstat())
        with _open_revision(path, revision) as stream:
            header = _header(stream)
            cwd, session_id = header.get("cwd"), header.get("id")
            if (
                not isinstance(cwd, str)
                or not Path(cwd).is_absolute()
                or Path(os.path.normpath(cwd)) != project
                or not isinstance(session_id, str)
                or not 1 <= len(session_id) <= 256
                or session_id.encode("utf-8", "replace").decode() != session_id
            ):
                return None
            name, preview = "", None
            while line := stream.readline(_MAX_LINE + 1):
                if len(line) > _MAX_LINE:
                    return None
                entry = json.loads(line)
                if not isinstance(entry, dict):
                    return None
                if entry.get("type") == "session_info":
                    name = _label(entry.get("name"))
                elif preview is None and entry.get("type") == "message":
                    message = entry.get("message")
                    if isinstance(message, dict) and message.get("role") == "user":
                        preview = _message_text(message, 160)
            return SessionRow(
                path,
                session_id,
                name or _label(preview) or "Untitled session",
                " ".join((preview or "").split()),
                revision,
            )
    except (OSError, ValueError, RecursionError):
        pass
    return None


def _preview_fields(entry: dict) -> dict:
    if entry.get("type") == "model_change":
        return {"provider": _label(entry.get("provider")), "model": _label(entry.get("modelId"))}
    message = entry.get("message")
    if entry.get("type") != "message" or not isinstance(message, dict):
        return {}
    role = message.get("role")
    if role not in ("user", "assistant"):
        return {}
    result = {"role": role, "text": _message_text(message, 800)}
    if role == "assistant":
        result.update(provider=_label(message.get("provider")), model=_label(message.get("model")))
        usage = message.get("usage")
        tokens = usage.get("totalTokens") if isinstance(usage, dict) else None
        if (
            type(tokens) is int
            and 0 < tokens <= 2**53 - 1
            and message.get("stopReason") not in ("aborted", "error")
        ):
            result["tokens"] = tokens
    return result


def read_preview(row: SessionRow) -> dict:
    """Read bounded inert text from the persisted leaf, never from another branch."""
    try:
        if row.revision[2] > _MAX_PREVIEW_BYTES:
            raise ValueError("Session exceeds preview limit")
        with _open_revision(row.path, row.revision) as stream:
            header = _header(stream)
            if header.get("id") != row.id:
                raise ValueError("Session ID changed")
            # Native Pi v2+ restores the last persisted entry as the leaf. Older
            # unlinked histories are linear; do not guess when a linked file is broken.
            entries: dict[str, tuple[str | None, dict]] = {}
            leaf = None
            linked = header.get("version") in (2, 3)
            for index in range(_MAX_PREVIEW_ENTRIES + 1):
                line = stream.readline(_MAX_LINE + 1)
                if not line:
                    break
                if len(line) > _MAX_LINE or index == _MAX_PREVIEW_ENTRIES:
                    raise ValueError("Session exceeds preview limit")
                if not line.strip():
                    continue
                entry = json.loads(line)
                if not isinstance(entry, dict):
                    raise ValueError("Invalid session entry")
                if index == 0 and ("id" in entry or "parentId" in entry):
                    linked = True
                key, parent = (
                    (entry.get("id"), entry.get("parentId")) if linked else (str(index), leaf)
                )
                if (
                    not isinstance(key, str)
                    or not key
                    or key in entries
                    or (parent is not None and not isinstance(parent, str))
                ):
                    raise ValueError("Invalid session branch")
                entries[key] = (parent, _preview_fields(entry))
                leaf = key
            branch = []
            while leaf is not None:
                # Popping also rejects cycles and missing parents.
                leaf, fields = entries.pop(leaf)
                branch.append(fields)
            user = assistant = model = tokens = None
            for fields in reversed(branch):
                if fields.get("model"):
                    model = "/".join(filter(None, (fields["provider"], fields["model"])))
                if fields.get("role") == "user":
                    user, assistant, tokens = fields["text"], None, None
                elif fields.get("role") == "assistant" and user is not None:
                    if fields["text"]:
                        assistant = fields["text"]
                    tokens = fields.get("tokens")
            return {"user": user, "assistant": assistant, "model": model, "tokens": tokens}
    except (OSError, ValueError, KeyError, RecursionError) as error:
        raise ValueError(
            "Session preview is unavailable. Reload Sessions if the file changed."
        ) from error


def list_rows(store: Path, project: Path) -> tuple[list[SessionRow], Counter]:
    rows = []
    try:
        for path in store.iterdir():
            if path.suffix == ".jsonl" and (row := read_row(path, project)) is not None:
                rows.append(row)
    except FileNotFoundError:
        pass
    rows.sort(key=lambda row: (-row.revision[3], row.id, row.path.name))
    return rows, Counter(row.id for row in rows)


class SessionClaim:
    """Advisory, per-file lock shared by updated Web Chat hosts, not Pi generally."""

    def __init__(self, path: Path):
        self.path = path
        lock_dir = path.parent / ".automata-web-locks"
        try:
            lock_dir.mkdir(mode=0o700, exist_ok=True)
            if lock_dir.is_symlink():
                raise OSError("Lock directory must not be a symlink")
            fd = os.open(
                lock_dir / (path.name + ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
            )
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(fd)
                raise
        except BlockingIOError as error:
            raise ValueError("Session is open in another Web Chat host") from error
        except OSError as error:
            raise ValueError("Could not establish Web Chat session ownership") from error
        self.fd = fd

    def close(self):
        # Never unlink a lock file: another opener could have acquired its inode.
        os.close(self.fd)
