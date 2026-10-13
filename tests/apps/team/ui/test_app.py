import asyncio

from textual.containers import VerticalScroll
from textual.widgets import DataTable, Static

from automata.apps.team.app import Dashboard
from automata.apps.team.panels import agent_panel
from automata.apps.team.store import snapshot
from automata.apps.team.view import agent_cells, table_columns


def test_live_direct_agent_reports_refresh_scope_navigation_and_quit(report_service):
    service = report_service
    service.init("other")

    async def check():
        app = Dashboard("g", service.url, poll=0.03)
        async with app.run_test(size=(83, 46)) as pilot:
            assert set(app.state["goals"]) == {"g"}
            assert "tasks" not in app.state
            assert app.route == "manager" and app.selected == "alice"
            assert [key for key, _ in app.rows] == ["alice"]
            assert len(app.query_one("#agents", DataTable).columns) == 7
            assert "Manager" == str(app.query_one("#heading", Static).render())
            assert (
                "Coordinating accepted scope" in app.query_one("#overview", Static).render().plain
            )
            service.call(
                "update",
                "--goal",
                "g",
                "--actor",
                "alice",
                "--kind",
                "agent",
                "--id",
                "alice",
                document={
                    "report": {
                        "summary": "Awaiting decision",
                        "status": "blocked",
                        "blocker": "Need approved boundary",
                    }
                },
            )
            await pilot.pause(0.15)
            alice = app.state["agents"]["alice"]
            expected = agent_panel(app.state, "alice", 71)[1].plain
            assert app.query_one("#owner-overview", Static).render().plain == expected
            assert "Blocker: Need approved boundary" in expected
            table = app.query_one("#agents", DataTable)
            assert table.get_row("alice") == agent_cells(alice, table_columns(83))
            await pilot.press("right")
            assert app.route == "alice" and app.selected == "bob"
            assert app.query_one("#overview", Static).render().plain == expected
            assert [key for key, _ in app.rows] == ["bob"]
            service.call(
                "update",
                "--goal",
                "g",
                "--actor",
                "bob",
                "--kind",
                "agent",
                "--id",
                "bob",
                document={"report": {"summary": "Verified report publishing", "status": "done"}},
            )
            await pilot.pause(0.15)
            bob_panel = app.query_one("#owner-overview", Static).render().plain
            assert "Verified report publishing" in bob_panel and "Done" in bob_panel
            assert table.get_row("bob") == agent_cells(
                app.state["agents"]["bob"], table_columns(83)
            )
            real_history = list(app.history)
            await pilot.press("right", "right", "right")
            assert app.route == "alice" and app.selected == "bob"
            assert app.history == real_history == [("manager", "alice")]
            assert [key for key, _ in app.rows] == ["bob"] and table.row_count == 1
            assert app.query_one("#overview", Static).render().plain == expected
            assert app.query_one("#owner-overview", Static).render().plain == bob_panel
            await pilot.press("enter")
            assert not app.query_one("#selection", VerticalScroll).display
            await pilot.press("enter")
            assert app.query_one("#selection", VerticalScroll).display
            await pilot.press("left")
            assert app.route == "manager" and app.selected == "alice" and app.history == []
            await pilot.press("left", "q")
        assert service.process.poll() is None
        assert (await snapshot("g", service.url))["tasks"] == {}

    asyncio.run(check())


def test_leaf_legacy_no_report_multiple_tasks_never_add_rows(service):
    original = service.snapshot()
    task = dict(original["tasks"]["t"], id="u")
    service.call(
        "put", "--goal", "g", "--actor", "alice", "--kind", "task", "--id", "u", document=task
    )

    async def check():
        app = Dashboard("g", service.url, poll=0.03)
        async with app.run_test(size=(83, 46)) as pilot:
            assert [key for key, _ in app.rows] == ["alice"]
            assert (
                "No current work report." in app.query_one("#owner-overview", Static).render().plain
            )
            assert "Unavailable" in app.query_one("#overview", Static).render().plain
            await pilot.press("right", "right", "right")
            assert app.route == "alice" and app.selected == "bob"
            assert [key for key, _ in app.rows] == ["bob"]
            assert app.history == [("manager", "alice")]
            assert (
                "No current work report." in app.query_one("#owner-overview", Static).render().plain
            )
            await pilot.press("left", "q")
            assert app.route == "manager" and app.selected == "alice"
        assert len((await snapshot("g", service.url))["tasks"]) == 2

    asyncio.run(check())


