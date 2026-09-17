"""Static review contracts; these checks do not evaluate live agent behavior."""

from pathlib import Path

import pytest
import yaml

from automata.install.skills import bundled_skill_root, list_skill_dirs

ROOT = Path(bundled_skill_root())


def text(name: str) -> str:
    return next(ROOT.rglob(f"{name}/SKILL.md")).read_text()


def normalized(name: str) -> str:
    return " ".join(text(name).casefold().split())


@pytest.mark.parametrize(
    ("name", "required", "overbroad"),
    [
        ("automata-communication", "repairing misunderstandings", "communication quality matters"),
        ("automata-question", "consequential or ambiguous", "preparing a response"),
        ("automata-context-status", "model-token usage", "begins implementation"),
        ("automata-goal", "durable project goals", "status reports"),
    ],
)
def test_activation_describes_specialized_need(name, required, overbroad) -> None:
    description = yaml.safe_load(text(name).split("---", 2)[1])["description"]
    assert required in description
    assert overbroad not in description


@pytest.mark.parametrize(
    ("name", "terms"),
    [
        (
            "automata-web-browser-control",
            (
                "consult relevant saved setup knowledge first",
                "approved owner-scoped data",
                "live endpoints and process handles separate and temporary",
                "saved knowledge does not authorize future actions",
                "do not stop after each routine action",
            ),
        ),
        (
            "automata-pc-ui-control",
            (
                "consult relevant saved setup knowledge",
                "after setup discovery succeeds, save a verified recipe",
                "commands for target selection, input, feedback",
                "update the recipe after verification",
                "when continuity or recovery needs a live record",
                "saved knowledge does not grant permission",
            ),
        ),
        (
            "automata-agent-browser-bridge",
            (
                "consult relevant saved setup knowledge",
                "separate from live endpoint records",
                "do not retain pairing secrets as setup knowledge",
                "save verified startup, connection, status-check, and owned cleanup commands",
                "consult relevant saved setup knowledge before reconstructing commands",
                "exclude live session identifiers",
                "update the recipe after verification",
            ),
        ),
        (
            "automata-adaptive-ui",
            (
                "when setup requires discovery, save verified",
                "consult saved recipes before rediscovery",
                "do not duplicate builder help",
                "separate from live session handles",
                "recheck changed prerequisites",
                "the builder owns defaults and build mechanics",
            ),
        ),
    ],
)
def test_environment_skills_reuse_knowledge_without_trusting_live_handles(name, terms) -> None:
    body = normalized(name)
    for term in terms:
        assert term in body, term


def test_browser_setup_retains_a_verified_executable_recipe() -> None:
    body = normalized("automata-web-browser-control")
    for term in (
        "reuse its verified recipe rather than reconstructing commands",
        "after successful setup, save a reusable recipe",
        "verified launch or attach commands",
        "minimal control example",
        "connection checks, cleanup procedure",
        "working directories and variable inputs",
        "exclude secrets and browser content",
        "if absent, ask before saving",
        "report the recipe's location",
        "update the recipe after verifying a changed setup",
    ):
        assert term in body, term
    assert "automata-agent-data" not in body


def test_skill_design_keeps_recipes_conditional_and_separate_from_runtime_state() -> None:
    body = normalized("automata-skill-design")
    for term in (
        "when setup requires discovery or experimentation",
        "save a verified recipe in a suitable agent-data location",
        "within existing storage authority",
        "consult it before repeating discovery",
        "update the recipe after verification",
        "saved knowledge does not grant permission",
        "separate reusable setup knowledge from temporary runtime state",
        "do not mandate records or a universal schema",
        "judgment-only skills need no setup ceremony",
    ):
        assert term in body, term


@pytest.mark.parametrize("name", ["automata-python", "automata-javascript"])
def test_project_configuration_stays_authoritative(name: str) -> None:
    body = normalized(name)
    assert "project configuration and lockfiles as authoritative" in body
    assert "do not create a setup record merely" in body


def test_completion_is_not_first_draft_or_unbounded_polishing() -> None:
    development = normalized("automata-software-development")
    for term in (
        "fix failures caused by this change within scope",
        "a first implementation is not completion",
        "a blocker needs input",
        "the next action exceeds authority",
        "do not repair unrelated defects",
    ):
        assert term in development
    delegation = normalized("automata-delegation")
    assert "verifiable completion criteria" in delegation
    assert "authorized corrections, stopping boundaries, and required checks" in delegation


def test_instruction_configuration_avoids_repeated_setup_interviews() -> None:
    body = normalized("automata-agents-md")
    assert "without asking again for the same scope" in body
    assert "rather than repeating a full setup interview" in body
    assert "not a reading checklist before every edit" in body
    assert "instructions actually loaded by a session" in body


def test_image_generation_checks_authority_before_calling() -> None:
    body = text("automata-codex-imagegen")
    assert body.index("Establish authorization") < body.index("Call `codex_imagegen`")
    assert "one image" in body
    assert "agent-inferred image requires confirmation" in body


def test_task_design_is_the_only_bundled_name() -> None:
    names = list_skill_dirs(ROOT)
    assert "automata-task-design" in names
    assert "automata-work-design" not in names
    for skill in ROOT.rglob("SKILL.md"):
        assert "automata-work-design" not in skill.read_text(), skill
    body = normalized("automata-task-design")
    assert "compare it with a simpler viable alternative" in body
    assert "without waiting to be asked why" in body
    assert "rather than redesigning merely to agree" in body
