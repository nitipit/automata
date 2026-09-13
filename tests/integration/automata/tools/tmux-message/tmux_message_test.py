from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

TOOL_PATH = (
    Path(__file__).parents[5]
    / "src"
    / "automata"
    / "tools"
    / "tmux-message"
    / "tmux_message.py"
)


def load_tool_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("automata_tmux_message_tool", TOOL_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pane_description(*, in_mode: bool) -> str:
    return "\x1f".join(("%7", "worker:0.0", "0", str(int(in_mode)), "pi"))


def test_delivery_interrupts_mode_before_payload_and_enter() -> None:
    tool = load_tool_module()
    calls: list[tuple[str, ...]] = []
    pane_states = iter(
        (
            pane_description(in_mode=True),
            pane_description(in_mode=False),
            pane_description(in_mode=True),
            pane_description(in_mode=False),
        )
    )
    sleeps: list[float] = []

    def run_tmux(arguments: tuple[str, ...]) -> str:
        calls.append(arguments)
        if arguments[0] == "display-message":
            return next(pane_states)
        return ""

    receipt = tool.deliver_message(
        target="worker:0.0",
        message="DONE task-123",
        owned_pane=True,
        run_tmux=run_tmux,
        sleep=sleeps.append,
    )

    assert receipt.status == "sent"
    assert receipt.mode_interruptions == 2
    assert receipt.current_command == "pi"
    assert sleeps == [0.1]
    assert calls == [
        ("display-message", "-p", "-t", "worker:0.0", tool.PANE_FORMAT),
        ("send-keys", "-t", "worker:0.0", "-X", "cancel"),
        ("display-message", "-p", "-t", "worker:0.0", tool.PANE_FORMAT),
        ("send-keys", "-t", "worker:0.0", "-l", "DONE task-123"),
        ("display-message", "-p", "-t", "worker:0.0", tool.PANE_FORMAT),
        ("send-keys", "-t", "worker:0.0", "-X", "cancel"),
        ("display-message", "-p", "-t", "worker:0.0", tool.PANE_FORMAT),
        ("send-keys", "-t", "worker:0.0", "Enter"),
    ]


def test_delivery_requires_explicit_ownership() -> None:
    tool = load_tool_module()

    with pytest.raises(tool.DeliveryError, match="--owned-pane is required"):
        tool.deliver_message(
            target="worker:0.0",
            message="READY task-123",
            owned_pane=False,
            run_tmux=lambda _: "",
        )


def test_delivery_rejects_multiline_payload() -> None:
    tool = load_tool_module()

    with pytest.raises(tool.DeliveryError, match="message must be one line"):
        tool.deliver_message(
            target="worker:0.0",
            message="first\nsecond",
            owned_pane=True,
            run_tmux=lambda _: "",
        )