def test_root_without_children_keeps_own_report_and_navigation_noops(report_service):
    from tests.apps.team.conftest import report_documents

    doc = report_documents("solo")
    doc["teams"] = [dict(doc["teams"][0], agent_ids=["manager"])]
    doc["agents"] = [doc["agents"][0]]
    report_service.call("init", "--goal", "solo", "--actor", "manager", document=doc)

    async def check():
        app = Dashboard("solo", report_service.url, poll=0.03)
        async with app.run_test(size=(83, 46)) as pilot:
            before = await snapshot("solo", report_service.url)
            assert app.route == "manager" and app.selected is None and app.rows == []
            assert (
                "Coordinating accepted scope" in app.query_one("#overview", Static).render().plain
            )
            assert app.query_one("#agents", DataTable).row_count == 0
            assert str(app.query_one("#empty", Static).render()) == "No direct reports"
            await pilot.press("right", "right", "left")
            assert app.route == "manager" and app.selected is None and app.history == []
            assert await snapshot("solo", report_service.url) == before
            await pilot.press("q")
        assert report_service.process.poll() is None

    asyncio.run(check())


def test_selection_resize_and_viewer_never_writes(report_service):
    service = report_service
    agent = dict(service.snapshot()["agents"]["bob"], id="eve", name="Eve")
    service.call(
        "put", "--goal", "g", "--actor", "eve", "--kind", "agent", "--id", "eve", document=agent
    )
    service.call(
        "update",
        "--goal",
        "g",
        "--actor",
        "manager",
        "--kind",
        "team",
        "--id",
        "root",
        document={"agent_ids": ["manager", "alice", "bob", "eve"]},
    )

    async def check():
        app = Dashboard("g", service.url, poll=0.03)
        async with app.run_test(size=(83, 46)) as pilot:
            before = await snapshot("g", service.url)
            assert [key for key, _ in app.rows] == ["alice", "eve"]
            await pilot.press("down")
            assert app.selected == "eve"
            await pilot.press("right", "left")
            assert app.route == "manager" and app.selected == "eve"
            assert await snapshot("g", service.url) == before
            service.call(
                "update",
                "--goal",
                "g",
                "--actor",
                "eve",
                "--kind",
                "agent",
                "--id",
                "eve",
                document={"report": {"elapsed_seconds": 123}},
            )
            await pilot.pause(0.15)
            assert app.selected == "eve"
            assert app.state["agents"]["eve"]["report"]["elapsed_seconds"] == 123
            await pilot.resize_terminal(60, 46)
            assert app.selected == "eve" and app.route == "manager"
            await pilot.resize_terminal(83, 46)
            assert app.selected == "eve"
            assert len(app.query_one("#agents", DataTable).columns) == 7
            await pilot.press("q")
        assert (await snapshot("g", service.url))["agents"]["alice"] == before["agents"]["alice"]

    asyncio.run(check())


def test_sample_report_usage_label_is_not_inferred_from_tasks(report_service):
    service = report_service

    async def check():
        app = Dashboard("g", service.url, poll=0.03)
        async with app.run_test(size=(83, 46)) as pilot:
            assert str(app.query_one("#sample", Static).render()) == ""
            service.call(
                "update",
                "--goal",
                "g",
                "--actor",
                "alice",
                "--kind",
                "agent",
                "--id",
                "alice",
                document={
                    "report": {
                        "tokens": {
                            "input": 100,
                            "output": 20,
                            "cache_write": 0,
                            "source": "sample",
                            "observed_at": "2026-10-13T16:35:00+00:00",
                        }
                    }
                },
            )
            await pilot.pause(0.15)
            assert str(app.query_one("#sample", Static).render()) == "SAMPLE DATA"
            assert "120 [sample] tokens" in app.query_one("#owner-overview", Static).render().plain
            await pilot.press("right")
            assert "120 [sample] tokens" in app.query_one("#overview", Static).render().plain
            await pilot.press("q")

    asyncio.run(check())


def test_quit_awaits_inflight_real_refresh_without_cancelling_it(report_service):
    service = report_service

    async def check():
        app = Dashboard("g", service.url, poll=0.02)
        async with app.run_test(size=(83, 46)):
            entered, release, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()
            real_refresh = app.refresh_snapshot

            async def gated_refresh():
                entered.set()
                await release.wait()
                await real_refresh()
                completed.set()

            app.refresh_snapshot = gated_refresh
            await asyncio.wait_for(entered.wait(), 2)
            quit_task = asyncio.create_task(app.action_quit())
            await asyncio.sleep(0)
            assert not quit_task.done()
            assert not app._poll_task.cancelled()
            release.set()
            await asyncio.wait_for(quit_task, 2)
            assert completed.is_set()
            assert app._poll_task.done() and not app._poll_task.cancelled()
        assert service.process.poll() is None

    asyncio.run(check())
