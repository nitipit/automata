"""Static ownership contracts and installation checks, not agent-behavior evaluation."""

from pathlib import Path

import pytest

from automata.character import compose_character
from automata.install.skills import bundled_skill_root, find_skill_dir, install_skills


def skill_text(name: str) -> str:
    return (find_skill_dir(bundled_skill_root(), name) / "SKILL.md").read_text()


def test_agent_design_is_a_small_capability_placement_contract() -> None:
    text = skill_text("automata-agent-design")
    normalized = " ".join(text.casefold().split())
    for term in (
        "deciding what belongs in character, behavior, skills, tools/runtime",
        "put each capability in the narrowest appropriate place",
        "keep fundamentals light and orienting",
        "**character:** identity and expression",
        "**behavior:** enduring orientation, judgment, and authority",
        "**skills:** context-activated expertise",
        "**tools/runtime:** executable mechanisms and observable signals",
        "**task context:** temporary goals",
        "missing capability, unclear placement, poor activation, or unreliable application",
        "without duplicating instructions or requiring a fixed skill chain",
        "recommendation does not authorize implementation or setup",
    ):
        assert term in normalized, term
    assert len(text) < 2_000


def test_work_design_owns_solo_team_arrangements_and_safe_redesign() -> None:
    text = skill_text("automata-work-design")
    normalized = " ".join(text.casefold().split())
    for term in (
        "organizing solo or team work involves meaningful choices",
        "not as a mandatory stage for every task",
        "one owner, fewer workers, or sequential work",
        "a full work plan is not required",
        "temporary responsibilities, not predefined roles",
        "delegating execution need not move the coordinator's design context",
        "shared versus isolated contexts",
        "ownership, dependencies, integration, and expected evidence",
        "initial delegation requires an approved envelope from the user or assigned parent",
        "launch, replacement, and rebalancing need no per-worker approval",
        "exceeding it requires explicit approval",
        "a safe transition as well as the new arrangement",
        "preserve partial results, keep ownership clear",
        "avoid concurrent writes or duplicate side effects",
        "handoff and recovery mechanics belong with delegation and management",
        "planning owns work decomposition and acceptance criteria",
        "delegation owns executable handoffs",
        "management recognizes redesign needs, enacts authorized changes",
        "does not launch or reassign workers",
        "not a mandatory skill chain",
    ):
        assert term in normalized, term
    assert len(text) < 6_000


def test_work_design_distinguishes_selected_supported_and_authorized_model_settings() -> None:
    normalized = " ".join(skill_text("automata-work-design").casefold().split())
    for term in (
        "every agent in the team, including the coordinator",
        "use known current settings or explicitly label unknown settings",
        "distinguish these from proposed worker settings",
        "include inherited defaults when known",
        "explain choices when they materially affect feasibility, cost, or authority",
        "distinguish **runtime capability** from **approved selection bounds**",
        "effort levels are not automatically permitted choices",
        "preserve allowed sets and discrete effort choices",
        "do not guess unknown settings or treat missing authority as unlimited",
        "delegation owns executable handoffs and verifies launched settings",
    ):
        assert term in normalized, term


def test_work_design_uses_delivery_tradeoffs_without_research_ceremony() -> None:
    normalized = " ".join(skill_text("automata-work-design").casefold().split())
    for term in (
        "context ownership, total cost, completion time, and risk",
        "keep tightly coupled knowledge together",
        "briefing, duplicated context, review, retries, and integration in total cost",
        "dependencies and waiting in end-to-end completion time",
        "meet agreed acceptance criteria",
        "stronger models or more agents do not guarantee quality",
        "planning keeps the agreed acceptance criteria",
        "do not silently lower the standard",
        "use established user priorities",
        "recommend an approach, explain its concrete consequence, and ask what matters most",
        "not as a routine questionnaire",
        "context distribution remains the agent's engineering decision",
        "adapt within agreed priorities without repeatedly asking",
        "let model choices and work distribution inform each other",
        "reuse relevant research or task evidence",
        "suggest focused research when missing or stale comparative evidence",
        "missing research alone does not require investigation",
        "separate vendor claims, observed results, and unknowns",
        "diagrams are optional",
        "not the full working analysis",
    ):
        assert term in normalized, term
    assert "show two compact plain-text diagrams" not in normalized


@pytest.mark.parametrize("name", ["automata-agent-design", "automata-work-design"])
def test_design_skills_install_independently(tmp_path: Path, name: str) -> None:
    target = tmp_path / "skills"
    results = install_skills(target_root=target, skill_names=[name])
    assert [result.name for result in results] == [name]
    installed = target / name
    assert not installed.is_symlink()
    assert (installed / "SKILL.md").read_text() == skill_text(name)
    assert list(tmp_path.iterdir()) == [target]
    assert list(target.iterdir()) == [installed]
    assert list(installed.iterdir()) == [installed / "SKILL.md"]


def test_delegation_transfers_work_without_treating_replacement_as_acceptance() -> None:
    normalized = " ".join(skill_text("automata-delegation").casefold().split())
    for term in (
        "initial delegation requires explicit user or assigned parent approval",
        "launch, replacement, and rebalancing need no per-worker approval",
        "if authority is missing or the assignment exceeds it, obtain approval",
        "task approval alone does not imply unrestricted delegation",
        "preserve partial results and pending decisions",
        "resolve outstanding writes or side effects before releasing the old owner",
        "a replacement launch alone is not a completed handoff",
    ):
        assert term in normalized, term


def test_fundamental_behavior_stays_short_and_question_activation_is_prospective() -> None:
    output = compose_character(behaviors=["co-pilot"])
    coordination = output.split("Choose solo work", 1)[1].split("\n\n", 1)[0]
    interaction = output.split("# Base Behavior\n", 1)[1].split("\n# Behavior:", 1)[0]
    assert len(coordination) < 400
    assert len(interaction) < 800
    normalized = " ".join(interaction.split())
    assert "Ask clear questions only when uncertainty affects the answer or action" in normalized
    assert "Do not add unnecessary questions" in normalized
    for mechanics in ("watchdog", "child_limit", "model", "envelope", "automata-"):
        assert mechanics not in coordination
        assert mechanics not in interaction
    question = skill_text("automata-question")
    assert (
        "description: Use when preparing a response that asks the user for input, including "
        "clarification, discussion, choices, feedback, confirmation, or permission to act."
    ) in question
    autonomous = compose_character(behaviors=["autonomous"])
    assert "# Base Behavior" in autonomous
    assert "use numbered choices when helpful" in " ".join(autonomous.split())
