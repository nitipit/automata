"""Installed guidance boundaries; live usability is evaluated separately."""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[3] / "src" / "automata"
SKILL = ROOT / "skills/operations/automata-agent-router/SKILL.md"


def test_bridge_skill_maps_shipped_implementation_and_clean_start_guidance() -> None:
    text = SKILL.read_text()
    _, raw, body = text.split("---\n", 2)
    frontmatter = yaml.safe_load(raw)
    body = " ".join(body.split())
    assert frontmatter["name"] == "automata-agent-router"
    assert frontmatter["metadata"]["automata-tools"] == (
        ".agents/tools/agent-router/agent_router.py"
    )
    for term in (
        "status, intended endpoints and ownership",
        "`serve` starts the listener",
        "current session",
        "server rather than regenerating",
        "Components own payload and reply semantics",
        "exact message ID as `replyTo`",
        "canonical message/tool-call records",
        "does not grant authority",
        "component handling",
        "Do not silently replay an uncertain",
        "stop only owned router services",
        "does not authorize deleting",
        "## Boundaries",
        "`nextTurn` queues data for the next prompt",
        "`inspect_context` or `clear_context`",
        "buffered, queued, and attached receipts",
        "explicit authorized `to`",
        "Static hosting is optional",
        "not page directories",
        "permission to delegate work",
    ):
        assert term in body
    for unrelated_detail in (
        "lib/example/chat-with-agent.html",
        "{text, context}",
        ".agents/var/skills/automata-adaptive-ui",
    ):
        assert unrelated_detail not in body
    assert not (ROOT / "tools/ui-channel").exists()
    assert not (ROOT / "extensions/ui-channel.ts").exists()
    assert not (ROOT / "skills/operations/automata-ui-channel-setup").exists()
