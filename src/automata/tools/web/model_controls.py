"""Browser-safe projection of the native session's catalog and control state."""

from __future__ import annotations

import json
from pathlib import Path

SCOPE_EXTENSION = Path(__file__).with_name("native-model-scope.mjs")
SCOPE_KEY_ENV = "AUTOMATA_WEB_MODEL_SCOPE_KEY"
THINKING_LEVELS = frozenset({"off", "minimal", "low", "medium", "high", "xhigh", "max"})
CONTROLS_UNAVAILABLE = "Native model and thinking controls are unavailable."


def _text(value, limit):
    return isinstance(value, str) and 0 < len(value) <= limit and "\0" not in value


def model_summary(model):
    if not isinstance(model, dict):
        return None
    provider, model_id, name = (model.get(key) for key in ("provider", "id", "name"))
    if not _text(provider, 256) or not _text(model_id, 512):
        return None
    return {
        "provider": provider,
        "id": model_id,
        "name": name if _text(name, 512) else model_id,
    }


def model_key(model):
    return (model["provider"], model["id"])


def effective_thinking(level):
    return level if isinstance(level, str) and level in THINKING_LEVELS else None


def scope_from_status(text):
    if not isinstance(text, str) or len(text) > 128 * 1024:
        return None
    try:
        items = json.loads(text)
    except (ValueError, RecursionError):
        return None
    if not isinstance(items, list) or len(items) > 512:
        return None
    scope = {}
    for item in items:
        model = model_summary(item)
        if model is None or model_key(model) in scope:
            return None
        hint = effective_thinking(item.get("thinkingLevel"))
        # A future native thinking hint is not a reason to discard a valid model.
        scope[model_key(model)] = (model, hint)
    return scope


def available_thinking(data, current):
    levels = data.get("levels") if isinstance(data, dict) else None
    if (
        not isinstance(levels, list)
        or not levels
        or len(levels) > len(THINKING_LEVELS)
        or any(effective_thinking(level) is None for level in levels)
        or len(set(levels)) != len(levels)
        or current not in levels
    ):
        return []
    return levels
