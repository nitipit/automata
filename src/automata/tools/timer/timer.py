#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["cyclopts>=4.11.1", "apscheduler>=3.11,<4"]
# ///
"""Repo-local command timer for agent-friendly delayed and recurring ticks."""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cyclopts import App, Parameter

DEFAULT_STATE_DIR = Path(
    os.environ.get("AUTOMATA_TIMER_STATE_DIR", ".agents/var/skills/automata-timer")
).expanduser()

app = App(
    name="timer",
    help=(
        "Schedule explicit commands after a delay, at a time, or on a guarded interval. "
        "Jobs, locks, and command logs live outside installed tool code under "
        f"{DEFAULT_STATE_DIR} by default; override with AUTOMATA_TIMER_STATE_DIR or "
        "--state-dir. Scheduling proves only that the command is attempted, not that its "
        "recipient acts or returns a response. Use status and logs to verify execution, "
        "cancel obsolete jobs, and cleanup terminal records."
    ),
)

TERMINAL_STATUSES = {"completed", "failed", "canceled"}
DURATION_PATTERN = re.compile(r"^(?P<amount>\d+)(?P<unit>[smhd])$")

StateDirOption = Annotated[
    Path,
    Parameter(
        help="Timer state directory; defaults to AUTOMATA_TIMER_STATE_DIR or "
        ".agents/var/skills/automata-timer."
    ),
]
CommandArg = Annotated[
    list[str],
    Parameter(help="Command to run. Put it after --, for example: -- echo ok"),
]
NameOption = Annotated[
    str | None,
    Parameter(help="Optional unique human-readable job name."),
]
GraceOption = Annotated[
    str | None,
    Parameter(help="Optional lateness grace, such as 30s or 5m; omitted means no expiry."),
]


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_instant(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        message = "time must be an ISO datetime, such as 2026-07-10T15:30:00+07:00"
        raise ValueError(message) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone(UTC)


def parse_duration(value: str) -> int:
    match = DURATION_PATTERN.match(value.strip())
    if match is None:
        raise ValueError("duration must look like 10s, 5m, 2h, or 1d")
    amount = int(match.group("amount"))
    if amount <= 0:
        raise ValueError("duration must be positive")
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return amount * multipliers[match.group("unit")]


def parse_timezone(value: str) -> str:
    """Validate and retain an explicit IANA timezone name."""
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"unknown timezone: {value}") from error
    return value


def schedule_trigger(job: dict[str, Any]) -> Any:
    """Build an APScheduler 3.x trigger without starting a scheduler service."""
    try:
        if job.get("schedule_kind") == "cron":
            from apscheduler.triggers.cron import CronTrigger

            return CronTrigger.from_crontab(
                str(job["cron_expression"]), timezone=ZoneInfo(str(job["timezone"]))
            )
        if job.get("schedule_kind") == "every" and job.get("mode") == "fixed-rate":
            from apscheduler.triggers.interval import IntervalTrigger

            return IntervalTrigger(
                seconds=int(job["interval_seconds"]),
                start_date=parse_instant(str(job["schedule_anchor"])),
                timezone=UTC,
            )
    except ModuleNotFoundError as error:
        raise ValueError("APScheduler 3.x is required for cron and fixed-rate schedules") from error
    raise ValueError(f"job has no APScheduler trigger: {job.get('schedule_kind')}")


