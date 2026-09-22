"""Bounded Choice request/response contracts; no credentials or network access."""

from __future__ import annotations

import hashlib
import json
import math
import re

MODEL = "jev-1.13.0"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MAX_INPUT_BYTES = 16_384
MAX_RESPONSE_BYTES = 262_144
MAX_MODEL_TOKENS = 65_536
INPUT_USD_PER_MILLION = 0.042
RESERVED_USD = MAX_MODEL_TOKENS * INPUT_USD_PER_MILLION / 1_000_000
PRICE_CHECKED = "2026-09-22"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")


class JevError(ValueError):
    """Messages must be fixed explanations, never input, credentials or server text."""

    def __init__(self, code: str, message: str, outcome: str = "not_sent") -> None:
        super().__init__(message)
        self.code = code
        self.outcome = outcome


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise JevError(code, message)


def _object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _constant(_value: str) -> None:
    raise ValueError("non-finite JSON number")


def decode(raw: bytes) -> object:
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=_constant)
    except (ValueError, RecursionError):
        raise JevError(
            "invalid_json", "Expected UTF-8 JSON without duplicate keys or NaN."
        ) from None


def _content(value: object) -> bool:
    return isinstance(value, (str, dict, list)) and bool(value)


def _identifier(value: object) -> bool:
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def validate_request(data: object) -> bytes:
    require(isinstance(data, dict), "request_schema", "Request must be a JSON object.")
    require(
        set(data) == {"model", "state", "questions"},
        "request_schema",
        "Request must contain only model, state and questions.",
    )
    require(
        data["model"] == MODEL,
        "unsupported_model",
        "Only pinned jev-1.13.0 is supported; aliases have no fixed pricing contract.",
    )
    require(
        _content(data["state"]), "request_schema", "State must be nonempty text, object or array."
    )
    questions = data["questions"]
    require(
        isinstance(questions, dict) and 1 <= len(questions) <= 16,
        "request_schema",
        "Supply 1 to 16 named Choice questions.",
    )
    for identity, question in questions.items():
        require(_identifier(identity), "request_schema", "Question IDs must be bounded ASCII IDs.")
        require(
            isinstance(question, dict) and set(question) == {"type", "instructions", "criteria"},
            "request_schema",
            "Each question needs only type, instructions and criteria.",
        )
        require(question["type"] == "choice", "unsupported_type", "Only Choice is supported.")
        require(
            _content(question["instructions"]),
            "request_schema",
            "Instructions must be nonempty text, object or array.",
        )
        criteria = question["criteria"]
        require(
            isinstance(criteria, dict) and 2 <= len(criteria) <= 255,
            "request_schema",
            "Each Choice needs 2 to 255 options.",
        )
        for option, description in criteria.items():
            require(_identifier(option), "request_schema", "Option IDs must be bounded ASCII IDs.")
            require(
                description is None or isinstance(description, (str, dict, list)),
                "request_schema",
                "Option criteria must be text, object, array or null.",
            )
    try:
        body = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise JevError("invalid_json", "Request contains unsupported JSON values.") from None
    require(len(body) <= MAX_INPUT_BYTES, "input_limit", "Request exceeds the 16 KiB client limit.")
    return body


def preflight(data: object, max_cost_usd: float | None, timeout: float) -> tuple[bytes, dict]:
    body = validate_request(data)
    require(
        type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 120,
        "invalid_timeout",
        "HTTP operation timeout must be finite, above 0 and at most 120s.",
    )
    if max_cost_usd is not None:
        require(
            type(max_cost_usd) in (int, float)
            and math.isfinite(max_cost_usd)
            and max_cost_usd >= RESERVED_USD,
            "budget_too_small",
            "Budget must cover the pinned model's conservative full-context reservation.",
        )
    plan = {
        "model": MODEL,
        "endpoint": ENDPOINT,
        "request_sha256": hashlib.sha256(body).hexdigest(),
        "request_bytes": len(body),
        "question_count": len(data["questions"]),
        "maximum_requests": 1,
        "retries": 0,
        "timeout_seconds_per_operation": timeout,
        "max_cost_usd": max_cost_usd,
        "reserved_list_cost_usd": RESERVED_USD,
        "input_usd_per_million": INPUT_USD_PER_MILLION,
        "output_usd_per_million": 0,
        "price_checked": PRICE_CHECKED,
        "price_source": "https://docs.typesafe.ai/models",
        "budget_scope": "one invocation; list-price estimate, not a provider billing cap",
    }
    return body, plan


def _probability(value: object) -> bool:
    return type(value) in (int, float) and 0 <= value <= 1 and math.isfinite(value)


def validate_response(data: object, request: dict) -> dict:
    require(
        isinstance(data, dict) and data.get("model") == request["model"],
        "response_model",
        "Response did not identify the exact requested model.",
    )
    answers = data.get("answers")
    require(
        isinstance(answers, dict) and set(answers) == set(request["questions"]),
        "response_schema",
        "Response question IDs do not match the request.",
    )
    clean = {}
    for identity, question in request["questions"].items():
        answer = answers[identity]
        require(
            isinstance(answer, dict) and answer.get("type") == "choice",
            "response_schema",
            "Expected a typed Choice answer.",
        )
        probabilities = answer.get("probabilities")
        require(
            isinstance(probabilities, dict)
            and set(probabilities) == set(question["criteria"])
            and all(_probability(p) for p in probabilities.values())
            and abs(sum(probabilities.values()) - 1) <= 0.020000001,
            "response_schema",
            "Invalid Choice probability distribution.",
        )
        pick = answer.get("choice")
        require(
            isinstance(pick, str)
            and pick in probabilities
            and probabilities[pick] >= max(probabilities.values()) - 1e-9,
            "response_schema",
            "Choice is not a maximum-probability declared option.",
        )
        require(
            _probability(answer.get("confidence")),
            "response_schema",
            "Choice confidence must be a finite number between zero and one.",
        )
        clean[identity] = {
            "type": "choice",
            "choice": pick,
            "probabilities": probabilities,
            "confidence": answer["confidence"],
        }
    usage = data.get("usage")
    require(
        isinstance(usage, dict)
        and all(
            type(usage.get(k)) is int and usage[k] >= 0 for k in ("input_tokens", "output_tokens")
        ),
        "response_usage",
        "Invalid token usage.",
    )
    require(
        usage["input_tokens"] <= MAX_MODEL_TOKENS,
        "pricing_contract_changed",
        "Reported input usage exceeds the pinned pricing reservation; inspect billing.",
    )
    return {
        "model": data["model"],
        "answers": clean,
        "usage": {k: usage[k] for k in ("input_tokens", "output_tokens")},
    }
