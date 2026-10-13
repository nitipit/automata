import asyncio
import copy
import json
import subprocess

import pytest

from automata.apps.team.store import snapshot


def test_real_shelfdb_plain_records(service):
    state = asyncio.run(snapshot("g", service.url))
    assert state == service.snapshot()
    assert json.loads(json.dumps(state)) == state
    assert state["tasks"]["t"]["status"] == "working"


@pytest.mark.parametrize(
    "kind,id,actor,patch",
    [
        ("goal", "g", "alice", {"name": "stolen"}),
        ("goal", "g", "manager", {"manager_id": "alice"}),
        ("team", "root", "alice", {"name": "stolen"}),
        ("team", "child", "bob", {"name": "stolen"}),
        ("team", "child", "alice", {"parent_id": None}),
        ("team", "child", "alice", {"manager_id": "bob"}),
        ("team", "child", "manager", {"parent_id": "child"}),
        ("team", "root", "manager", {"agent_ids": ["manager", "missing"]}),
        ("team", "child", "manager", {"agent_ids": ["bob"]}),
        ("team", "child", "manager", {"task_ids": []}),
        ("team", "child", "manager", {"task_ids": ["t", "missing"]}),
        ("agent", "alice", "bob", {"name": "stolen"}),
        ("agent", "alice", "alice", {"context": {"used_tokens": 20}}),
        ("agent", "alice", "alice", {"context": {"extra": 1}}),
        ("task", "t", "bob", {"note": "stolen"}),
        ("task", "t", "alice", {"owner_id": "bob"}),
        ("task", "t", "alice", {"team_id": "root"}),
        ("task", "t", "alice", {"id": "different"}),
        ("task", "t", "alice", {"goal_id": "foreign"}),
        ("task", "t", "alice", {"updated_at": "2026-10-13T10:00:00+07:00"}),
        ("task", "t", "alice", {"status_changed_at": "2026-10-13T10:00:00+07:00"}),
        ("task", "t", "alice", {"elapsed_seconds": -1}),
        ("task", "t", "alice", {"elapsed_seconds": True}),
        ("task", "t", "alice", {"status": "invented"}),
        ("task", "t", "alice", {"estimate": {"min_seconds": 100, "max_seconds": 1}}),
        ("task", "t", "alice", {"tokens": {"input": 10}}),
        ("task", "t", "alice", {"tokens": {"input": 10, "source": "measured"}}),
        ("task", "t", "alice", {"tokens": {"unknown": 1}}),
    ],
)
def test_invalid_updates_are_atomic_at_public_cli(service, kind, id, actor, patch):
    before = service.snapshot()
    result = service.call(
        "update",
        "--goal",
        "g",
        "--actor",
        actor,
        "--kind",
        kind,
        "--id",
        id,
        document=patch,
        ok=False,
    )
    assert not result.stdout
    assert service.snapshot() == before


def test_status_timestamps_same_status_metrics_replace_and_transition(service):
    old = service.snapshot()["tasks"]["t"]
    for patch in (
        {"elapsed_seconds": 5},
        {"status": "working"},
        {
            "tokens": {
                "input": 10,
                "output": 5,
                "cache_write": 0,
                "cache_read": 0,
                "source": "measured",
                "observed_at": "2026-10-13T15:00:00+00:00",
            }
        },
    ):
        task = json.loads(
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
                document=patch,
            ).stdout
        )
        assert task["status_changed_at"] == old["status_changed_at"]
    task["status_changed_at"] = "2020-01-01T00:00:00+00:00"
    replaced = json.loads(
        service.call(
            "put", "--goal", "g", "--actor", "alice", "--kind", "task", "--id", "t", document=task
        ).stdout
    )
    assert replaced["status_changed_at"] == old["status_changed_at"]
    transition = json.loads(
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
            document={"status": "done"},
        ).stdout
    )
    assert transition["status_changed_at"] != old["status_changed_at"]
    assert transition["status_changed_at"] == transition["updated_at"]
    assert transition["tokens"]["input"] == 10
    assert transition["tokens"]["output"] == 5


