"""Monitoring baseline: time contracts remain independent of dashboard navigation."""
from datetime import UTC, datetime

import pytest

from automata.apps.dashboard.activity import aggregate, bucket_bounds, make_window

NOW = datetime(2026, 9, 28, 10, tzinfo=UTC)


@pytest.mark.parametrize("kwargs", [
    {"timezone": "Not/AZone"}, {"range_name": "unknown"},
    {"range_name": "custom", "start": "2026-02-30", "end": "2026-03-01"},
    {"range_name": "custom", "start": "2026-09-28", "end": "2026-09-27"},
    {"range_name": "custom", "start": "2026-09-28", "end": "2026-09-29"},
    {"range_name": "custom", "start": "2024-01-01", "end": "2026-01-01"},
])
def test_invalid_windows(kwargs):
    with pytest.raises(ValueError):
        make_window(now=NOW, **kwargs)


@pytest.mark.parametrize(("day", "hours"), [("2026-03-08", 23), ("2025-11-02", 25)])
def test_dst_calendar_days(day, hours):
    window = make_window("custom", "America/New_York", day, day, now=NOW)
    bounds = bucket_bounds(window)
    assert len(bounds) == 1
    assert (bounds[0][1] - bounds[0][0]).total_seconds() == hours * 3600


def test_selection_and_half_open_bounds():
    window = make_window("7d", "UTC", skill="one", now=NOW)
    events = [("one", window.start), ("two", NOW.replace(hour=9)), ("one", window.end)]
    result = aggregate(events, window)
    assert result["total"] == sum(row["count"] for row in result["rows"]) == 1
    assert sum(row["count"] for row in result["timeline"]) == 1
    assert result["last24h"] == 1  # Independent of the selected skill.
    assert result["skillOptions"] == ["one", "two"]
    assert len(result["timeline"]) == 7


def test_rolling_hours_are_contiguous_across_dst():
    now = datetime(2025, 11, 2, 12, 30, tzinfo=UTC)
    window = make_window("24h", "America/New_York", now=now)
    bounds = bucket_bounds(window)
    assert bounds[0][0] == window.start and bounds[-1][1] == now
    assert all(left[1] == right[0] for left, right in zip(bounds, bounds[1:], strict=False))
    assert sum((end - start).total_seconds() for start, end in bounds) == 86400
