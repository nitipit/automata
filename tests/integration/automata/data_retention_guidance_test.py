"""Guard shared retention responsibilities without imposing capability-specific quotas."""

from importlib.resources import files

ROOT = files("automata").joinpath("skills")


def test_agent_data_owns_contextual_growth_and_cleanup_guidance() -> None:
    text = ROOT.joinpath("core", "automata-agent-data", "SKILL.md").read_text()
    normalized = " ".join(text.casefold().split())
    for term in (
        "accumulation warrants a retention review",
        "distinguish rebuildable caches and disposable outputs from durable decisions",
        "age alone does not establish that data is safe to remove",
        "data owner's agreed growth and retention policy",
        "not recursive scans on every write",
        "avoid repeating unchanged notices",
        "no universal file count, age, or byte quota",
        "a soft review threshold from a hard limit",
        "a reminder does not stop growth",
        "a clear scoped removal request or agreed automatic-retention policy",
        "a growth notice cannot",
        "prefer recoverable removal",
        "do not delete active data",
        "ask before consolidating or relocating durable data",
    ):
        assert term in normalized, term
    assert len(text) < 5_000
    assert "automata-time-estimation" not in text
    assert "automata-worklog" not in text


def test_task_workspace_is_a_disposable_fallback_not_a_fixed_ui_layout() -> None:
    text = ROOT.joinpath("core", "automata-agent-data", "SKILL.md").read_text()
    normalized = " ".join(text.casefold().split())
    for term in (
        "when no suitable task location is established",
        ".agents/var/workspace/<task-name>/",
        "choose layout from the task and context",
        "a fallback, not a mandatory directory template",
        "keep capability-owned state in its own namespace",
        "fresh repository operation must not depend on it",
        "stop its owned processes before cleanup",
        "choose ui output and serving roots as needed",
        "credentials and private state outside the served root",
        "the entire workspace is not implicitly a public website",
    ):
        assert term in normalized, term
    assert "<task-name>/public" not in text


def test_skill_design_requires_retention_design_without_a_named_skill_chain() -> None:
    text = ROOT.joinpath("skill-ops", "automata-skill-design", "SKILL.md").read_text()
    normalized = " ".join(text.casefold().split())
    for term in (
        "for accumulating data or runtime resources",
        "establish growth/retention review, cleanup authority",
        "distinguish disposable material from needed evidence",
        "review thresholds from deletion permission",
        "a terminal status alone does not prove inactivity",
        "automatic deletion needs an agreed policy",
        "avoid universal quotas or checks on every write",
        "put concurrency and deletion safeguards in tools",
    ):
        assert term in normalized, term
    assert "automata-agent-data" not in text
