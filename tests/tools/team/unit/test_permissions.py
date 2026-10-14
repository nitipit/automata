import copy

import pytest

from automata.tools.team.store import authorize, validate_state


def test_root_manager_controls_structure_not_foreign_reports(graph):
    root = dict(graph["teams"]["root"], name="Renamed")
    authorize(graph, "teams", "root", root, "manager")
    with pytest.raises(ValueError, match="agent record owner"):
        authorize(graph, "agents", "alice", graph["agents"]["alice"], "manager")
    with pytest.raises(ValueError, match="task owner"):
        authorize(graph, "tasks", "t", graph["tasks"]["t"], "manager")


def test_nested_manager_edits_own_team_and_creates_child(graph):
    child = dict(graph["teams"]["child"], name="Updated")
    authorize(graph, "teams", "child", child, "alice")
    new = dict(child, id="grandchild", manager_id="bob", parent_id="child", task_ids=[])
    authorize(graph, "teams", "grandchild", new, "alice")
    graph["teams"]["grandchild"] = new
    validate_state(graph, "g")


@pytest.mark.parametrize(
    "key,patch,actor,match",
    [
        ("root", {"name": "takeover"}, "alice", "manager required"),
        ("child", {"manager_id": "bob"}, "alice", "manager or parent"),
        ("child", {"parent_id": None}, "alice", "manager or parent"),
        ("child", {"name": "takeover"}, "bob", "manager required"),
    ],
)
def test_nested_escalation_rejected(graph, key, patch, actor, match):
    candidate = dict(graph["teams"][key], **patch)
    with pytest.raises(ValueError, match=match):
        authorize(graph, "teams", key, candidate, actor)


def test_nested_membership_and_foreign_task_links(graph):
    graph["agents"]["stranger"] = dict(graph["agents"]["bob"], id="stranger")
    candidate = copy.deepcopy(graph["teams"]["child"])
    candidate["agent_ids"].append("stranger")
    with pytest.raises(ValueError, match="foreign membership"):
        authorize(graph, "teams", "child", candidate, "alice")
    candidate = dict(graph["teams"]["child"], task_ids=["t", "foreign"])
    graph["tasks"]["foreign"] = dict(graph["tasks"]["t"], id="foreign", team_id="root")
    with pytest.raises(ValueError, match="foreign task links"):
        authorize(graph, "teams", "child", candidate, "alice")


def test_agents_own_records_task_placement_immutable(graph):
    authorize(graph, "agents", "alice", graph["agents"]["alice"], "alice")
    authorize(graph, "tasks", "t", graph["tasks"]["t"], "alice")
    task = dict(graph["tasks"]["t"], owner_id="bob")
    with pytest.raises(ValueError, match="task owner"):
        authorize(graph, "tasks", "t", task, "bob")
    task = dict(graph["tasks"]["t"], team_id="root")
    with pytest.raises(ValueError, match="placement immutable"):
        authorize(graph, "tasks", "t", task, "alice")


def test_goal_manager_identity_cannot_be_reassigned(graph):
    with pytest.raises(ValueError, match="manager identity immutable"):
        authorize(graph, "goals", "g", dict(graph["goals"]["g"], manager_id="alice"), "manager")
