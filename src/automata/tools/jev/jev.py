#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["cyclopts>=4.11.1"]
# ///
"""Explicit, optional Jev Choice calls; no routing or execution authority."""

from __future__ import annotations

import http.client
import json
import os
import ssl
import sys
import time
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter
from jev_contract import (
    INPUT_USD_PER_MILLION,
    MAX_INPUT_BYTES,
    MAX_RESPONSE_BYTES,
    MODEL,
    JevError,
    decode,
    preflight,
    require,
    validate_response,
)

app = App(
    name="jev",
    help=(
        "Optional typed judgments through TypeSafe Jev. Choice only; no browser control, "
        "skill loading or autonomous routing. 'judge' is offline unless --execute is supplied. "
        "Each execution sends one HTTPS request to api.typesafe.ai, with no redirects, retries, "
        "proxy-environment use or fallback providers. No operational state, inference cache or "
        "credential files are created. JSON on stdout; structured errors on stderr. "
        "Use 'schema' for the request contract. Requires Python 3.12+ and Cyclopts."
    ),
)


def read_input(source: str) -> object:
    try:
        if source == "-":
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with Path(source).open("rb") as stream:
                raw = stream.read(MAX_INPUT_BYTES + 1)
    except OSError:
        raise JevError("input_read", "Cannot read the explicit request file or stdin.") from None
    require(len(raw) <= MAX_INPUT_BYTES, "input_limit", "Input file exceeds the 16 KiB limit.")
    return decode(raw)


def read_key(key_file: Path | None) -> str:
    """Explicit file takes precedence; never discover files or expose key text."""
    try:
        if key_file is not None:
            with key_file.expanduser().open("rb") as stream:
                raw = stream.read(4097)
            require(
                len(raw) <= 4096, "credential_format", "Credential file exceeds the size limit."
            )
            key = raw.decode("ascii").strip()
        else:
            key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    except (OSError, UnicodeError):
        raise JevError(
            "credential_read", "Cannot read the explicitly selected credential file."
        ) from None
    require(
        0 < len(key) <= 4096 and all(33 <= ord(c) <= 126 for c in key),
        "credential_format",
        "Supply a plain token via --key-file or TYPESAFE_API_KEY.",
    )
    return key


def evaluate(request: dict, body: bytes, key: str, timeout: float) -> dict:
    """One call, even after an uncertain outcome. Returned data is allowlisted."""
    require(
        key.encode("ascii") not in body,
        "credential_in_input",
        "The selected credential also occurs in the request; nothing was sent.",
    )
    connection = http.client.HTTPSConnection(
        "api.typesafe.ai", timeout=timeout, context=ssl.create_default_context()
    )
    started = time.monotonic()
    status = None
    try:
        connection.request(
            "POST",
            "/v1/systemone",
            body=body,
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Automata-Jev/1",
            },
        )
        response = connection.getresponse()
        status = response.status
        if status != 200:
            # Error bodies and headers may reflect input or credentials. Never render them.
            raise JevError(
                "provider_http_error",
                f"Provider returned HTTP {status}; no retry.",
                "response_received",
            )
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        require(len(raw) <= MAX_RESPONSE_BYTES, "response_limit", "Response exceeded 256 KiB.")
        result = validate_response(decode(raw), request)
        return {
            **result,
            "elapsed_seconds": round(time.monotonic() - started, 4),
            "estimated_list_cost_usd": result["usage"]["input_tokens"]
            * INPUT_USD_PER_MILLION
            / 1_000_000,
        }
    except JevError as exc:
        exc.outcome = "response_received" if status is not None else "outcome_unknown"
        raise
    except (
        OSError,
        http.client.HTTPException,
        ValueError,
        OverflowError,
        RecursionError,
        KeyboardInterrupt,
    ):
        raise JevError(
            "transport_or_decode_error",
            "Request failed or was interrupted; it may have been billed. No retry.",
            "response_received" if status is not None else "outcome_unknown",
        ) from None
    finally:
        connection.close()


