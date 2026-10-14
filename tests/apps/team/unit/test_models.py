import copy
import json
from pathlib import Path

import pytest
from dictify import Model

from automata.tools.team.models import canonical
from automata.tools.team.store import validate_state
from tests.apps.team.conftest import report


def test_legacy_fixture_is_valid_and_has_no_invented_measurements():
    path = Path(__file__).resolve().parents[1] / "fixtures/legacy-goal.json"
    document = json.loads(path.read_text())
    state = {
        kind: {row["id"]: canonical(kind, row) for row in rows} for kind, rows in document.items()
    }
    validate_state(state, "example")
    assert state["goals"]["example"]["name"].startswith("SAMPLE")
    assert all(agent["context"]["source"] == "unavailable" for agent in state["agents"].values())
    assert all(task["tokens"]["source"] == "unavailable" for task in state["tasks"].values())


@pytest.mark.parametrize(
    "patch",
    [
        {"status": "invented"},
        {"status": "blocked", "blocker": ""},
        {"summary": ""},
        {"summary": None},
        {"blocker": None},
        {"elapsed_seconds": True},
        {"elapsed_seconds": -1},
        {"tokens": {"input": 1}},
        {"estimate": {"min_seconds": -1}},
        {"status_changed_at": "2026-10-13T10:00:00"},
        {"todo": []},
    ],
)
def test_canonical_report_rejects_bad_fields(graph, patch):
    agent = graph["agents"]["alice"]
    agent["report"] = report() | patch
    with pytest.raises((ValueError, Model.Error)):
        canonical("agents", agent)


def test_legacy_missing_and_explicit_null_report_preserved(graph):
    agent = graph["agents"]["alice"]
    assert "report" not in canonical("agents", agent)
    agent["report"] = None
    assert canonical("agents", agent)["report"] is None
    agent["report"] = report("Explicit own report")
    assert canonical("agents", agent)["report"] == agent["report"]


def test_canonical_plain_json_and_strict_nested_fields(graph):
    for kind, records in graph.items():
        for record in records.values():
            result = canonical(kind, record)
            assert type(result) is dict
            assert json.loads(json.dumps(result)) == record
    bad = copy.deepcopy(graph["tasks"]["t"])
    bad["tokens"]["extra"] = 3
    with pytest.raises((ValueError, Model.Error)):
        canonical("tasks", bad)


@pytest.mark.parametrize(
    "field,value",
    [
        ("elapsed_seconds", -1),
        ("elapsed_seconds", True),
        ("elapsed_seconds", float("nan")),
        ("status", "completed"),
        ("status_changed_at", "2026-10-13T10:00:00"),
        ("note", None),
        ("name", ""),
        ("owner_id", None),
        ("unexpected", 1),
    ],
)
def test_bad_task_fields(graph, field, value):
    task = graph["tasks"]["t"]
    task[field] = value
    with pytest.raises((ValueError, Model.Error)):
        canonical("tasks", task)


@pytest.mark.parametrize(
    "patch",
    [
        {"input": -1},
        {"input": True},
        {"input": 5},
        {"input": 5, "source": "measured"},
        {"source": "invented"},
    ],
)
def test_bad_token_measurements(graph, patch):
    task = graph["tasks"]["t"]
    task["tokens"].update(patch)
    with pytest.raises((ValueError, Model.Error)):
        canonical("tasks", task)


@pytest.mark.parametrize(
    "patch",
    [
        {"used_tokens": 2},
        {"used_tokens": 100, "capacity_tokens": 1, "source": "measured"},
        {"capacity_tokens": 0},
        {"used_tokens": True},
        {"source": "invented"},
    ],
)
def test_bad_context(graph, patch):
    agent = graph["agents"]["alice"]
    agent["context"].update(patch)
    with pytest.raises((ValueError, Model.Error)):
        canonical("agents", agent)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda s: s["goals"]["g"].update(manager_id="missing"),
        lambda s: s["teams"]["root"].update(manager_id="alice"),
        lambda s: s["teams"]["child"].update(parent_id="missing"),
        lambda s: s["teams"]["child"].update(agent_ids=["alice", "alice"]),
        lambda s: s["teams"]["child"].update(agent_ids=["bob"]),
        lambda s: s["teams"]["child"].update(task_ids=["missing"]),
        lambda s: s["tasks"]["t"].update(team_id="missing"),
        lambda s: s["tasks"]["t"].update(owner_id="manager"),
        lambda s: s["agents"]["alice"].update(goal_id="other"),
        lambda s: s["teams"]["child"].update(parent_id="child"),
    ],
)
def test_graph_rejections(graph, mutation):
    mutation(graph)
    with pytest.raises((ValueError, Model.Error)):
        validate_state(graph, "g")


def test_cycle_not_just_missing_root(graph):
    graph["teams"]["grandchild"] = dict(graph["teams"]["child"], id="grandchild", parent_id="child")
    graph["teams"]["child"]["parent_id"] = "grandchild"
    with pytest.raises(ValueError, match="cycle"):
        validate_state(graph, "g")


def test_estimate_bounds_and_finite_json(graph):
    graph["tasks"]["t"]["estimate"].update(min_seconds=100, max_seconds=50)
    with pytest.raises((ValueError, Model.Error)):
        canonical("tasks", graph["tasks"]["t"])