def next_scheduled_fire(job: dict[str, Any], now: datetime) -> datetime | None:
    """Return the next fire strictly after now, skipping all missed occurrences."""
    trigger = schedule_trigger(job)
    if job.get("schedule_kind") == "every":
        anchor = parse_instant(str(job["schedule_anchor"]))
        if now < anchor:
            fire_time = trigger.get_next_fire_time(None, now)
        else:
            interval = int(job["interval_seconds"])
            elapsed_intervals = int((now - anchor).total_seconds() // interval) + 1
            previous = anchor + timedelta(seconds=(elapsed_intervals - 1) * interval)
            fire_time = trigger.get_next_fire_time(previous, now)
    else:
        # Passing now as the previous occurrence advances directly past all
        # overdue calendar occurrences instead of replaying them one by one.
        fire_time = trigger.get_next_fire_time(now, now)
    return fire_time.astimezone(UTC) if fire_time is not None else None


def cron_first_fire(expression: str, timezone: str, now: datetime) -> datetime:
    trigger = schedule_trigger(
        {
            "schedule_kind": "cron",
            "cron_expression": expression,
            "timezone": parse_timezone(timezone),
        }
    )
    fire_time = trigger.get_next_fire_time(None, now)
    if fire_time is None:
        raise ValueError("cron expression has no future run")
    return fire_time.astimezone(UTC)


def is_late(job: dict[str, Any], now: datetime) -> bool:
    grace_seconds = job.get("grace_seconds")
    if grace_seconds is None:
        return False
    due = parse_instant(str(job["next_run_at"]))
    return now > due + timedelta(seconds=int(grace_seconds))


def next_recurring_run(job: dict[str, Any], now: datetime) -> datetime | None:
    if job.get("schedule_kind") == "cron" or job.get("mode", "after-completion") == "fixed-rate":
        return next_scheduled_fire(job, now)
    interval_seconds = int(job.get("interval_seconds") or 0)
    return now + timedelta(seconds=interval_seconds)


def ensure_state_dirs(state_dir: Path) -> None:
    (state_dir / "jobs").mkdir(parents=True, exist_ok=True)
    (state_dir / "logs").mkdir(parents=True, exist_ok=True)
    (state_dir / "locks").mkdir(parents=True, exist_ok=True)


def job_path(state_dir: Path, job_id: str) -> Path:
    return state_dir / "jobs" / f"{job_id}.json"


def lock_path(state_dir: Path, job_id: str) -> Path:
    return state_dir / "locks" / f"{job_id}.lock"


def job_log_dir(state_dir: Path, job_id: str) -> Path:
    return state_dir / "logs" / job_id


def load_job(state_dir: Path, job_id: str) -> dict[str, Any]:
    path = job_path(state_dir, job_id)
    if not path.exists():
        raise ValueError(f"job not found: {job_id}")
    return json.loads(path.read_text())


def save_job(state_dir: Path, job: dict[str, Any]) -> None:
    path = job_path(state_dir, job["id"])
    temp = path.with_suffix(".json.tmp")
    job["updated_at"] = iso_now()
    temp.write_text(json.dumps(job, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


@contextmanager
def state_lock(state_dir: Path) -> Iterator[None]:
    """Serialize lease acquisition and record removal; never unlink this lock."""
    ensure_state_dirs(state_dir)
    with (state_dir / "locks" / ".state.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


@contextmanager
def locked_job(state_dir: Path, job_id: str) -> Iterator[dict[str, Any]]:
    with state_lock(state_dir):
        with lock_path(state_dir, job_id).open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield load_job(state_dir, job_id)


@contextmanager
def active_job(state_dir: Path, job_id: str) -> Iterator[None]:
    """Keep records alive for the full worker/executor lifetime, including log writes."""
    with state_lock(state_dir):
        load_job(state_dir, job_id)
        handle = (state_dir / "locks" / f"{job_id}.active").open("a")
        fcntl.flock(handle, fcntl.LOCK_SH)
    try:
        yield
    finally:
        handle.close()


def process_identity(pid: int) -> str | None:
    """Linux start time guards cancellation against recycled process IDs."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def process_group_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def list_jobs(state_dir: Path) -> list[dict[str, Any]]:
    ensure_state_dirs(state_dir)
    jobs = []
    for path in sorted((state_dir / "jobs").glob("*.json")):
        try:
            jobs.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"warning: could not parse {path}", file=sys.stderr)
    jobs.sort(key=lambda item: (item.get("next_run_at") or "", item.get("created_at") or ""))
    return jobs


def resolve_job_id(state_dir: Path, job_id_or_name: str) -> str:
    if job_path(state_dir, job_id_or_name).exists():
        return job_id_or_name
    matches = [job for job in list_jobs(state_dir) if job.get("name") == job_id_or_name]
    if not matches:
        raise ValueError(f"job not found: {job_id_or_name}")
    if len(matches) > 1:
        ids = ", ".join(job["id"] for job in matches)
        raise ValueError(f"name is ambiguous: {job_id_or_name} ({ids})")
    return str(matches[0]["id"])


def validate_command(command: list[str]) -> None:
    if not command:
        raise ValueError("command is required; put it after --, for example: -- echo ok")


def create_job(
    *,
    state_dir: Path,
    command: list[str],
    schedule_kind: str,
    next_run_at: datetime,
    name: str | None,
    interval_seconds: int | None = None,
    max_runs: int = 1,
    forever: bool = False,
    until: datetime | None = None,
    mode: str = "after-completion",
    grace_seconds: int | None = None,
    timezone: str | None = None,
    cron_expression: str | None = None,
    schedule_anchor: datetime | None = None,
) -> dict[str, Any]:
    validate_command(command)
    recurring_schedule = schedule_kind in {"every", "cron"}
    if recurring_schedule and mode not in {"fixed-rate", "after-completion"}:
        raise ValueError("mode must be fixed-rate or after-completion")
    if not recurring_schedule and mode != "after-completion":
        raise ValueError("mode only applies to recurring schedules")
    if grace_seconds is not None and grace_seconds < 0:
        raise ValueError("grace duration must not be negative")
    if schedule_kind == "cron":
        if not cron_expression:
            raise ValueError("cron expression is required")
        if not timezone:
            raise ValueError("cron timezone is required")
        timezone = parse_timezone(timezone)
    ensure_state_dirs(state_dir)
    job_id = f"{utc_now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    job = {
        "id": job_id,
        "name": name,
        "status": "pending",
        "schedule_kind": schedule_kind,
        "command": command,
        "created_at": iso_now(),
        "updated_at": iso_now(),
        "next_run_at": next_run_at.isoformat(),
        "interval_seconds": interval_seconds,
        "mode": mode,
        "grace_seconds": grace_seconds,
        "timezone": timezone,
        "cron_expression": cron_expression,
        "schedule_anchor": (schedule_anchor or next_run_at).isoformat(),
        "run_count": 0,
        "max_runs": max_runs,
        "forever": forever,
        "until": until.isoformat() if until else None,
        "worker_pid": None,
        "command_pid": None,
        "last_exit_code": None,
        "last_run_at": None,
        "finished_at": None,
        "log_files": [],
    }
    save_job(state_dir, job)
    return job


def maybe_start_worker(state_dir: Path, job_id: str, start: bool) -> None:
    if not start:
        return
    with locked_job(state_dir, job_id) as job:
        if job.get("status") in TERMINAL_STATUSES or job.get("status") == "canceling":
            return
        worker_log = job_log_dir(state_dir, job_id) / "worker.log"
        worker_log.parent.mkdir(parents=True, exist_ok=True)
        with worker_log.open("ab") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "worker",
                    job_id,
                    "--state-dir",
                    str(state_dir),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        job["worker_pid"] = process.pid
        save_job(state_dir, job)


def is_due(job: dict[str, Any], now: datetime | None = None) -> bool:
    if job.get("status") in TERMINAL_STATUSES or job.get("status") in {"running", "canceling"}:
        return False
    next_run_at = job.get("next_run_at")
    if not next_run_at:
        return False
    return parse_instant(next_run_at) <= (now or utc_now())


def command_preview(command: list[str], max_length: int = 72) -> str:
    text = " ".join(command)
    return text if len(text) <= max_length else text[: max_length - 1] + "…"


def run_log_path(state_dir: Path, job_id: str, run_number: int) -> Path:
    path = job_log_dir(state_dir, job_id) / f"run-{run_number:03d}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def kill_pid(pid: int, *, process_group: bool = False) -> bool:
    try:
        if process_group:
            os.killpg(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    return True


def execute_due_job(state_dir: Path, job_id: str) -> bool:
    try:
        with active_job(state_dir, job_id):
            return _execute_due_job(state_dir, job_id)
    except ValueError:
        if not job_path(state_dir, job_id).exists():
            return False  # A queued scheduler snapshot may outlive cleanup.
        raise


def _execute_due_job(state_dir: Path, job_id: str) -> bool:
    with locked_job(state_dir, job_id) as job:
        if not is_due(job):
            return False
        now = utc_now()
        until_value = job.get("until")
        if until_value and now > parse_instant(until_value):
            job["status"] = "completed"
            job["worker_pid"] = None
            job["next_run_at"] = None
            job["finished_at"] = iso_now()
            job["skip_reason"] = "past-until"
            save_job(state_dir, job)
            return False

        recurring = job.get("schedule_kind") in {"every", "cron"}
        if is_late(job, now):
            if not recurring:
                job["status"] = "completed"
                job["worker_pid"] = None
                job["next_run_at"] = None
                job["finished_at"] = iso_now()
                job["skip_reason"] = "expired"
                save_job(state_dir, job)
                return False
            next_run_at = next_recurring_run(job, now)
            if next_run_at is None or (until_value and next_run_at > parse_instant(until_value)):
                job["status"] = "completed"
                job["worker_pid"] = None
                job["next_run_at"] = None
                job["finished_at"] = iso_now()
                job["skip_reason"] = "stale-occurrence"
            else:
                job["status"] = "pending"
                job["next_run_at"] = next_run_at.isoformat()
                job["skip_reason"] = "stale-occurrence"
            save_job(state_dir, job)
            return False

        run_number = int(job.get("run_count", 0)) + 1
        log_path = run_log_path(state_dir, job_id, run_number)
        job.pop("skip_reason", None)
        job["status"] = "running"
        job["last_run_at"] = iso_now()
        job["command_pid"] = None
        log_files = list(job.get("log_files") or [])
        log_files.append(str(log_path.relative_to(state_dir)))
        job["log_files"] = log_files
        save_job(state_dir, job)
        command = list(job["command"])

    exit_code = 1
    command_pid: int | None = None
    with log_path.open("ab") as log:
        started = iso_now()
        log.write(f"# timer job {job_id} run {run_number} started {started}\n".encode())
        log.write(("# command: " + " ".join(command) + "\n").encode())
        log.flush()
        try:
            with locked_job(state_dir, job_id) as job:
                if job.get("status") in {"canceling", "canceled"}:
                    job["status"] = "canceled"
                    job["finished_at"] = iso_now()
                    save_job(state_dir, job)
                    return True
                process = subprocess.Popen(
                    command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                command_pid = process.pid
                job["command_pid"] = command_pid
                job["command_identity"] = process_identity(command_pid)
                save_job(state_dir, job)
            exit_code = process.wait()
        except FileNotFoundError as error:
            log.write(f"command not found: {error.filename}\n".encode())
            exit_code = 127
        except Exception as error:  # noqa: BLE001 - surface command launch failures in the job log.
            log.write(f"timer command error: {error}\n".encode())
            exit_code = 1
        finally:
            finished = (
                f"# timer job {job_id} run {run_number} finished {iso_now()} exit={exit_code}\n"
            )
            log.write(finished.encode())

    with locked_job(state_dir, job_id) as job:
        if job.get("status") in {"canceling", "canceled"}:
            if not process_group_alive(job.get("command_pid")):
                job["status"] = "canceled"
                job["command_pid"] = None
            job["last_exit_code"] = exit_code
            job["finished_at"] = iso_now()
            save_job(state_dir, job)
            return True

        job["run_count"] = run_number
        job["last_exit_code"] = exit_code
        # Retain a surviving command group so cleanup cannot discard its evidence.
        if not process_group_alive(job.get("command_pid")):
            job["command_pid"] = None
        max_runs = int(job.get("max_runs") or 0)
        forever = bool(job.get("forever"))
        until_value = job.get("until")
        recurring = job.get("schedule_kind") in {"every", "cron"}
        has_more_runs = recurring and (forever or run_number < max_runs)
        if recurring and has_more_runs and process_group_alive(job.get("command_pid")):
            # Never overwrite the identity of an outstanding process group on a rerun.
            job["status"] = "failed"
            job["next_run_at"] = None
            job["finished_at"] = iso_now()
            save_job(state_dir, job)
            return True
        if recurring and has_more_runs:
            next_run_at = next_recurring_run(job, utc_now())
            if next_run_at is not None and not (
                until_value and next_run_at > parse_instant(until_value)
            ):
                job["status"] = "pending"
                job["next_run_at"] = next_run_at.isoformat()
                save_job(state_dir, job)
                return True

        job["status"] = "completed" if exit_code == 0 else "failed"
        job["worker_pid"] = None
        job["next_run_at"] = None
        job["finished_at"] = iso_now()
        save_job(state_dir, job)
    return True


def print_scheduled(job: dict[str, Any], *, started: bool) -> None:
    print(f"scheduled: {job['id']}")
    if job.get("name"):
        print(f"name: {job['name']}")
    print(f"next run: {job['next_run_at']}")
    print(f"command: {command_preview(job['command'])}")
    print(f"worker started: {str(started).lower()}")


@app.command(name="after")
def after(
    delay: Annotated[str, Parameter(help="Delay before first run, such as 10s, 5m, or 2h.")],
    command: CommandArg,
    name: NameOption = None,
    grace: GraceOption = None,
    start: Annotated[
        bool,
        Parameter(help="Start a detached worker for this job immediately."),
    ] = True,
    state_dir: StateDirOption = DEFAULT_STATE_DIR,
) -> None:
    """Schedule a one-shot command after a duration."""
    seconds = parse_duration(delay)
    job = create_job(
        state_dir=state_dir,
        command=command,
        schedule_kind="after",
        next_run_at=utc_now() + timedelta(seconds=seconds),
        name=name,
        grace_seconds=parse_duration(grace) if grace else None,
    )
    maybe_start_worker(state_dir, job["id"], start)
    print_scheduled(load_job(state_dir, job["id"]), started=start)


@app.command(name="at")
def at(
    when: Annotated[
        str,
        Parameter(help="ISO datetime, such as 2026-07-10T15:30:00+07:00."),
    ],
    command: CommandArg,
    name: NameOption = None,
    grace: GraceOption = None,
    start: Annotated[
        bool,
        Parameter(help="Start a detached worker for this job immediately."),
    ] = True,
    state_dir: StateDirOption = DEFAULT_STATE_DIR,
) -> None:
    """Schedule a one-shot command at an ISO datetime."""
    job = create_job(
        state_dir=state_dir,
        command=command,
        schedule_kind="at",
        next_run_at=parse_instant(when),
        name=name,
        grace_seconds=parse_duration(grace) if grace else None,
    )
    maybe_start_worker(state_dir, job["id"], start)
    print_scheduled(load_job(state_dir, job["id"]), started=start)


@app.command(name="every")
def every(
    interval: Annotated[str, Parameter(help="Interval between runs, such as 10s, 5m, or 2h.")],
    command: CommandArg,
    name: NameOption = None,
    mode: Annotated[
        str,
        Parameter(help="Recurrence mode: fixed-rate or after-completion (default)."),
    ] = "after-completion",
    grace: GraceOption = None,
    max_runs: Annotated[
        int | None,
        Parameter(help="Maximum runs; required unless --forever is used."),
    ] = None,
    forever: Annotated[
        bool,
        Parameter(help="Allow an unbounded recurring job explicitly."),
    ] = False,
    until: Annotated[
        str | None,
        Parameter(help="Optional datetime after which no next run is scheduled."),
    ] = None,
    start: Annotated[
        bool,
        Parameter(help="Start a detached worker for this job immediately."),
    ] = True,
    state_dir: StateDirOption = DEFAULT_STATE_DIR,
) -> None:
    """Schedule a guarded recurring command."""
    seconds = parse_duration(interval)
    if not forever and max_runs is None:
        raise ValueError("every requires --max-runs unless --forever is explicit")
    if max_runs is not None and max_runs <= 0:
        raise ValueError("--max-runs must be positive")
    until_dt = parse_instant(until) if until else None
    first_run = utc_now() + timedelta(seconds=seconds)
    job = create_job(
        state_dir=state_dir,
        command=command,
        schedule_kind="every",
        next_run_at=first_run,
        name=name,
        interval_seconds=seconds,
        max_runs=max_runs or 0,
        forever=forever,
        until=until_dt,
        mode=mode,
        grace_seconds=parse_duration(grace) if grace else None,
        schedule_anchor=first_run,
    )
    maybe_start_worker(state_dir, job["id"], start)
    print_scheduled(load_job(state_dir, job["id"]), started=start)


@app.command(name="cron")
def cron(
    expression: Annotated[
        str,
        Parameter(help="Five-field APScheduler crontab expression."),
    ],
    command: CommandArg,
    timezone: Annotated[
        str,
        Parameter(name="--timezone", help="Required IANA timezone, such as Asia/Bangkok."),
    ],
    name: NameOption = None,
    grace: GraceOption = None,
    max_runs: Annotated[
        int | None,
        Parameter(help="Maximum runs; required unless --forever is used."),
    ] = None,
    forever: Annotated[
        bool,
        Parameter(help="Allow an unbounded recurring job explicitly."),
    ] = False,
    until: Annotated[
        str | None,
        Parameter(help="Optional datetime after which no next run is scheduled."),
    ] = None,
    start: Annotated[
        bool,
        Parameter(help="Start a detached worker for this job immediately."),
    ] = True,
    state_dir: StateDirOption = DEFAULT_STATE_DIR,
) -> None:
    """Schedule a calendar-recurring command in an explicit IANA timezone."""
    if not forever and max_runs is None:
        raise ValueError("cron requires --max-runs unless --forever is explicit")
    if max_runs is not None and max_runs <= 0:
        raise ValueError("--max-runs must be positive")
    timezone = parse_timezone(timezone)
    first_run = cron_first_fire(expression, timezone, utc_now())
    until_dt = parse_instant(until) if until else None
    job = create_job(
        state_dir=state_dir,
        command=command,
        schedule_kind="cron",
        next_run_at=first_run,
        name=name,
        max_runs=max_runs or 0,
        forever=forever,
        until=until_dt,
        mode="fixed-rate",
        grace_seconds=parse_duration(grace) if grace else None,
        timezone=timezone,
        cron_expression=expression,
        schedule_anchor=first_run,
    )
    maybe_start_worker(state_dir, job["id"], start)
    print_scheduled(load_job(state_dir, job["id"]), started=start)


@app.command(name="run")
def run_scheduler(
    once: Annotated[bool, Parameter(help="Scan due jobs once and exit.")] = False,
    poll_interval: Annotated[
        float,
        Parameter(help="Seconds between scans when running continuously."),
    ] = 1.0,
    state_dir: StateDirOption = DEFAULT_STATE_DIR,
) -> None:
    """Run due jobs from the persisted queue."""
    if poll_interval <= 0:
        raise ValueError("--poll-interval must be positive")
    while True:
        ran = 0
        for job in list_jobs(state_dir):
            if execute_due_job(state_dir, job["id"]):
                ran += 1
        print(f"due jobs executed: {ran}")
        if once:
            return
        time.sleep(poll_interval)


@app.command(name="worker")
def worker(
    job_id: Annotated[str, Parameter(help="Job id for the detached worker to manage.")],
    state_dir: StateDirOption = DEFAULT_STATE_DIR,
) -> None:
    """Run one job until it reaches a terminal state. Intended for detached workers."""
    try:
        with active_job(state_dir, job_id):
            while True:
                job = load_job(state_dir, job_id)
                if job.get("status") in TERMINAL_STATUSES or job.get("status") == "canceling":
                    return
                next_run_at = job.get("next_run_at")
                if next_run_at is None:
                    return
                delay = max(0.0, (parse_instant(next_run_at) - utc_now()).total_seconds())
                if delay > 0:
                    time.sleep(min(delay, 5.0))
                    continue
                execute_due_job(state_dir, job_id)
    except ValueError:
        if job_path(state_dir, job_id).exists():
            raise


@app.command(name="status")
def status(
    state_dir: StateDirOption = DEFAULT_STATE_DIR,
) -> None:
    """Print persisted timer jobs."""
    jobs = list_jobs(state_dir)
    if not jobs:
        print("no jobs")
        return
    print(f"{'id':<24} {'name':<20} {'status':<10} {'runs':<9} {'next_run_at':<32} command")
    for job in jobs:
        max_runs = "∞" if job.get("forever") else str(job.get("max_runs") or 0)
        runs = f"{job.get('run_count', 0)}/{max_runs}"
        print(
            f"{job['id']:<24} "
            f"{str(job.get('name') or '-'):<20.20} "
            f"{job.get('status', '-'):<10} "
            f"{runs:<9} "
            f"{str(job.get('next_run_at') or '-'):<32.32} "
            f"{command_preview(job.get('command') or [])}"
        )


@app.command(name="cancel")
def cancel(
    job: Annotated[str, Parameter(help="Job id or unique job name to cancel.")],
    state_dir: StateDirOption = DEFAULT_STATE_DIR,
) -> None:
    """Request cancellation without deleting evidence or killing its writer."""
    job_id = resolve_job_id(state_dir, job)
    with locked_job(state_dir, job_id) as item:
        if item.get("status") in TERMINAL_STATUSES:
            print(f"already terminal: {job_id} status={item.get('status')}")
            return
        item["status"] = "canceling"
        item["next_run_at"] = None
        # Signal while holding the launch lock; never clear an unconfirmed PID.
        command_pid = item.get("command_pid")
        if isinstance(command_pid, int):
            identity = item.get("command_identity")
            if identity is not None and identity == process_identity(command_pid):
                kill_pid(command_pid, process_group=True)
            elif process_group_alive(command_pid):
                print("process identity unavailable or changed; not signaling", file=sys.stderr)
        if not process_group_alive(command_pid):
            item["status"] = "canceled"
            item["command_pid"] = None
            item["finished_at"] = iso_now()
        save_job(state_dir, item)
    if item["status"] == "canceling":
        print(f"cancellation requested: {job_id}; execution stop not confirmed")
    else:
        print(f"canceled: {job_id}; cleanup still checks worker inactivity")


@app.command(name="logs")
def logs(
    job: Annotated[str, Parameter(help="Job id or unique job name to inspect.")],
    all_runs: Annotated[
        bool,
        Parameter(name="--all", help="Print all run logs instead of only the latest."),
    ] = False,
    state_dir: StateDirOption = DEFAULT_STATE_DIR,
) -> None:
    """Print a job's command logs."""
    job_id = resolve_job_id(state_dir, job)
    item = load_job(state_dir, job_id)
    log_files = list(item.get("log_files") or [])
    if not log_files:
        print(f"no run logs for {job_id}")
        return
    selected = log_files if all_runs else log_files[-1:]
    for index, relative in enumerate(selected):
        path = state_dir / relative
        if index:
            print()
        print(f"==> {path} <==")
        if path.exists():
            print(path.read_text(), end="")
        else:
            print("missing log file")


def remove_terminal_job(state_dir: Path, job_id: str, cutoff: datetime | None) -> bool:
    with locked_job(state_dir, job_id) as job:
        if job.get("status") not in TERMINAL_STATUSES | {"canceling"}:
            raise ValueError(f"job is not terminal: {job_id}")
        lease = state_dir / "locks" / f"{job_id}.active"
        with lease.open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError(f"job still has an active worker or executor: {job_id}") from error
            if any(process_group_alive(job.get(key)) for key in ("command_pid", "worker_pid")):
                raise ValueError(f"job process shutdown is not confirmed: {job_id}")
            if job.get("status") == "canceling":
                job["status"] = "canceled"
                job["finished_at"] = iso_now()
                job["command_pid"] = None
                save_job(state_dir, job)
            finished = job.get("finished_at") or job.get("updated_at")
            if cutoff is not None and (
                not isinstance(finished, str) or parse_instant(finished) > cutoff
            ):
                return False
            # Delete logs first so failure leaves the record discoverable for retry.
            logs_dir = job_log_dir(state_dir, job_id)
            if logs_dir.exists():
                shutil.rmtree(logs_dir)
            job_path(state_dir, job_id).unlink()
            lock_path(state_dir, job_id).unlink(missing_ok=True)
            lease.unlink(missing_ok=True)
            return True


@app.command(name="cleanup")
def cleanup(
    job: Annotated[str | None, Parameter(help="Exact job id or unique name to remove.")] = None,
    older_than: Annotated[
        str | None,
        Parameter(help="Remove terminal jobs older than this duration; default 7d."),
    ] = None,
    all_terminal: Annotated[
        bool,
        Parameter(name="--all", help="Select all terminal jobs regardless of age."),
    ] = False,
    state_dir: StateDirOption = DEFAULT_STATE_DIR,
) -> None:
    """Permanently remove inactive terminal job records and logs; never cancel jobs."""
    if sum((job is not None, older_than is not None, all_terminal)) > 1:
        raise ValueError("choose one selector: job, --older-than, or --all")
    cutoff = (
        None
        if job is not None or all_terminal
        else (utc_now() - timedelta(seconds=parse_duration(older_than or "7d")))
    )
    if job is not None:
        removed = int(remove_terminal_job(state_dir, resolve_job_id(state_dir, job), cutoff))
    else:
        removed = 0
        for item in list_jobs(state_dir):
            if item.get("status") not in TERMINAL_STATUSES | {"canceling"}:
                continue
            try:
                removed += remove_terminal_job(state_dir, str(item["id"]), cutoff)
            except ValueError as error:
                print(f"skipped: {error}", file=sys.stderr)
    print(f"terminal jobs removed: {removed}")


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130) from None
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
