"""Static implementation-guidance contracts, not agent-behavior evaluation."""

from automata.install.skills import bundled_skill_root, find_skill_dir, list_skill_dirs


def skill_text() -> str:
    root = find_skill_dir(bundled_skill_root(), "automata-software-development")
    return (root / "SKILL.md").read_text()


def test_contract_diffusion_is_retired_from_bundled_skills() -> None:
    assert "automata-contract-diffusion" not in list_skill_dirs(bundled_skill_root())


def test_development_resolves_uncertainty_with_representative_evidence() -> None:
    normalized = " ".join(skill_text().casefold().split())
    for term in (
        "before building on an uncertain assumption",
        "smallest executable check in a representative, authorized environment",
        "browser-dependent assumptions need real browser evidence",
        "pure logic may need only a direct test",
        "do not establish behavior of the boundaries they replace",
        "do not require a separate prototype for every change",
        "prove a minimal integrated path early, then extend it",
        "minimum protection needed to avoid an unintended capability",
    ):
        assert term in normalized, term


def test_documentation_explains_hidden_contracts_beside_the_owner() -> None:
    normalized = " ".join(skill_text().casefold().split())
    for term in (
        "contracts code alone does not reveal",
        "extension points, lifecycle order, invariants, side effects, and failure expectations",
        "beside the owning api",
        "language's documentation conventions",
        "use examples for composition",
        "do not restate signatures or obvious implementation",
    ):
        assert term in normalized, term


def test_architecture_scopes_implementation_through_logical_composition() -> None:
    normalized = " ".join(skill_text().casefold().split())
    for term in (
        "the plan aligns intent and constraints; it is not a file-editing checklist",
        "systems, subsystems, modules, and functions",
        "responsibility, local logic, and dependency contracts",
        "decompose or inspect deeper only where needed",
        "need not mirror directories",
        "interfaces, signatures, and focused comments",
        "do not require another design document",
        "state ownership, and important invariants",
        "leave internal implementation flexible",
        "implement coherent responsibilities, even across files",
        "parallelize where boundaries permit independence",
        "align affected owners and verify compatibility",
    ):
        assert term in normalized, term


def test_execution_is_adaptive_without_expanding_authority() -> None:
    normalized = " ".join(skill_text().casefold().split())
    workflow = skill_text().split("## Workflow\n", 1)[1].split("\n## ", 1)[0]
    for term in (
        "stable constraints with adaptive execution",
        "dependencies, uncertainty, and risk, not a universal sequence",
        "within approved scope without repeated confirmation",
        "keep planning proportional to the work",
        "rather than leaving integration until every module is finished",
        "relevant, credible new information",
        "changes assumptions, constraints, or available approaches",
        "adapt the implementation model or plan where useful",
        "preserving valid work rather than restarting by default",
        "explain material decisions when useful or asked",
        "do not expand product scope or add extra features without approval",
        "ask before changing public apis",
    ):
        assert term in normalized, term
    assert "\n1. " not in workflow
