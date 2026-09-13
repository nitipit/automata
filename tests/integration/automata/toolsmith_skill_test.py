"""Check tool placement guidance without creating or moving runtime tools."""

from importlib.resources import files


def toolsmith() -> str:
    return " ".join(
        files("automata")
        .joinpath("skills", "skill-ops", "automata-toolsmith", "SKILL.md")
        .read_text()
        .split()
    )


def test_toolsmith_separates_concerns_without_requiring_directories() -> None:
    text = toolsmith()
    for term in (
        "tool's purpose, intended owner, and project conventions",
        "does not automatically own the tools it creates",
        "three concerns, not three mandatory directories",
        "**Source:**",
        "**Installed copy:**",
        "**Runtime state:**",
        "Change maintained source and reinstall rather than patching installed copies",
        "Stateless tools need no state directory",
        "without an installed copy",
        "do not move existing files or create unused directories",
    ):
        assert term in text, term
    assert "By default, create agent-built tools under" not in text


def test_toolsmith_keeps_automata_paths_contextual() -> None:
    text = toolsmith()
    for term in (
        "`src/automata/tools/<name>/`",
        "`.agents/tools/<name>/`",
        "`.agents/var/tools/<name>/`",
        "unless an explicit data convention overrides it",
        "not a required layout for other projects",
        "that skill's `scripts/`",
        "an approved disposable location for temporary helpers",
    ):
        assert term in text, term


def test_toolsmith_does_not_require_artificial_skill_ownership() -> None:
    text = toolsmith()
    assert "When a skill owns usage judgment" in text
    assert "A stand-alone tool may instead provide sufficient direct CLI documentation" in text
    assert "an applicable skill mapping or sufficient direct CLI documentation" in text
    assert "without a meaningful owning skill" not in text