def test_create_replace_permissions_and_atomic_missing_link(service):
    state = service.snapshot()
    task = dict(state["tasks"]["t"], id="new", owner_id="bob")
    for actor, body in [
        ("alice", task),
        ("manager", task),
        ("bob", dict(task, goal_id="other")),
        ("bob", dict(task, team_id="missing")),
        ("bob", dict(task, tokens=dict(task["tokens"], input=5))),
    ]:
        service.call(
            "put",
            "--goal",
            "g",
            "--actor",
            actor,
            "--kind",
            "task",
            "--id",
            "new",
            document=body,
            ok=False,
        )
        assert service.snapshot() == state
    service.call(
        "put", "--goal", "g", "--actor", "bob", "--kind", "task", "--id", "new", document=task
    )
    state = service.snapshot()
    stolen = dict(state["tasks"]["new"], owner_id="alice")
    service.call(
        "put",
        "--goal",
        "g",
        "--actor",
        "alice",
        "--kind",
        "task",
        "--id",
        "new",
        document=stolen,
        ok=False,
    )
    assert service.snapshot() == state
    agent = dict(state["agents"]["bob"], id="stranger")
    service.call(
        "put",
        "--goal",
        "g",
        "--actor",
        "manager",
        "--kind",
        "agent",
        "--id",
        "stranger",
        document=agent,
        ok=False,
    )
    service.call(
        "put",
        "--goal",
        "g",
        "--actor",
        "stranger",
        "--kind",
        "agent",
        "--id",
        "stranger",
        document=agent,
    )
    child = copy.deepcopy(state["teams"]["child"])
    child["agent_ids"].append("stranger")
    before = service.snapshot()
    service.call(
        "put",
        "--goal",
        "g",
        "--actor",
        "alice",
        "--kind",
        "team",
        "--id",
        "child",
        document=child,
        ok=False,
    )
    assert service.snapshot() == before
    root = copy.deepcopy(state["teams"]["root"])
    root["agent_ids"].append("stranger")
    service.call(
        "put", "--goal", "g", "--actor", "manager", "--kind", "team", "--id", "root", document=root
    )
    service.call(
        "put", "--goal", "g", "--actor", "alice", "--kind", "team", "--id", "child", document=child
    )
    assert "stranger" in service.snapshot()["teams"]["child"]["agent_ids"]


def test_nested_manager_can_create_child_without_parent_escalation(service):
    team = dict(
        service.snapshot()["teams"]["child"],
        id="grandchild",
        parent_id="child",
        manager_id="bob",
        task_ids=[],
    )
    service.call(
        "put",
        "--goal",
        "g",
        "--actor",
        "bob",
        "--kind",
        "team",
        "--id",
        "grandchild",
        document=team,
        ok=False,
    )
    service.call(
        "put",
        "--goal",
        "g",
        "--actor",
        "alice",
        "--kind",
        "team",
        "--id",
        "grandchild",
        document=team,
    )
    assert service.snapshot()["teams"]["grandchild"]["manager_id"] == "bob"
    before = service.snapshot()
    service.call(
        "update",
        "--goal",
        "g",
        "--actor",
        "bob",
        "--kind",
        "team",
        "--id",
        "grandchild",
        document={"parent_id": "root"},
        ok=False,
    )
    assert service.snapshot() == before


def test_independent_concurrent_cli_writers_no_lost_updates(service):
    service.init("second")
    task = dict(service.snapshot()["tasks"]["t"], id="bob-task", owner_id="bob")
    service.call(
        "put", "--goal", "g", "--actor", "bob", "--kind", "task", "--id", "bob-task", document=task
    )
    writers = []
    try:
        for goal, owner, id, patch in [
            ("g", "alice", "t", {"elapsed_seconds": 42}),
            ("g", "alice", "t", {"note": "Concurrent factual note"}),
            ("g", "bob", "bob-task", {"elapsed_seconds": 21}),
            ("second", "alice", "t", {"elapsed_seconds": 99}),
        ]:
            process = subprocess.Popen(
                service.argv(
                    "update",
                    "--goal",
                    goal,
                    "--actor",
                    owner,
                    "--kind",
                    "task",
                    "--id",
                    id,
                    "--file",
                    "-",
                ),
                env=service.env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            process.stdin.write(json.dumps(patch))
            process.stdin.close()
            process.stdin = None
            writers.append(process)
        for process in writers:
            out, err = process.communicate(timeout=10)
            assert process.returncode == 0, err
            assert json.loads(out)["goal_id"] in {"g", "second"}
    finally:
        for process in writers:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
    state = service.snapshot()
    assert state["tasks"]["t"]["elapsed_seconds"] == 42
    assert state["tasks"]["t"]["note"] == "Concurrent factual note"
    assert state["tasks"]["bob-task"]["elapsed_seconds"] == 21
    assert service.snapshot("second")["tasks"]["t"]["elapsed_seconds"] == 99
