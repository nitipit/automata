import copy
import json

from tests.apps.team.conftest import documents


def test_public_stdin_snapshot_and_patch(service):
    before = service.snapshot()
    result = service.call(
        "update",
        "--goal",
        "g",
        "--actor",
        "alice",
        "--kind",
        "task",
        "--id",
        "t",
        document={"elapsed_seconds": 12},
    )
    task = json.loads(result.stdout)
    assert task["elapsed_seconds"] == 12
    assert task["status_changed_at"] == before["tasks"]["t"]["status_changed_at"]
    assert task["note"] == before["tasks"]["t"]["note"]
    assert service.snapshot()["tasks"]["t"] == task
    record = service.call("json", "--goal", "g", "--kind", "agent", "--id", "alice")
    assert json.loads(record.stdout)["id"] == "alice"


def test_second_goal_identical_ids_and_reinit_rejected(service):
    first = service.snapshot()
    service.init("second")
    assert service.snapshot() == first
    assert set(service.snapshot("second")["agents"]) == set(first["agents"])
    service.call(
        "init",
        "--goal",
        "g",
        "--actor",
        "manager",
        document={kind: list(rows.values()) for kind, rows in first.items()},
        ok=False,
    )
    assert service.snapshot() == first


def test_errors_atomic_and_strict_json(service):
    before = service.snapshot()
    for raw in ('{"note":"x","note":"y"}', '{"elapsed_seconds":NaN}', "[]", "{"):
        service.call(
            "update",
            "--goal",
            "g",
            "--actor",
            "alice",
            "--kind",
            "task",
            "--id",
            "t",
            raw=raw,
            ok=False,
        )
        assert service.snapshot() == before
    service.call(
        "update",
        "--goal",
        "g",
        "--actor",
        "bob",
        "--kind",
        "task",
        "--id",
        "t",
        document={"note": "stolen"},
        ok=False,
    )
    service.call("json", "--goal", "absent", ok=False)
    service.call("json", "--goal", "g", "--kind", "agent", ok=False)
    assert service.snapshot() == before


def test_invalid_initial_graphs_do_not_leave_partial_records(service):
    first = service.snapshot()
    for index, mutation in enumerate(
        [
            lambda d: d["agents"].append(copy.deepcopy(d["agents"][0])),
            lambda d: d["teams"][1].update(parent_id="child"),
            lambda d: d["goals"][0].update(manager_id="missing"),
            lambda d: d["tasks"][0].update(goal_id="g"),
        ]
    ):
        goal = f"invalid-{index}"
        document = documents(goal)
        mutation(document)
        service.call("init", "--goal", goal, "--actor", "manager", document=document, ok=False)
        assert service.snapshot() == first
        service.call("json", "--goal", goal, ok=False)
        service.init(goal)  # Succeeds only if no hidden partial records remain.
        assert service.snapshot(goal)["goals"][goal]["manager_id"] == "manager"


def test_actor_cannot_bootstrap_foreign_manager_goal(service):
    before = service.snapshot()
    service.call(
        "init", "--goal", "second", "--actor", "alice", document=documents("second"), ok=False
    )
    assert service.snapshot() == before
    service.init("second")


def test_create_task_atomically_links_team(service):
    task = service.snapshot()["tasks"]["t"]
    task.update(id="new", owner_id="bob", name="New task")
    service.call(
        "put", "--goal", "g", "--actor", "bob", "--kind", "task", "--id", "new", document=task
    )
    state = service.snapshot()
    assert state["teams"]["child"]["task_ids"] == ["t", "new"]
    assert state["tasks"]["new"]["owner_id"] == "bob"
