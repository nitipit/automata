"""Current report publishing through the real installed CLI and ShelfDB."""

import asyncio
import json
import re
import shlex
import subprocess
from pathlib import Path

import pytest
from shelfdb.client import Client

from automata.apps.team.store import snapshot
from automata.install.skills import skill_sources
from tests.apps.team.conftest import report


def update(service, patch, actor="alice", ok=True):
    return service.call(
        "update",
        "--goal",
        "g",
        "--actor",
        actor,
        "--kind",
        "agent",
        "--id",
        "alice",
        document=patch,
        ok=ok,
    )


def test_first_report_merge_timestamps_metrics_same_status_and_replace(service):
    original = service.snapshot()["agents"]["alice"]
    assert original.get("report") is None
    first = report("Own initial current work")
    first.pop("status_changed_at")
    result = json.loads(update(service, {"report": first}).stdout)
    stamp = result["report"]["status_changed_at"]
    assert stamp == result["updated_at"]
    for patch in (
        {"report": {"elapsed_seconds": 12}},
        {"report": {"status": "working"}},
        {
            "report": {
                "tokens": {
                    "input": 10,
                    "output": 3,
                    "cache_write": 0,
                    "source": "measured",
                    "observed_at": "2026-10-13T16:35:00+00:00",
                }
            }
        },
        {
            "context": {
                "used_tokens": 100,
                "capacity_tokens": 1000,
                "source": "measured",
                "observed_at": "2026-10-13T16:35:00+00:00",
            }
        },
    ):
        result = json.loads(update(service, patch).stdout)
        assert result["report"]["status_changed_at"] == stamp
        assert result["report"]["summary"] == "Own initial current work"
    result["report"]["status_changed_at"] = "2020-01-01T00:00:00+00:00"
    replaced = json.loads(
        service.call(
            "put",
            "--goal",
            "g",
            "--actor",
            "alice",
            "--kind",
            "agent",
            "--id",
            "alice",
            document=result,
        ).stdout
    )
    assert replaced["report"]["status_changed_at"] == stamp
    changed = json.loads(
        update(service, {"report": {"status": "blocked", "blocker": "Need decision"}}).stdout
    )
    assert changed["report"]["status_changed_at"] != stamp
    assert changed["report"]["status_changed_at"] == changed["updated_at"]
    assert changed["report"]["tokens"]["input"] == 10
    assert changed["report"]["tokens"]["output"] == 3
    assert changed["report"]["tokens"]["cache_read"] is None
    assert changed["context"]["used_tokens"] == 100


@pytest.mark.parametrize(
    "patch,actor",
    [
        ({"report": {"summary": "stolen"}}, "manager"),
        ({"report": {"summary": "stolen"}}, "bob"),
        ({"report": {"status_changed_at": "2026-10-13T16:00:00+00:00"}}, "alice"),
        ({"report": {"status": "blocked", "blocker": ""}}, "alice"),
        ({"report": {"status": "blocked", "blocker": "  "}}, "alice"),
        ({"report": {"status": "invented"}}, "alice"),
        ({"report": {"elapsed_seconds": True}}, "alice"),
        ({"report": {"elapsed_seconds": -1}}, "alice"),
        ({"report": {"tokens": {"input": 5}}}, "alice"),
        ({"report": {"estimate": {"min_seconds": 100, "max_seconds": 10}}}, "alice"),
        ({"report": {"summary": ""}}, "alice"),
        ({"report": {"todo": ["a", "b"]}}, "alice"),
    ],
)
def test_invalid_or_foreign_reports_leave_all_records_unchanged(report_service, patch, actor):
    before = report_service.snapshot()
    result = update(report_service, patch, actor, ok=False)
    assert not result.stdout
    assert report_service.snapshot() == before


