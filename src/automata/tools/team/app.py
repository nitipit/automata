"""Read-only goal-scoped navigation through agents and their direct reports."""

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Footer, Static

from .hierarchy import agent_parents, direct_reports
from .panels import agent_panel
from .store import service_url, snapshot
from .view import agent_cells, table_columns


class Dashboard(App):
    TITLE = "Automata Team"
    BINDINGS = [
        Binding("right", "drill", "Selected agent", priority=True, key_display="→"),
        Binding("left", "back", "Back", priority=True, key_display="←"),
        Binding("enter", "details", "Selected panel", priority=True),
        Binding("q", "quit", "Close viewer only", priority=True),
    ]
    CSS = """
    Screen { background: #10161f; color: #dbe4ee; }
    #goal { height: auto; padding: 1 2 0 2; color: #a6cdf5; text-style: bold; }
    #heading { height: auto; padding: 0 2; color: #a6cdf5; text-style: bold; }
    #sample { height: auto; margin: 0 2 1 2; color: #8495a8; }
    #overview, #owner-overview { height: auto; padding: 1 2;
                border: round #38536c; background: #17212d; }
    #current-panel { height: auto; max-height: 14; margin: 0 2 1 2; }
    #selection { height: auto; max-height: 16; margin: 1 2; }
    #owner-heading { height: auto; color: #a6cdf5; text-style: bold; }
    #agents { height: 1fr; margin: 0 2; background: #10161f; border: round #38536c; }
    DataTable > .datatable--header { background: #243548; color: #dbe4ee; text-style: bold; }
    DataTable > .datatable--cursor { background: #294c6b; color: #ffffff; }
    #empty { height: auto; margin: 0 2; color: #8495a8; }
    Footer { background: #243548; }
    """

    def __init__(self, goal, url=None, poll=0.2):
        super().__init__()
        self._goal = goal
        self.url, self.poll = url or service_url(), poll
        self.state = {}
        self.route = None
        self.selected = None
        self.history = []
        self.rows = []
        self.revision = 0
        self._rendering = False
        self._detail_key = None
        self._poll_timer = None
        self._poll_task = None

    @property
    def goal(self):
        return self._goal

    def compose(self) -> ComposeResult:
        yield Static("Connecting…", id="goal", markup=False)
        yield Static("", id="heading", markup=False)
        yield Static("", id="sample", markup=False)
        with VerticalScroll(id="current-panel"):
            yield Static("", id="overview", markup=False)
        yield DataTable(id="agents", cursor_type="row", zebra_stripes=True)
        yield Static("", id="empty", markup=False)
        with VerticalScroll(id="selection"):
            yield Static("", id="owner-heading", markup=False)
            yield Static("", id="owner-overview", markup=False)
        yield Footer()

    async def on_mount(self):
        await self.refresh_snapshot()
        self._poll_timer = self.set_interval(self.poll, self.poll_snapshot)
        self.query_one("#agents", DataTable).focus()

    async def poll_snapshot(self):
        self._poll_task = asyncio.create_task(self.refresh_snapshot())
        await asyncio.shield(self._poll_task)

    async def action_quit(self):
        if self._poll_timer is not None:
            self._poll_timer.stop()
        if self._poll_task is not None:
            await asyncio.gather(self._poll_task, return_exceptions=True)
        self.exit()

    async def refresh_snapshot(self):
        try:
            # Never enumerate the tasks shelf: reports need no task publishing.
            fresh = await snapshot(self.goal, self.url, reports_only=True)
            agent_parents(fresh)
        except Exception as error:
            self.query_one("#overview", Static).update(f"Unavailable: {error}")
            return
        if fresh == self.state:
            return
        self.state = fresh
        self.revision += 1
        sample = any(
            a["context"]["source"] == "sample"
            or (a.get("report") is not None and a["report"]["tokens"]["source"] == "sample")
            for a in fresh["agents"].values()
        )
        self.query_one("#sample", Static).update("SAMPLE DATA" if sample else "")
        if self.route not in fresh["agents"]:
            self.route = fresh["goals"][self.goal]["manager_id"]
            self.history = []
        self.render_view()

    def on_resize(self, event):
        if self.route is not None:
            self.render_view(width=event.size.width)

    def render_view(self, width=None):
        table = self.query_one("#agents", DataTable)
        self.rows = [(agent["id"], agent) for agent in direct_reports(self.state, self.route)]
        if self.selected not in [key for key, _ in self.rows]:
            self.selected = self.rows[0][0] if self.rows else None
        self._rendering = True
        table.clear(columns=True)
        viewport_width = self.size.width if width is None else width
        columns = table_columns(viewport_width)
        for _, label, column_width in columns:
            table.add_column(label, width=column_width)
        for key, agent in self.rows:
            table.add_row(*agent_cells(agent, columns), key=key)
        if self.selected:
            table.move_cursor(row=[key for key, _ in self.rows].index(self.selected))
        self._rendering = False
        self.query_one("#empty", Static).update("No direct reports" if not self.rows else "")
        heading, overview = agent_panel(self.state, self.route, viewport_width - 12)
        self.query_one("#goal", Static).update(
            f"Goal #{self.goal} · {self.state['goals'][self.goal]['name']}"
        )
        self.query_one("#heading", Static).update(heading)
        self.query_one("#overview", Static).update(overview)
        self.show_details(width=viewport_width)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        key = str(event.row_key.value)
        if not self._rendering and key in [key for key, _ in self.rows]:
            self.selected = key
            self.show_details()

    def show_details(self, width=None):
        panel_width = (self.size.width if width is None else width) - 12
        if self.selected is None:
            heading, overview = "", "No selected agent"
        else:
            heading, overview = agent_panel(self.state, self.selected, panel_width)
        self.query_one("#owner-heading", Static).update(heading)
        self.query_one("#owner-overview", Static).update(overview)
        if self._detail_key != self.selected:
            self.query_one("#selection", VerticalScroll).scroll_home(animate=False)
            self._detail_key = self.selected

    def action_drill(self):
        if self.selected is None or not direct_reports(self.state, self.selected):
            return
        self.history.append((self.route, self.selected))
        self.route, self.selected = self.selected, None
        self.render_view()

    def action_back(self):
        if self.history:
            self.route, self.selected = self.history.pop()
            self.render_view()

    def action_details(self):
        widget = self.query_one("#selection", VerticalScroll)
        widget.display = not widget.display