@app.command
def schema() -> None:
    """Print an offline request example, client limits and execution semantics."""
    print(
        json.dumps(
            {
                "example": {
                    "model": MODEL,
                    "state": {
                        "goal": "Find public product information",
                        "observed_actions": {"a1": "Products navigation", "a2": "Help navigation"},
                    },
                    "questions": {
                        "candidate": {
                            "type": "choice",
                            "instructions": "Which observed action best matches the goal?",
                            "criteria": {
                                "a1": "View products",
                                "a2": "Read help",
                                "none": "Neither action fits or the observation is insufficient",
                            },
                        }
                    },
                },
                "required_request_keys": ["model", "state", "questions"],
                "required_question_keys": ["type", "instructions", "criteria"],
                "limits": {
                    "input_bytes": MAX_INPUT_BYTES,
                    "questions": [1, 16],
                    "options": [2, 255],
                    "ids": "1–128 ASCII letters/digits/underscore/dot/hyphen; start alphanumeric",
                    "state_and_instructions": "nonempty text, object or array",
                    "criteria_values": "text, object, array or null",
                    "types": ["choice"],
                    "models": [MODEL],
                },
                "semantics": [
                    "Judge without --execute validates locally; no credentials or network needed.",
                    "--execute attests paid-call AND data-export authorization for this request.",
                    "Execution needs --max-cost-usd covering the full-context reserve.",
                    "Reservation uses documented list pricing, not an invoice guarantee.",
                    "Budgets are per invocation; the caller tracks cumulative spending.",
                    "Probabilities and confidence are model outputs, never permissions.",
                    "Probability sums within 0.02 of one are accepted unchanged; no normalization.",
                    "Timeout is per network operation, not a hard wall-clock deadline.",
                    "Outcome-unknown errors may be billed; don't automatically repeat the request.",
                    "No task state or persistent process is retained. Python may cache bytecode.",
                ],
            },
            indent=2,
        )
    )


@app.command
def judge(
    request: Annotated[
        str,
        Parameter(
            help="UTF-8 JSON file, or '-' for stdin (16 KiB maximum).", allow_leading_hyphen=True
        ),
    ],
    *,
    execute: Annotated[
        bool,
        Parameter(
            help=(
                "Send one paid request. Attest authorization to export this exact data and spend "
                "within the supplied limit. Omit for credential-free offline validation."
            )
        ),
    ] = False,
    key_file: Annotated[
        Path | None,
        Parameter(
            help=(
                "Explicit token file; otherwise TYPESAFE_API_KEY. No auto-discovery. Keep files "
                "owner-readable only and Git-ignored. Never put literal tokens on the command line."
            )
        ),
    ] = None,
    max_cost_usd: Annotated[
        float | None,
        Parameter(
            help=(
                "Per-call list-price budget; required for execution. Must cover $0.002752512 "
                "(65,536 tokens at $0.042/M), even for small requests. Caller tracks total spend."
            )
        ),
    ] = None,
    timeout: Annotated[
        float, Parameter(help="Per-network-operation timeout in seconds (0 < t <= 120).")
    ] = 20.0,
) -> None:
    """Validate a Choice request offline, or explicitly send it once.

    Results are JSON. Exit 0: valid offline plan or validated response; 2: preflight
    failure (not sent); 3: provider/transport/response failure (may be billed).
    Parser/usage errors also exit nonzero. Private input/answers require appropriate
    storage care when redirecting streams. Raw requests, keys and server error bodies
    are never logged. There is no automatic fallback, credential setup or account mutation.
    """
    plan = None
    try:
        data = read_input(request)
        body, plan = preflight(data, max_cost_usd, timeout)
        if not execute:
            result = {"status": "validated", "network_requests": 0, "plan": plan}
        else:
            require(
                max_cost_usd is not None,
                "budget_required",
                "Execution requires an explicit --max-cost-usd.",
            )
            key = read_key(key_file)
            result = {
                "status": "ok",
                "network_requests": 1,
                "plan": plan,
                **evaluate(data, body, key, timeout),
            }
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except JevError as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": exc.code,
                    "message": str(exc),
                    "outcome": exc.outcome,
                    "automatic_retry": False,
                    "reserved_list_cost_usd": plan["reserved_list_cost_usd"] if plan else None,
                }
            ),
            file=sys.stderr,
        )
        raise SystemExit(2 if exc.outcome == "not_sent" else 3) from None


if __name__ == "__main__":
    app()
