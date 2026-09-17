"""Check cue guidance boundaries, not live recall or token savings."""

from importlib.resources import files

SKILL = files("automata").joinpath("skills", "core", "automata-cue", "SKILL.md")


def test_cues_keep_short_recall_notes_with_examples() -> None:
    text = SKILL.read_text()
    normalized = " ".join(text.casefold().split())
    for term in (
        "quick notes",
        "not complete memory, an authoritative instruction, or the source of truth",
        "one idea per markdown bullet",
        "15–40 words excluding its timestamp and source pointer",
        "soft target: recall matters more than word count",
        "leave changing task status in its existing owner records",
        "actual save-time iso 8601 timestamp and utc offset",
        "source pointer when needed",
        "verify consequential claims at their source",
        "useful:",
        "too much:",
        "example timestamps are illustrative",
    ):
        assert term in normalized, term
    assert len(text) < 3_400  # Includes durable-instruction recognition and scope selection.


def test_cue_save_authority_includes_default_file_creation() -> None:
    normalized = " ".join(SKILL.read_text().casefold().split())
    for term in (
        "read relevant cues when they help orientation",
        "revise a matching note rather than duplicating it",
        "a request to remember, a clearly lasting user instruction, or approved automatic capture",
        "follow an established destination or data convention for that scope",
        "global preferences: `~/.agents/var/skills/automata-cue/cues.md`",
        "project-specific knowledge: `.agents/var/skills/automata-cue/cues.md`",
        "authorizes creating the missing default file and parent directories",
        "no separate file-creation approval is needed",
        "clarify conflicting notes or sensitive content before saving",
        "preserve the surrounding file's structure",
    ):
        assert term in normalized, term


def test_cue_recognizes_durable_intent_without_keyword_only_capture() -> None:
    normalized = " ".join(SKILL.read_text().casefold().split())
    for term in (
        "“always,” “from now on,” and “make this our convention”",
        "when context establishes a future rule—not merely when those words occur",
        "do not require the phrase “remember this.”",
        "incidental remarks, one-off directions, and task completion alone do not authorize saving",
    ):
        assert term in normalized, term


def test_cue_selects_scope_before_destination() -> None:
    normalized = " ".join(SKILL.read_text().casefold().split())
    for term in (
        "choose scope before location",
        "a repo discussion supports saving repo-specific conventions locally",
        "use global scope only when cross-project intent is clear",
        "ask before writing if intent or scope is unclear",
    ):
        assert term in normalized, term


def test_cue_maintenance_preserves_cleanup_and_privacy_boundaries() -> None:
    normalized = " ".join(SKILL.read_text().casefold().split())
    for term in (
        "do not store secrets or raw transcripts",
        "edit instruction files merely to remember a convention",
        "remove notes only with scoped authorization",
        "prefer recoverable removal",
        "never delete their referenced sources",
        "does not erase conversation history",
        "delegated agents return cue candidates to their owner",
    ):
        assert term in normalized, term
