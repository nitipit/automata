from automata.tools.team.panels import agent_panel, label_value_grid
from automata.tools.team.view import report_projection
from tests.tools.team.conftest import report


def test_headerless_grid_wraps_values_under_values():
    rendered = label_value_grid(
        [
            ("Agent", "one two three four five six seven"),
            ("Summary", "A factual long summary for this current work."),
        ],
        30,
    )
    lines = rendered.plain.splitlines()
    assert lines[0].startswith("Agent   one")
    assert any(line.startswith("        ") and line.strip() for line in lines)
    assert not any("│" in line or "┃" in line for line in lines)
    assert sum(line.startswith("Summary") for line in lines) == 1
    for line in lines:
        if not line.startswith(("Agent", "Summary")):
            assert line.startswith("        ")


def test_agent_panel_uses_shared_projection_without_tasks_or_counts(graph):
    graph["agents"]["alice"]["report"] = report("Explicit own current work")
    path, panel = agent_panel(graph, "alice", 71)
    assert path == "Manager / Alice"
    assert "Shared goal" not in panel.plain + path
    for label in ("Agent", "Summary", "Status", "Time", "Usage"):
        assert sum(line.startswith(label) for line in panel.plain.splitlines()) == 1
    assert report_projection(graph["agents"]["alice"])["summary"] in panel.plain
    assert "unavailable tokens" in panel.plain
    assert "Implement slice" not in panel.plain and "tasks" not in panel.plain
    graph.pop("tasks")
    assert agent_panel(graph, "alice", 71)[1].plain == panel.plain
