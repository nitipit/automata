import copy
from typing import Any

import pytest

from automata.tools.team.hierarchy import agent_parents, agent_path, direct_reports
from automata.tools.team.view import (
    agent_cells,
    compact,
    context_cell,
    report_projection,
    seconds,
    summary_fields,
    table_columns,
    time_cell,
    token_count,
    tokens_cell,
)
from tests.apps.team.conftest import report


def test_manager_alice_bob_direct_hierarchy_ignores_ancestor_overlap_and_tasks(graph):
    assert agent_parents(graph) == {"manager": None, "alice": "manager", "bob": "alice"}
    assert [agent["id"] for agent in direct_reports(graph, "manager")] == ["alice"]
    assert [agent["id"] for agent in direct_reports(graph, "alice")] == ["bob"]
    assert direct_reports(graph, "bob") == []
    graph["tasks"]["other"] = dict(graph["tasks"]["t"], id="other")
    assert [agent["id"] for agent in direct_reports(graph, "manager")] == ["alice"]
    assert agent_path(graph, "bob") == "Manager / Alice / Bob"
    graph.pop("tasks")
    assert agent_path(graph, "alice") == "Manager / Alice"


def test_shared_report_not_task_derived_and_missing_report_unavailable(graph):
    fields = report_projection(graph["agents"]["alice"])
    assert fields["summary"] == "No current work report."
    assert fields["status"] == "Unavailable"
    assert fields["tokens"] == fields["time"] == "unavailable"
    graph["agents"]["alice"]["report"] = report("Own current report")
    path, pairs = summary_fields(graph, "alice")
    assert path == "Manager / Alice"
    assert dict(pairs)["Summary"] == "Own current report"
    assert dict(pairs)["Status"] == "Working"
    assert not any("tasks" in value or "0/" in value for _, value in pairs)


def test_ambiguous_membership_not_guessed_and_root_never_reports_to_child(graph):
    graph["teams"]["child"]["agent_ids"].append("manager")
    assert agent_parents(graph)["manager"] is None
    graph["agents"]["eve"] = dict(graph["agents"]["alice"], id="eve", name="Eve")
    graph["teams"]["other"] = dict(
        graph["teams"]["child"], id="other", manager_id="eve", agent_ids=["eve", "bob"], task_ids=[]
    )
    with pytest.raises(ValueError, match="ambiguous reporting managers for agent bob"):
        agent_parents(graph)


def test_multiple_managed_teams_same_manager_deduplicate(graph):
    graph["teams"]["more"] = dict(graph["teams"]["child"], id="more")
    assert [agent["id"] for agent in direct_reports(graph, "manager")] == ["alice"]
    assert [agent["id"] for agent in direct_reports(graph, "alice")] == ["bob"]


def test_unknown_zero_source_and_time_formatting(graph):
    work: dict[str, Any] = report()
    assert token_count(work) is None
    assert compact(None) == seconds(None) == "unavailable"
    assert seconds(0) == "0s" and seconds(60) == "1m" and seconds(3600) == "1h"
    assert time_cell(work) == "unavailable / unavailable"
    work["tokens"].update(input=1000, output=100, cache_write=50, cache_read=9000, source="sample")
    assert token_count(work) == 1150
    assert tokens_cell(work) == "1.1k [sample]"
    work["tokens"].update(input=0, output=0, cache_write=0, source="measured")
    assert tokens_cell(work) == "0 [measured]"
    agent = graph["agents"]["alice"]
    assert context_cell(agent) == "unavailable"
    agent["context"].update(used_tokens=25, capacity_tokens=100, source="sample")
    assert context_cell(agent) == "25.0% [sample]"
    work["estimate"]["target_finish"] = "2026-10-13T10:00:00+07:00"
    assert time_cell(work) == "unavailable / target 10:00:00"


def test_blocker_projection_and_raw_unchanged(graph):
    agent = graph["agents"]["alice"]
    agent["report"] = report("Reviewing boundary", "blocked")
    agent["report"]["blocker"] = "Awaiting access"
    before = copy.deepcopy(agent)
    fields = report_projection(agent)
    assert fields["summary"] == "Reviewing boundary — Blocker: Awaiting access"
    assert fields["status"] == "Blocked"
    assert agent == before


def test_83_columns_all_agent_fields_and_shared_projection(graph):
    columns = table_columns(83)
    assert [field for field, _, _ in columns] == [
        "status",
        "agent",
        "summary",
        "timestamp",
        "time",
        "tokens",
        "context",
    ]
    assert sum(width + 2 for _, _, width in columns) <= 75
    agent = graph["agents"]["alice"]
    agent["report"] = report("Own current report")
    before = copy.deepcopy(agent)
    cells = agent_cells(agent, columns)
    assert cells == [
        "●",
        "Alice",
        "Own current report",
        "10:00",
        "— / —",
        "unavailable",
        "unavailable",
    ]
    assert agent == before
    full = table_columns(200)
    projection = report_projection(agent)
    assert agent_cells(agent, full) == [projection[key] for key, _, _ in full]
    assert len(table_columns(60)) < len(columns)
