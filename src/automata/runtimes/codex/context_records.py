"""Bounded metadata projection for context and timestamp awareness.

Native totals here are context observations, never billing/response-ledger sums.
No message text, tool arguments, reasoning or history bodies are retained.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

MAX_INTEGER = 2**53 - 1
RECENT_LIMIT = 6


def identity(value):
    return (
        value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", value) else None
    )


def integer(value):
    return value if type(value) is int and 0 <= value <= MAX_INTEGER else None


def timestamp(value):
    """Accept only offset-aware ISO strings; canonical UTC retains an offset."""
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(UTC).isoformat() if parsed.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def milliseconds(value):
    if integer(value) is None or value == 0:
        return None
    try:
        return datetime.fromtimestamp(value / 1000, UTC).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


class ContextRecords:
    def __init__(self):
        self.recent = []
        self.latest_user = None
        self.latest_task = None
        self.native_context = None
        self.malformed = 0

    def observe(self, row):
        payload = row["payload"]
        if row.get("type") != "event_msg":
            return
        event = payload.get("type")
        ordinal = row["ordinal"]
        recorded_at = timestamp(row.get("timestamp"))
        if event == "token_count":
            info = payload.get("info")
            if info is None:  # Rate-limit-only notification is not a new context observation.
                return
            usage = info.get("last_token_usage") if isinstance(info, dict) else None
            total = integer(usage.get("total_tokens")) if isinstance(usage, dict) else None
            window = integer(info.get("model_context_window")) if isinstance(info, dict) else None
            if window == 0:
                window = None
            recomputed = (
                isinstance(usage, dict)
                and total is not None
                and total > 0
                and all(
                    usage.get(name) == 0
                    for name in (
                        "input_tokens",
                        "output_tokens",
                        "cached_input_tokens",
                        "cache_write_input_tokens",
                        "reasoning_output_tokens",
                    )
                )
            )
            reported = total
            if total == 0:
                total = None  # Native zero/default telemetry does not establish an empty context.
            self.native_context = {
                "tokens": total,
                "reportedTokens": reported,
                "window": window,
                "recordOrdinal": ordinal,
                "recordedAt": recorded_at,
                "source": (
                    "recomputed-context-estimate"
                    if recomputed
                    else "native-last-usage-total"
                    if total is not None
                    else "unknown-native-usage"
                ),
                "percent": round(total * 100 / window, 3) if total is not None and window else None,
            }
            if total is None:
                self.malformed += 1
        elif event == "task_started":
            turn = identity(payload.get("turn_id"))
            seconds = integer(payload.get("started_at"))
            window = integer(payload.get("model_context_window"))
            self.latest_task = {
                "turn": turn,
                "recordOrdinal": ordinal,
                "startedAt": milliseconds(seconds * 1000) if seconds else None,
                "modelWindow": window or None,
                "recordedAt": recorded_at,
            }
        elif event == "item_completed":
            item = payload.get("item")
            if not isinstance(item, dict):
                self.malformed += 1
                return
            kind = item.get("type")
            if not isinstance(kind, str) or kind not in {"UserMessage", "AgentMessage"}:
                return
            item_id = identity(item.get("id"))
            turn = identity(payload.get("turn_id"))
            if item_id is None or turn is None:
                self.malformed += 1
                return
            entry = {
                "item": item_id,
                "turn": turn,
                "role": "user" if kind == "UserMessage" else "assistant",
                "startedAt": milliseconds(payload.get("started_at_ms")),
                "completedAt": milliseconds(payload.get("completed_at_ms")),
                "recordedAt": recorded_at,
                "recordOrdinal": ordinal,
            }
            # Native item IDs, not timestamps/line offsets, establish identity.
            key = (turn, item_id)
            prior = next((e for e in self.recent if (e["turn"], e["item"]) == key), None)
            if prior is None:
                self.recent = (self.recent + [entry])[-RECENT_LIMIT:]
            elif any(prior[name] != entry[name] for name in ("role", "startedAt", "completedAt")):
                self.malformed += 1
            if kind == "UserMessage":
                self.latest_user = prior or entry

    def result(self):
        return {
            "recentMessages": self.recent,
            "latestUser": self.latest_user,
            "latestTask": self.latest_task,
            "nativeContext": self.native_context,
            "malformedMetadata": self.malformed,
        }
