"""Persistence envelopes, not component rendering schemas.

The JS registry/component owners validate rendering and submission contracts.
Python bounds opaque JSON and validates identities/state; unsupported components
remain safely displayable as visible fallbacks, never executable content.
"""
from __future__ import annotations

import json
import re
from typing import Any

IDENTIFIER = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")
STATUSES = {"draft", "pending", "forwarded", "attached", "completed", "failed", "uncertain"}


def validate_interaction(value: Any) -> None:
    if not isinstance(value, dict) or value.get("status") not in STATUSES:
        raise ValueError("Invalid interaction status")
    if "values" in value and (
        not isinstance(value["values"], dict)
        or any(not isinstance(item, str) or len(item) > 6000 for item in value["values"].values())
    ):
        raise ValueError("Invalid stored form values")
    for name in ("operationId", "participant", "sessionId"):
        if name in value and (
            not isinstance(value[name], str) or not IDENTIFIER.fullmatch(value[name])
        ):
            raise ValueError(f"Invalid interaction {name}")
    if "detail" in value and (not isinstance(value["detail"], str) or len(value["detail"]) > 1000):
        raise ValueError("Invalid interaction detail")


def validate_message(message: Any) -> None:
    if (
        not isinstance(message, dict)
        or message.get("role") not in {"user", "agent"}
        or not isinstance(message.get("text"), str)
        or len(message["text"]) > 6000
        or any(not isinstance(message.get(name), str) or not IDENTIFIER.fullmatch(message[name])
               for name in ("id", "operationId"))
    ):
        raise ValueError("Invalid message envelope")
    if "author" in message:
        author = message["author"]
        if (not isinstance(author, dict) or author.get("agentId") != "agent-automata"
                or author.get("participant") != "workspace-agent"
                or not isinstance(author.get("sessionId"), str)
                or not IDENTIFIER.fullmatch(author["sessionId"])):
            raise ValueError("Invalid assigned author identity")
    content = message.get("content")
    if content is not None:
        if not isinstance(content, list) or not 1 <= len(content) <= 16:
            raise ValueError("Invalid content envelope")
        if len(json.dumps(content, ensure_ascii=False, allow_nan=False).encode()) > 24000:
            raise ValueError("Content envelope too large")
        ids = set()
        for item in content:
            if (not isinstance(item, dict)
                or not isinstance(item.get("id"), str) or not IDENTIFIER.fullmatch(item["id"])
                or item["id"] in ids or not isinstance(item.get("type"), str)
                or type(item.get("version")) is not int or not isinstance(item.get("data"), dict)):
                raise ValueError("Invalid component envelope")
            ids.add(item["id"])
        interactions = message.get("interactions", {})
        if not isinstance(interactions, dict) or not set(interactions).issubset(ids):
            raise ValueError("Invalid interaction identity")
        for interaction in interactions.values():
            validate_interaction(interaction)
    if "delivery" in message:
        validate_interaction(message["delivery"])


def normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    """Additive v2 compatibility: preserve original text and all existing fields."""
    if "content" not in message:
        return {**message, "content": [{"id": "legacy-text", "type": "text", "version": 1,
                                       "data": {"text": message["text"]}}],
                "provenance": "historical-simulation"}
    return message