def test_board_snapshot_does_not_even_read_task_shelf(report_service):
    async def check():
        client = await Client.connect(report_service.url)
        try:
            async with client.transaction(write=True) as tx:
                await tx.shelf("tasks").put("unread-legacy-record", {"not": "a task"}).query()
        finally:
            await client.close()
        scoped = await snapshot("g", report_service.url, reports_only=True)
        assert set(scoped) == {"goals", "teams", "agents"}
        assert scoped["agents"]["alice"]["report"]["summary"] == "Implementing report contract"
        # The ordinary whole snapshot really encounters that test-only malformed row.
        with pytest.raises(KeyError, match="goal_id"):
            await snapshot("g", report_service.url)
        published = json.loads(
            update(report_service, {"report": {"summary": "No task enumeration"}}).stdout
        )
        assert published["report"]["summary"] == "No task enumeration"
        inspected = json.loads(
            report_service.call("json", "--goal", "g", "--kind", "agent", "--id", "alice").stdout
        )
        assert inspected == published
        from textual.widgets import Static

        from automata.apps.team.app import Dashboard

        app = Dashboard("g", report_service.url, poll=0.03)
        async with app.run_test(size=(83, 46)) as pilot:
            assert [key for key, _ in app.rows] == ["alice"]
            assert "No task enumeration" in app.query_one("#owner-overview", Static).render().plain
            await pilot.press("q")

    asyncio.run(check())


def test_report_ownership_on_replace_and_explicit_unavailable(report_service):
    before = report_service.snapshot()
    agent = dict(before["agents"]["alice"], report=None)
    report_service.call(
        "put",
        "--goal",
        "g",
        "--actor",
        "bob",
        "--kind",
        "agent",
        "--id",
        "alice",
        document=agent,
        ok=False,
    )
    assert report_service.snapshot() == before
    update(report_service, {"report": None})
    assert report_service.snapshot()["agents"]["alice"]["report"] is None
    assert report_service.snapshot()["tasks"] == {}
    # Re-publish own first report without any legacy reset or task publishing.
    update(
        report_service,
        {"report": report("Resumed current work") | {"status_changed_at": None}},
        ok=False,
    )
    work = report("Resumed current work")
    work.pop("status_changed_at")
    update(report_service, {"report": work})
    assert report_service.snapshot()["agents"]["alice"]["report"]["status_changed_at"] is not None


def test_concurrent_report_patches_and_identical_ids_across_goals(report_service):
    from tests.apps.team.conftest import report_documents

    report_service.call(
        "init", "--goal", "second", "--actor", "manager", document=report_documents("second")
    )
    writers = []
    try:
        for goal, patch in [
            ("g", {"report": {"elapsed_seconds": 42}}),
            ("g", {"report": {"summary": "Concurrent own report"}}),
            ("second", {"report": {"elapsed_seconds": 99}}),
        ]:
            process = subprocess.Popen(
                report_service.argv(
                    "update",
                    "--goal",
                    goal,
                    "--actor",
                    "alice",
                    "--kind",
                    "agent",
                    "--id",
                    "alice",
                    "--file",
                    "-",
                ),
                env=report_service.env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            writers.append(process)
            process.stdin.write(json.dumps(patch))
            process.stdin.close()
            process.stdin = None
        for process in writers:
            out, err = process.communicate(timeout=10)
            assert process.returncode == 0, err
            assert json.loads(out)["id"] == "alice"
    finally:
        for process in writers:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
    first = report_service.snapshot()["agents"]["alice"]["report"]
    assert first["summary"] == "Concurrent own report" and first["elapsed_seconds"] == 42
    assert report_service.snapshot("second")["agents"]["alice"]["report"]["elapsed_seconds"] == 99


def test_bundled_skill_discovery_and_literal_publishing_examples(service):
    skill = skill_sources()["automata-team-use"] / "SKILL.md"
    root = Path(__file__).resolve().parents[4]
    blocks = re.findall(r"```sh\n(.*?)\n```", skill.read_text(), re.S)
    console = shlex.quote(service.argv()[0])
    executed = []
    for block in blocks:
        # Board is interactive: its public terminal boundary is tested separately.
        lines = block.splitlines()
        lines = [line for line in lines if not line.startswith("automata team board ")]
        script = "\n".join(lines).replace("automata ", console + " ")
        script = script.replace(".agents/var/apps/agent-team", shlex.quote(str(service.root)))
        script = script.replace(
            "examples/team/reports.json", shlex.quote(str(root / "examples/team/reports.json"))
        )
        result = subprocess.run(
            ["bash", "-e", "-c", script],
            env=service.env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        executed.append(result.stdout)
    state = service.snapshot("example-reports")
    assert state["tasks"] == {}
    work = state["agents"]["alice"]["report"]
    assert work["summary"] == "Verified current-report publishing"
    assert work["status"] == "done" and work["blocker"] == ""
    assert work["tokens"]["source"] == "unavailable"
    assert work["elapsed_seconds"] is None
    assert json.loads(executed[-1])["report"] == work
    assert service.snapshot()["goals"]["g"]["id"] == "g"
