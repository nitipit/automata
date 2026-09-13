#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["cyclopts>=3.0.0"]
# ///
"""Deliver a bounded literal message to an explicitly owned tmux agent pane."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Annotated

from cyclopts import App, Parameter

DEFAULT_ENTER_DELAY = 0.1
DEFAULT_MODE_TIMEOUT = 0.5
MAX_MESSAGE_BYTES = 16_384
EXACT_TARGET = re.compile(r"^[^:]+:\d+\.\d+$")
app = App(
    name="tmux-message",
    help=(
        "Deliver one bounded literal message to an explicitly owned tmux agent pane. "
        "Delivery interrupts tmux copy or scroll mode before the payload and again before "
        "Enter, uses literal input with bounded pacing, and prints a JSON transport receipt. "
        "A sent receipt does not prove that the receiving agent processed or accepted the "
        "message. Never attest ownership for unrelated, user-owned, or unknown panes."
    ),
)

PANE_FORMAT = "\x1f".join(
    (
        "#{pane_id}",
        "#{session_name}:#{window_index}.#{pane_index}",
        "#{pane_dead}",
        "#{pane_in_mode}",
        "#{pane_current_command}",
    )
)

RunTmux = Callable[[Sequence[str]], str]
Sleep = Callable[[float], None]


class DeliveryError(ValueError):
    """A delivery precondition or tmux operation failed."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class PaneState:
    pane_id: str
    target: str
    dead: bool
    in_mode: bool
    current_command: str


@dataclass(frozen=True)
class DeliveryReceipt:
    status: str
    target: str
    pane_id: str
    current_command: str
    mode_interruptions: int
    enter_delay: float
    message_bytes: int


def subprocess_tmux(command: str) -> RunTmux:
    def run(arguments: Sequence[str]) -> str:
        try:
            completed = subprocess.run(
                [command, *arguments],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise DeliveryError("tmux_unavailable", f"tmux command not found: {command}") from error
        except subprocess.CalledProcessError as error:
            detail = error.stderr.strip() or error.stdout.strip() or "tmux command failed"
            raise DeliveryError("tmux_failed", detail) from error
        return completed.stdout.rstrip("\n")

    return run


def inspect_pane(target: str, run_tmux: RunTmux) -> PaneState:
    output = run_tmux(("display-message", "-p", "-t", target, PANE_FORMAT))
    fields = output.split("\x1f")
    if len(fields) != 5:
        raise DeliveryError("invalid_tmux_response", "tmux returned an unexpected pane description")
    pane_id, resolved_target, pane_dead, pane_in_mode, current_command = fields
    return PaneState(
        pane_id=pane_id,
        target=resolved_target,
        dead=pane_dead == "1",
        in_mode=pane_in_mode != "0",
        current_command=current_command,
    )


def require_live_pane(state: PaneState) -> None:
    if state.dead:
        raise DeliveryError("pane_dead", f"target pane is dead: {state.target}")


def interrupt_mode(
    target: str,
    run_tmux: RunTmux,
    sleep: Sleep,
    mode_timeout: float,
) -> tuple[PaneState, bool]:
    state = inspect_pane(target, run_tmux)
    require_live_pane(state)
    if not state.in_mode:
        return state, False

    run_tmux(("send-keys", "-t", target, "-X", "cancel"))
    deadline = time.monotonic() + mode_timeout
    while True:
        state = inspect_pane(target, run_tmux)
        require_live_pane(state)
        if not state.in_mode:
            return state, True
        if time.monotonic() >= deadline:
            raise DeliveryError(
                "pane_mode_persisted",
                f"target pane remained in tmux mode after interruption: {state.target}",
            )
        sleep(min(0.02, mode_timeout))


def deliver_message(
    *,
    target: str,
    message: str,
    owned_pane: bool,
    enter_delay: float = DEFAULT_ENTER_DELAY,
    mode_timeout: float = DEFAULT_MODE_TIMEOUT,
    run_tmux: RunTmux,
    sleep: Sleep = time.sleep,
) -> DeliveryReceipt:
    if not owned_pane:
        raise DeliveryError("ownership_required", "--owned-pane is required")
    if not EXACT_TARGET.fullmatch(target):
        raise DeliveryError(
            "invalid_target",
            "target must use exact session:window.pane format",
        )
    if not message:
        raise DeliveryError("empty_message", "message must not be empty")
    if "\n" in message or "\r" in message or "\x00" in message:
        raise DeliveryError("invalid_message", "message must be one line without NUL bytes")
    message_bytes = len(message.encode())
    if message_bytes > MAX_MESSAGE_BYTES:
        raise DeliveryError(
            "message_too_large",
            f"message exceeds {MAX_MESSAGE_BYTES} UTF-8 bytes",
        )
    if enter_delay < 0:
        raise DeliveryError("invalid_delay", "--enter-delay must not be negative")
    if mode_timeout <= 0:
        raise DeliveryError("invalid_timeout", "--mode-timeout must be positive")

    initial, interrupted_before = interrupt_mode(target, run_tmux, sleep, mode_timeout)
    run_tmux(("send-keys", "-t", target, "-l", message))
    sleep(enter_delay)
    before_enter, interrupted_after = interrupt_mode(target, run_tmux, sleep, mode_timeout)
    run_tmux(("send-keys", "-t", target, "Enter"))

    return DeliveryReceipt(
        status="sent",
        target=before_enter.target,
        pane_id=before_enter.pane_id,
        current_command=initial.current_command,
        mode_interruptions=int(interrupted_before) + int(interrupted_after),
        enter_delay=enter_delay,
        message_bytes=message_bytes,
    )


@app.command
def send(
    *,
    target: Annotated[
        str,
        Parameter(name="--target", help="Exact owned pane in session:window.pane format."),
    ],
    owned_pane: Annotated[
        bool,
        Parameter(
            name="--owned-pane",
            negative=False,
            help="Required ownership attestation; permits interrupting the target's tmux mode.",
        ),
    ] = False,
    message: Annotated[
        str,
        Parameter(help="One-line literal message."),
    ],
    enter_delay: Annotated[
        float,
        Parameter(help="Seconds to pace literal payload before Enter."),
    ] = DEFAULT_ENTER_DELAY,
    mode_timeout: Annotated[
        float,
        Parameter(help="Seconds allowed for an interrupted tmux mode to clear."),
    ] = DEFAULT_MODE_TIMEOUT,
    tmux_command: Annotated[
        str,
        Parameter(help="tmux executable; defaults to AUTOMATA_TMUX_COMMAND or tmux."),
    ] = os.environ.get("AUTOMATA_TMUX_COMMAND", "tmux"),
) -> None:
    """Interrupt tmux pane mode as needed, submit one message, and print a JSON receipt."""
    receipt = deliver_message(
        target=target,
        message=message,
        owned_pane=owned_pane,
        enter_delay=enter_delay,
        mode_timeout=mode_timeout,
        run_tmux=subprocess_tmux(tmux_command),
    )
    print(json.dumps(asdict(receipt), sort_keys=True))


def main() -> None:
    try:
        app()
    except DeliveryError as error:
        print(
            json.dumps({"status": "error", "reason": error.reason, "detail": str(error)}),
            file=sys.stderr,
        )
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
