"""Bounded interoperable JSON and version-one compatibility envelopes."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

MAX_FRAME_BYTES = 64 * 1024
MAX_PAYLOAD_BYTES = 32 * 1024
MAX_METADATA_BYTES = 16 * 1024
MAX_JSON_DEPTH = 32
MAX_ID_LENGTH = 128
MAX_SAFE_INTEGER = 2**53 - 1
SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

JsonObject = dict[str, Any]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode(
        "utf-8", errors="backslashreplace"
    )


def valid_json_value(value: Any, depth: int = 0) -> bool:
    """Check the JSON subset shared by Python and JavaScript without projection."""
    if depth > MAX_JSON_DEPTH:
        return False
    if value is None or isinstance(value, (str, bool)):
        return True
    if isinstance(value, int) and not isinstance(value, bool):
        return abs(value) <= MAX_SAFE_INTEGER
    if isinstance(value, float):
        return math.isfinite(value) and (not value.is_integer() or abs(value) <= MAX_SAFE_INTEGER)
    if isinstance(value, list):
        return all(valid_json_value(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and valid_json_value(item, depth + 1)
            for key, item in value.items()
        )
    return False


def validate_payload(value: Any) -> bytes:
    if not valid_json_value(value):
        raise ValueError("payload must contain only finite, interoperable JSON values")
    try:
        encoded = json_bytes(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("payload is not serializable JSON") from error
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise ValueError("payload exceeds 32 KiB")
    return encoded


def validate_metadata(value: Any) -> bytes:
    """Leave headroom for provenance and bounded Pi tool results beside a full payload."""
    encoded = validate_payload(value)
    if len(encoded) > MAX_METADATA_BYTES:
        raise ValueError("metadata exceeds 16 KiB")
    return encoded


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-JSON number {value} is not supported")


def strict_object_pairs(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def parse_frame(raw: Any) -> JsonObject:
    if not isinstance(raw, str):
        raise ValueError("WebSocket messages must be text")
    if len(raw.encode("utf-8")) > MAX_FRAME_BYTES:
        raise ValueError("WebSocket frame exceeds 64 KiB")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=strict_object_pairs,
            parse_constant=reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError, RecursionError) as error:
        raise ValueError("WebSocket message is not valid JSON") from error
    if not isinstance(value, dict):
        raise ValueError("WebSocket message must be an object")
    # Allow routing wrappers above the independently bounded component payload.
    if not valid_json_value(value, depth=-4):
        raise ValueError("WebSocket frame contains invalid or excessively nested JSON")
    return value


def require_string(value: Any, name: str, *, max_length: int = MAX_ID_LENGTH) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise ValueError(f"{name} must be a bounded non-empty string")
    return value


def validate_message(value: JsonObject) -> tuple[str, Any]:
    if isinstance(value.get("v"), bool) or value.get("v") != 1 or value.get("kind") != "message":
        raise ValueError("Expected a version 1 message envelope")
    identity = require_string(value.get("id"), "message id")
    if "payload" not in value:
        raise ValueError("message envelope requires payload")
    payload = value["payload"]
    validate_payload(payload)
    return identity, payload


def validate_delivery(value: Any) -> JsonObject:
    """Delivery policy is transport metadata, never inferred from component payloads."""
    if not isinstance(value, dict) or set(value) - {"role", "deliverAs", "slot", "triggerTurn"}:
        raise ValueError("Invalid delivery options")
    role, mode = value.get("role", "user"), value.get("deliverAs", "immediate")
    if role not in ("user", "context") or mode not in (
        "immediate",
        "steer",
        "followUp",
        "nextTurn",
    ):
        raise ValueError("Invalid role or deliverAs")
    if role == "user" and (mode == "nextTurn" or "triggerTurn" in value):
        raise ValueError("User messages always trigger a turn and cannot use nextTurn")
    if "triggerTurn" in value and not isinstance(value["triggerTurn"], bool):
        raise ValueError("triggerTurn must be boolean")
    if mode == "nextTurn" and value.get("triggerTurn"):
        raise ValueError("nextTurn cannot trigger a turn")
    if "slot" in value:
        require_string(value["slot"], "context slot")
        if role != "context" or mode != "nextTurn":
            raise ValueError("Slots require context nextTurn delivery")
    return {"role": role, "deliverAs": mode, **value}


def validate_reply(value: Any, pending_id: str) -> Any:
    if not isinstance(value, dict):
        raise ValueError("reply envelope must be an object")
    if isinstance(value.get("v"), bool) or value.get("v") != 1 or value.get("kind") != "reply":
        raise ValueError("Expected a version 1 reply envelope")
    reply_id = require_string(value.get("id"), "reply id")
    correlation_id = value.get("correlationId")
    if correlation_id != pending_id:
        raise ValueError("Reply does not correlate to the pending browser message")
    if "payload" not in value:
        raise ValueError("reply envelope requires payload")
    validate_payload(value["payload"])
    # Return the original object: payload keys, including constructor and __proto__,
    # are component data and are never merged into broker configuration.
    value["id"] = reply_id
    return value


@dataclass
class Connection:
    send: Any
