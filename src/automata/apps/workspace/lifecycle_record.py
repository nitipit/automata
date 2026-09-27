"""Private durable launch identity and exact owned-session validation."""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .lifecycle_config import AgentConfig


def atomic_json(path: Path, value: dict) -> None:
    temp = path.with_suffix(".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def load_record(config: AgentConfig) -> dict | None:
    path = config.root / "lifecycle.json"
    if not path.exists():
        return None
    record = json.loads(path.read_text())
    if (not isinstance(record, dict) or record.get("agentId") != config.agent_id
            or record.get("participant") != config.participant
            or record.get("cwd") != str(config.cwd)
            or not isinstance(record.get("sessionId"), str)
            or not isinstance(record.get("sessionFile"), str)
            or not record.get("sessionId")):
        raise ValueError("Lifecycle ownership record mismatch")
    return record


def new_record(config: AgentConfig) -> dict:
    session_id = str(uuid4())
    directory = config.root / "sessions"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / f"{session_id}.jsonl"
    record = {"agentId": config.agent_id, "participant": config.participant,
              "cwd": str(config.cwd), "sessionId": session_id, "sessionFile": str(path),
              "phase": "starting", "pid": None, "processStart": None}
    # Reserve exact ownership before creating or spawning; an interrupted reservation
    # stays visible and never silently creates a replacement session on Resume.
    atomic_json(config.root / "lifecycle.json", record)
    header = {"type": "session", "version": 3, "id": session_id,
              "timestamp": datetime.now(UTC).isoformat(), "cwd": str(config.cwd)}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(json.dumps(header) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return record


def validate_session(config: AgentConfig, record: dict) -> Path:
    path = Path(record["sessionFile"])
    directory = (config.root / "sessions").resolve()
    if path.is_symlink() or path.parent.resolve() != directory or not path.is_file():
        raise ValueError("Exact owned saved session is missing or outside its store")
    # Validate only this explicitly owned file, not Pi's default/global session store.
    # Pi tolerates malformed lines; Resume must fail closed instead of losing history.
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Owned session exceeds validation bound")
    with path.open() as stream:
        first = stream.readline()
        if not first:
            raise ValueError("Owned saved session is empty")
        header = json.loads(first)
        if (not isinstance(header, dict) or header.get("type") != "session"
                or header.get("version") != 3
                or header.get("id") != record["sessionId"]
                or header.get("cwd") != str(config.cwd)):
            raise ValueError("Saved session identity mismatch")
        for line in stream:
            entry = json.loads(line)
            if (not isinstance(entry, dict) or not isinstance(entry.get("type"), str)
                    or not isinstance(entry.get("id"), str)
                    or not isinstance(entry.get("timestamp"), str)
                    or "parentId" not in entry):
                raise ValueError("Corrupt owned saved session")
    return path


def process_start(pid: int) -> str | None:
    try:
        # Linux /proc identity protects against PID reuse; no process-name inference.
        text = Path(f"/proc/{pid}/stat").read_text()
        return text[text.rfind(")") + 2:].split()[19]
    except (OSError, IndexError):
        return None
