"""Project-scoped recorded loads, explicit time windows and zero-filled buckets."""

import importlib.util
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

STORE = Path.home() / ".pi/agent/extensions/skill-activity/store.py"
DATABASE = Path.home() / ".agents/var/tools/skill-activity/db"
COVERAGE = (
    "Zero means no recorded load in that bucket, not proof the recorder was active. "
    "Recording uptime and missing-event intervals are unknown."
)
NOTE = (
    "Observed complete SKILL.md reads for this project only. Review reads count too; "
    "partial reads, shell reads and unrecorded sessions may be missing. "
    "Loads do not prove successful use or skill quality. Tool-call usage is not measured."
)


@dataclass(frozen=True)
class Window:
    range: str
    timezone: ZoneInfo
    start: datetime
    end: datetime
    skill: str | None
    now: datetime

    @property
    def bucket(self):
        return "hour" if self.range == "24h" else "day"

    def public(self):
        return dict(
            range=self.range,
            timezone=self.timezone.key,
            start=self.start.isoformat(),
            end=self.end.isoformat(),
            skill=self.skill,
        )


def make_window(
    range_name="7d", timezone="Asia/Bangkok", start=None, end=None, skill=None, now=None
):
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValueError("Choose a valid IANA timezone, such as Asia/Bangkok or UTC.") from None
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("The clock must include a timezone.")
    now = now.astimezone(UTC)
    today = now.astimezone(zone).date()
    if range_name == "24h":
        beginning, ending = now - timedelta(hours=24), now
    elif range_name in ("7d", "30d"):
        first_day = today - timedelta(days=6 if range_name == "7d" else 29)
        beginning = datetime.combine(first_day, time.min, zone).astimezone(UTC)
        ending = now
    elif range_name == "custom":
        try:
            first_day, last_day = date.fromisoformat(start or ""), date.fromisoformat(end or "")
            if first_day.isoformat() != start or last_day.isoformat() != end:
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError("Custom range requires start and end in YYYY-MM-DD format.") from None
        if first_day > last_day:
            raise ValueError("Start date must not be after end date.")
        if last_day > today:
            raise ValueError("Custom dates cannot be in the future in the selected timezone.")
        if (last_day - first_day).days >= 366:
            raise ValueError("Custom range is limited to 366 calendar days.")
        beginning = datetime.combine(first_day, time.min, zone).astimezone(UTC)
        ending = min(
            datetime.combine(last_day + timedelta(days=1), time.min, zone).astimezone(UTC), now
        )
    else:
        raise ValueError("Range must be 24h, 7d, 30d, or custom.")
    return Window(range_name, zone, beginning, ending, skill or None, now)


def bucket_bounds(window):
    """UTC intervals; calendar-day lengths follow the selected zone, including DST."""
    bounds = []
    if window.bucket == "hour":
        cursor = (
            window.start.astimezone(window.timezone)
            .replace(minute=0, second=0, microsecond=0)
            .astimezone(UTC)
        )
        while cursor < window.end:
            following = cursor + timedelta(hours=1)
            bounds.append((max(cursor, window.start), min(following, window.end)))
            cursor = following
    else:
        day = window.start.astimezone(window.timezone).date()
        cursor = datetime.combine(day, time.min, window.timezone).astimezone(UTC)
        while cursor < window.end:
            day += timedelta(days=1)
            following = datetime.combine(day, time.min, window.timezone).astimezone(UTC)
            bounds.append((max(cursor, window.start), min(following, window.end)))
            cursor = following
    return bounds


def aggregate(events, window):
    """Events contain only (skill name, aware timestamp), never session IDs or text."""
    selected = [
        (name, stamp.astimezone(UTC))
        for name, stamp in events
        if window.start <= stamp < window.end and (window.skill is None or name == window.skill)
    ]
    counts = Counter(name for name, _ in selected)
    latest = {}
    for name, stamp in selected:
        latest[name] = max(latest.get(name, stamp), stamp)
    bounds = bucket_bounds(window)
    starts = [start for start, _ in bounds]
    bucket_counts = [0] * len(bounds)
    for _, stamp in selected:
        index = bisect_right(starts, stamp) - 1
        if index >= 0 and stamp < bounds[index][1]:
            bucket_counts[index] += 1
    timestamps = [stamp for _, stamp in selected]
    all_stamps = [stamp for _, stamp in events]
    return dict(
        total=len(selected),
        distinct=len(counts),
        last24h=sum(window.now - timedelta(hours=24) <= stamp < window.now for stamp in all_stamps),
        rows=[
            dict(name=name, count=count, latest=latest[name].isoformat())
            for name, count in sorted(counts.items(), key=lambda row: (-row[1], row[0]))
        ],
        first=min(timestamps).isoformat() if timestamps else None,
        latest=max(timestamps).isoformat() if timestamps else None,
        availableFirst=min(all_stamps).isoformat() if all_stamps else None,
        availableLatest=max(all_stamps).isoformat() if all_stamps else None,
        skillOptions=sorted({name for name, _ in events}),
        timeline=[
            dict(start=start.isoformat(), end=end.isoformat(), count=count)
            for (start, end), count in zip(bounds, bucket_counts, strict=True)
        ],
    )


def activity(project, window):
    result = dict(
        status="unavailable",
        total=None,
        distinct=None,
        last24h=None,
        rows=[],
        first=None,
        latest=None,
        invalid=0,
        source="~/.agents/var/tools/skill-activity/db",
        note=NOTE,
        coverageNote=COVERAGE,
        window=window.public(),
        bucket=window.bucket,
        timeline=[],
        skillOptions=[],
        availableFirst=None,
        availableLatest=None,
    )
    if not STORE.is_file() or not (DATABASE / "data.mdb").is_file():
        return result
    try:
        spec = importlib.util.spec_from_file_location("anatomy_skill_activity_contract", STORE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        events, invalid = [], 0
        with module.DB(str(DATABASE)) as db, db.transaction(write=False) as tx:
            for item in tx.shelf("skill_activations").items():
                raw = item.value
                if not isinstance(raw, dict) or raw.get("project") != str(project):
                    continue
                try:
                    record = module.SkillActivation(raw)
                    events.append((record["skill"], datetime.fromisoformat(record["timestamp"])))
                except (module.Model.Error, ValueError, TypeError):
                    invalid += 1
        result.update(aggregate(events, window), status="ready", invalid=invalid)
    except Exception as error:
        result["error"] = type(error).__name__
    return result
