"""Version-pinned, session-local Codex 0.159.0 usage extraction (no discovery).

Only usage and provenance leave this module. Conversation bodies are discarded.
Aggregated TokenCount and restored estimates are never added to response usage.
"""

from __future__ import annotations

import json
import os
import stat
import uuid
from pathlib import Path

from context_records import ContextRecords

VERSION = "0.159.0"
MAX_BYTES = 64 * 1024 * 1024
MAX_LINE = 8 * 1024 * 1024
MAX_INTEGER = 2**53 - 1
CATEGORIES = ("input", "output", "cacheRead", "cacheWrite")


class CoverageError(ValueError):
    """A bounded, non-sensitive reason the input cannot establish coverage."""


def identifier(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 200:
        raise CoverageError("invalid response identity")
    if any(not (character.isalnum() or character in "_-.:") for character in value):
        raise CoverageError("invalid response identity")
    return value


def session_id(value: object) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError) as error:
        raise CoverageError("invalid session identity") from error


def normalize(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        raise CoverageError("missing response usage")
    names = ("input_tokens", "output_tokens", "cached_input_tokens", "cache_write_input_tokens")
    if any(
        type(value.get(name)) is not int or not 0 <= value[name] <= MAX_INTEGER for name in names
    ):
        raise CoverageError("unknown usage schema")
    input_tokens, output, reads, writes = (value[name] for name in names)
    if reads + writes > input_tokens or input_tokens + output > MAX_INTEGER:
        raise CoverageError("inconsistent cache categories")
    # Codex input includes cache reads/writes. Reasoning is already in output.
    return {
        "input": input_tokens - reads - writes,
        "output": output,
        "cacheRead": reads,
        "cacheWrite": writes,
    }


def counted(usage: dict[str, int]) -> int:
    return usage["input"] + usage["output"] + usage["cacheWrite"]


def scan(path: Path, expected_session: str, excluded_turns=()) -> dict:
    """Read only this explicit path, to a fixed byte boundary; defer partial tail.

    No inherited history paths are followed. Ordinal is a location, never dedup
    identity. A disappearing/rewritten file fails closed, retaining prior state.
    """
    expected_session = session_id(expected_session)
    if not path.is_absolute():
        raise CoverageError("transcript path must be absolute")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise CoverageError("transcript unavailable") from error
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise CoverageError("unsupported transcript file or size")
        remaining = before.st_size
        records = {}
        context = ContextRecords()
        completed_turns = set()
        compacted_turns = set(excluded_turns)
        active_turn = None
        metadata = None
        partial_tail = False
        last_ordinal = -1
        while remaining:
            line = stream.readline(min(remaining, MAX_LINE + 1))
            remaining -= len(line)
            if len(line) > MAX_LINE:
                raise CoverageError("transcript record too large")
            if not line.endswith(b"\n"):
                partial_tail = True
                break
            try:
                item = json.loads(line)
            except (ValueError, UnicodeDecodeError) as error:
                raise CoverageError("invalid transcript JSON") from error
            if not isinstance(item, dict) or not isinstance(item.get("payload"), dict):
                raise CoverageError("unknown transcript envelope")
            ordinal = item.get("ordinal")
            if type(ordinal) is not int or ordinal <= last_ordinal:
                raise CoverageError("unknown transcript sequence")
            last_ordinal = ordinal
            payload = item["payload"]
            context.observe(item)
            if metadata is None:
                if item.get("type") != "session_meta" or payload.get("cli_version") != VERSION:
                    raise CoverageError("unsupported Codex transcript version")
                if session_id(payload.get("session_id")) != expected_session:
                    raise CoverageError("transcript session mismatch")
                metadata = {
                    "thread": session_id(payload.get("id")),
                    "session": expected_session,
                    "version": VERSION,
                }
            elif item.get("type") == "session_meta":
                raise CoverageError("duplicate session metadata")
            if item.get("type") == "event_msg":
                event = payload.get("type")
                if event == "task_started":
                    active_turn = identifier(payload.get("turn_id"))
                elif event == "task_complete":
                    completed_turns.add(identifier(payload.get("turn_id")))
                elif event in ("item_started", "item_completed"):
                    if not isinstance(payload.get("item"), dict):
                        raise CoverageError("unknown turn item envelope")
                    if payload["item"].get("type") == "ContextCompaction":
                        compacted_turns.add(identifier(payload.get("turn_id")))
            elif item.get("type") == "compacted":
                # Exclude the entire containing turn, not just the final summary:
                # retries can have usage too. Main work in mixed turns is omitted.
                compacted_turns.add(active_turn)
            if item.get("type") != "token_usage_record":
                continue
            thread = session_id(payload.get("thread_id"))
            response = identifier(payload.get("response_id"))
            record = {
                "thread": thread,
                "response": response,
                "turn": identifier(payload.get("turn_id")),
                "usage": normalize(payload.get("usage")),
                "ordinal": ordinal,
            }
            key = f"{thread}:{response}"
            previous = records.get(key)
            if previous and any(previous[k] != record[k] for k in ("turn", "usage")):
                raise CoverageError("conflicting response replay")
            records.setdefault(key, record)
        after = os.fstat(stream.fileno())
        if after.st_size < before.st_size or after.st_mtime_ns != before.st_mtime_ns:
            raise CoverageError("transcript changed during observation")
    if metadata is None:
        raise CoverageError("session metadata unavailable")
    eligible = {
        key: record
        for key, record in records.items()
        if record["turn"] in completed_turns and record["turn"] not in compacted_turns
    }
    return {
        **metadata,
        "records": eligible,
        "observations": context.result(),
        "partialTail": partial_tail,
        "excludedCompactionRecords": sum(r["turn"] in compacted_turns for r in records.values()),
        "unclassifiedRecords": sum(r["turn"] not in completed_turns for r in records.values()),
        "throughOrdinal": last_ordinal,
        "observedBytes": before.st_size,
    }
