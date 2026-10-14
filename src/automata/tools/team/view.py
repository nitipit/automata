"""One current-report projection shared by panels and direct-agent table rows."""

from datetime import datetime
from zoneinfo import ZoneInfo

from .hierarchy import agent_path


def compact(value):
    return (
        "unavailable"
        if value is None
        else (f"{value / 1000:.1f}k" if value >= 1000 else str(value))
    )


def seconds(value):
    if value is None:
        return "unavailable"
    if value >= 3600:
        return f"{value / 3600:g}h"
    if value >= 60:
        return f"{value / 60:g}m"
    return f"{value:g}s"


def timestamp(value):
    if value is None:
        return "unavailable"
    return datetime.fromisoformat(value).astimezone(ZoneInfo("Asia/Bangkok")).strftime("%H:%M:%S")


def time_cell(report):
    estimate = report["estimate"]
    low, high = estimate["min_seconds"], estimate["max_seconds"]
    duration = seconds(low) if low == high else f"{seconds(low)}–{seconds(high)}"
    if low is None and high is None and estimate["target_finish"] is not None:
        duration = "target " + timestamp(estimate["target_finish"])
    return f"{seconds(report['elapsed_seconds'])} / {duration}"


def token_count(report):
    tokens = report["tokens"]
    values = [tokens[key] for key in ("input", "output", "cache_write")]
    return None if any(value is None for value in values) else sum(values)


def tokens_cell(report):
    count = token_count(report)
    return compact(count) + (f" [{report['tokens']['source']}]" if count is not None else "")


def context_cell(agent):
    ctx = agent["context"]
    used, cap = ctx["used_tokens"], ctx["capacity_tokens"]
    if used is None or cap is None:
        return "unavailable"
    return f"{used / cap * 100:.1f}% [{ctx['source']}]"


def report_projection(agent):
    """No task access, counts, progress inference or subtree aggregation."""
    report = agent.get("report")
    summary = "No current work report."
    if report is not None:
        summary = report["summary"]
        if report["status"] == "blocked":
            summary += " — Blocker: " + report["blocker"]
    return dict(
        agent=f"{agent['name']} · {agent['model']}/{agent['thinking']}",
        summary=summary,
        status=report["status"].title() if report is not None else "Unavailable",
        timestamp=timestamp(report["status_changed_at"]) if report is not None else "unavailable",
        time=time_cell(report) if report is not None else "unavailable",
        tokens=tokens_cell(report) if report is not None else "unavailable",
        context=context_cell(agent),
    )


def summary_fields(state, aid):
    fields = report_projection(state["agents"][aid])
    return agent_path(state, aid), [
        ("Agent", fields["agent"]),
        ("Summary", fields["summary"]),
        ("Status", fields["status"]),
        ("Time", fields["time"]),
        ("Usage", fields["tokens"] + " tokens · context " + fields["context"]),
    ]


def table_columns(screen_width):
    full = [
        ("status", "Status", 8),
        ("agent", "Agent", 27),
        ("summary", "Work", 23),
        ("timestamp", "Timestamp", 10),
        ("time", "Time", 22),
        ("tokens", "Tokens", 20),
        ("context", "Context %", 23),
    ]
    budget = max(6, screen_width - 8)
    if sum(width + 2 for _, _, width in full) <= budget:
        return full
    minimum = dict(status=1, agent=8, summary=12, timestamp=5, time=13, tokens=11, context=11)
    columns = [(key, label, minimum[key]) for key, label, _ in full]
    for omit in ("context", "timestamp", "tokens", "time", "agent"):
        if sum(width + 2 for _, _, width in columns) <= budget:
            break
        columns = [column for column in columns if column[0] != omit]
    widths = {key: width for key, _, width in columns}
    widths["summary"] = max(1, min(widths["summary"], budget - widths["status"] - 4))
    spare = budget - sum(widths[key] + 2 for key, _, _ in columns)
    for key in ("summary", "agent", "time", "tokens", "context", "timestamp", "status"):
        if key in widths:
            maximum = next(width for field, _, width in full if field == key)
            growth = min(spare, maximum - widths[key])
            widths[key] += growth
            spare -= growth
    labels = {"status": "S", "timestamp": "Stamp"}
    return [
        (key, labels.get(key, label) if len(label) > widths[key] else label, widths[key])
        for key, label, _ in columns
    ]


def agent_cells(agent, columns):
    """Only width-specific compression; facts come from the shared projection."""
    fields = report_projection(agent)
    widths = {key: width for key, _, width in columns}
    if widths["status"] < 7:
        fields["status"] = {"Pending": "○", "Working": "●", "Done": "✓", "Blocked": "!"}.get(
            fields["status"], "—"
        )
    if widths.get("agent", 27) < 27:
        fields["agent"] = agent["name"]
    if widths.get("timestamp", 8) < 8 and fields["timestamp"] != "unavailable":
        fields["timestamp"] = fields["timestamp"][:5]
    if widths.get("time", 22) < 22:
        fields["time"] = fields["time"].replace("unavailable", "—")
    for key in ("tokens", "context"):
        if widths.get(key, 23) < 20:
            fields[key] = fields[key].split(" [", 1)[0]
    return [fields[key] for key, _, _ in columns]
