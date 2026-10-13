"""Real public-CLI/ShelfDB fixtures, isolated from all previews and agent state."""

import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

STAMP = "2026-10-13T10:00:00+07:00"


def documents(goal="g"):
    context = dict(used_tokens=None, capacity_tokens=None, observed_at=None, source="unavailable")
    agents = [
        dict(
            id=aid,
            goal_id=goal,
            name=aid.title(),
            model="unavailable",
            thinking="unavailable",
            context=copy.deepcopy(context),
            updated_at=STAMP,
        )
        for aid in ("manager", "alice", "bob")
    ]
    task = dict(
        id="t",
        goal_id=goal,
        name="Implement slice",
        owner_id="alice",
        team_id="child",
        status="working",
        status_changed_at=STAMP,
        updated_at=STAMP,
        elapsed_seconds=None,
        estimate=dict(min_seconds=None, max_seconds=None, target_finish=None),
        tokens=dict(
            input=None,
            output=None,
            cache_read=None,
            cache_write=None,
            observed_at=None,
            source="unavailable",
        ),
        note="Real work report",
    )
    return dict(
        goals=[dict(id=goal, goal_id=goal, name="Shared goal", manager_id="manager")],
        teams=[
            dict(
                id="root",
                goal_id=goal,
                name="Root",
                manager_id="manager",
                parent_id=None,
                agent_ids=["manager", "alice", "bob"],
                task_ids=["t"],
            ),
            dict(
                id="child",
                goal_id=goal,
                name="Child",
                manager_id="alice",
                parent_id="root",
                agent_ids=["alice", "bob"],
                task_ids=["t"],
            ),
        ],
        agents=agents,
        tasks=[task],
    )


def report(summary="Implementing report contract", status="working"):
    return dict(
        summary=summary,
        status=status,
        blocker="",
        status_changed_at=STAMP,
        elapsed_seconds=None,
        estimate=dict(min_seconds=None, max_seconds=None, target_finish=None),
        tokens=dict(
            input=None,
            output=None,
            cache_read=None,
            cache_write=None,
            observed_at=None,
            source="unavailable",
        ),
    )


def report_documents(goal="g"):
    doc = documents(goal)
    doc["tasks"] = []
    for team in doc["teams"]:
        team["task_ids"] = []
    for agent in doc["agents"]:
        agent["report"] = report(
            {
                "manager": "Coordinating accepted scope",
                "alice": "Implementing report contract",
                "bob": "Checking validated publishing",
            }[agent["id"]]
        )
    return doc


def mapping(doc):
    return {
        kind: {record["id"]: copy.deepcopy(record) for record in rows} for kind, rows in doc.items()
    }


@pytest.fixture
def graph():
    return mapping(documents())


class Service:
    def __init__(self, root):
        self.root = root
        self.env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[3] / "src"))
        self.log = (root.parent / "server.log").open("w+")
        self.process = subprocess.Popen(
            self.argv("serve"), env=self.env, stdout=self.log, stderr=self.log
        )
        deadline = time.monotonic() + 8
        while not (root / "db.sock").exists():
            if self.process.poll() is not None or time.monotonic() > deadline:
                self.stop()
                self.log.seek(0)
                raise RuntimeError(self.log.read())
            time.sleep(0.02)

    @property
    def url(self):
        from automata.apps.team.store import service_url

        return service_url(self.root)

    def argv(self, *args):
        console = Path(sys.executable).with_name("automata")
        assert console.is_file(), "Install the project in the isolated test environment first"
        return [str(console), "team", *args, "--state-root", str(self.root)]

    def call(self, *args, document=None, raw=None, ok=True):
        if document is not None or raw is not None:
            args += ("--file", "-")
        result = subprocess.run(
            self.argv(*args),
            input=(json.dumps(document) if document is not None else raw),
            text=True,
            capture_output=True,
            env=self.env,
            timeout=10,
        )
        if ok:
            assert result.returncode == 0, result.stderr
        else:
            assert result.returncode != 0, result.stdout
            assert result.stderr
        return result

    def init(self, goal="g"):
        self.call("init", "--goal", goal, "--actor", "manager", document=documents(goal))

    def snapshot(self, goal="g"):
        return json.loads(self.call("json", "--goal", goal).stdout)

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)


@pytest.fixture
def report_service(tmp_path):
    instance = Service(tmp_path / "state")
    try:
        instance.call("init", "--goal", "g", "--actor", "manager", document=report_documents())
        yield instance
    finally:
        instance.stop()
        instance.log.close()
    assert not (instance.root / "db.sock").exists()


@pytest.fixture
def service(tmp_path):
    instance = Service(tmp_path / "state")
    try:
        instance.init()
        yield instance
    finally:
        instance.stop()
        instance.log.close()
    assert not (instance.root / "db.sock").exists()
