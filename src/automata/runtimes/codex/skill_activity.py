#!/usr/bin/env python3
"""Session-scoped native Codex skill insertion recorder and query/control CLI.

Explicit installed hook activation enrolls each thread at its first observation;
existing transcript history is never backfilled. Stdlib, no skill-file reads.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path

from skill_records import NAME, SkillRecords, absolute_metadata_path, event_id
from token_awareness import EVENTS, atomic_write
from token_records import CoverageError, identifier, scan, session_id

MAX_RECORDS = 10_000
SCOPE = (
    "Codex 0.159.0 native metadata-tagged local skill instruction insertions after "
    "enrollment, observed at supported hooks or explicit controls. Not all skill use: "
    "shell reads, scripts, resource-backed skills and cooperative reports are not counted. "
    "Discovery and mentions without successful insertion are not evidence. "
    "Counts prove insertion, not compliance or continued context presence. "
    "Lifetime retained observations, not active-branch state; no inherited backfill."
)


def load(path, thread):
    if not path.exists():
        return None
    try:
        if path.stat().st_size > 128 * 1024 * 1024:
            raise ValueError
        state = json.loads(path.read_text())
        fields = {
            "version",
            "thread",
            "project",
            "enabled",
            "enrolledAt",
            "enrollmentOrdinal",
            "throughOrdinal",
            "records",
            "capacitySkipped",
            "disabledSkipped",
        }
        if (
            set(state) != fields
            or state["version"] != 1
            or not absolute_metadata_path(state["project"])
            or state["thread"] != thread
            or type(state["enabled"]) is not bool
            or type(state["throughOrdinal"]) is not int
            or type(state["enrollmentOrdinal"]) is not int
            or not 0 <= state["enrollmentOrdinal"] <= state["throughOrdinal"]
            or not isinstance(state["records"], dict)
            or len(state["records"]) > MAX_RECORDS
            or type(state["capacitySkipped"]) is not int
            or state["capacitySkipped"] < 0
            or type(state["disabledSkipped"]) is not int
            or state["disabledSkipped"] < 0
        ):
            raise ValueError
        if datetime.fromisoformat(state["enrolledAt"]).utcoffset() is None:
            raise ValueError
        record_fields = {
            "eventId",
            "message",
            "part",
            "turn",
            "skill",
            "path",
            "timestamp",
            "ordinal",
            "evidenceKind",
            "runtime",
            "project",
            "thread",
            "session",
            "observedAt",
        }
        for key, record in state["records"].items():
            if (
                set(record) != record_fields
                or key != record["eventId"]
                or key != event_id(identifier(record["message"]), record["part"])
                or type(record["part"]) is not int
                or record["part"] < 0
                or not NAME.fullmatch(record["skill"])
                or not absolute_metadata_path(record["path"])
                or Path(record["path"]).name != "SKILL.md"
                or record["project"] != state["project"]
                or type(record["ordinal"]) is not int
                or record["thread"] != thread
                or record["runtime"] != "codex"
                or record["evidenceKind"] != "native_instruction_insertion"
                or not state["enrollmentOrdinal"] < record["ordinal"] <= state["throughOrdinal"]
            ):
                raise ValueError
            identifier(record["turn"])
            session_id(record["session"])
            for name in ("timestamp", "observedAt"):
                if datetime.fromisoformat(record[name]).utcoffset() is None:
                    raise ValueError
        return state
    except (ValueError, KeyError, TypeError, AttributeError):
        raise CoverageError("invalid saved skill state; not reset") from None


def records_view(state, limit, skill):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise CoverageError("limit must be from 1 to 100")
    selected = [r for r in state["records"].values() if skill is None or r["skill"] == skill]
    selected.sort(key=lambda r: (r["ordinal"], r["eventId"]), reverse=True)
    return {
        "retainedCount": len(state["records"]),
        "matchedCount": len(selected),
        "records": selected[:limit],
        "truncated": len(selected) > limit,
    }


def saved(root, thread, limit=20, skill=None):
    """Read one explicitly authorized atomic state snapshot, with no side effects.

    No lock file is needed: writers replace complete JSON atomically. A concurrent
    writer can make this snapshot stale, but cannot expose a partially written file.
    No transcript lookup, enrollment, namespace creation or state update occurs.
    """
    thread = session_id(thread)
    state = load(root / "skill-activity" / f"{thread}.json", thread)
    result = {
        "runtime": "codex",
        "thread": thread,
        "readOnly": True,
        "coverage": "saved-observations-only",
        "currentCoverage": "unknown; transcript not consulted",
        "scope": SCOPE,
        "available": state is not None,
    }
    if state is None:
        return {
            **result,
            "coverage": "no-saved-state; enrollment/history unknown",
            **records_view({"records": {}}, limit, skill),
        }
    return {
        **result,
        "project": state["project"],
        "enabledAtLastObservation": state["enabled"],
        "enrolledAt": state["enrolledAt"],
        "enrollmentOrdinal": state["enrollmentOrdinal"],
        "savedThroughOrdinal": state["throughOrdinal"],
        "capacity": MAX_RECORDS,
        "capacitySkipped": state["capacitySkipped"],
        "disabledSkipped": state["disabledSkipped"],
        **records_view(state, limit, skill),
    }


def observe(root, transcript, session, action="inspect", limit=20, skill=None):
    session = session_id(session)
    # Separate namespace: never touches Pi shelves or token state.
    root = root / "skill-activity"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Session ID can differ from the durable thread ID. Scan is inside a common
    # namespace lock so concurrent hook/controls cannot apply stale snapshots.
    with (root / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        projection = SkillRecords()
        snapshot = scan(transcript, session, observe_item=projection.observe)
        thread = snapshot["thread"]
        path = root / f"{thread}.json"
        state = load(path, thread)
        now = datetime.now(UTC).isoformat()
        if state is None:
            state = {
                "version": 1,
                "thread": thread,
                "project": projection.project,
                "enabled": True,
                "enrolledAt": now,
                "enrollmentOrdinal": snapshot["throughOrdinal"],
                "throughOrdinal": snapshot["throughOrdinal"],
                "records": {},
                "capacitySkipped": 0,
                "disabledSkipped": 0,
            }
        if projection.project != state["project"]:
            raise CoverageError("skill project identity changed; state retained")
        if snapshot["throughOrdinal"] < state["throughOrdinal"]:
            raise CoverageError("skill transcript sequence rewound; state retained")
        for key, event in projection.records.items():
            prior = state["records"].get(key)
            if prior:
                if any(prior[k] != event[k] for k in event if k != "ordinal"):
                    raise CoverageError("selected-skill identity changed; state retained")
                continue
            if event["ordinal"] <= state["throughOrdinal"]:
                continue
            record = {**event, "thread": thread, "session": session, "observedAt": now}
            if not state["enabled"]:
                state["disabledSkipped"] += 1
            elif len(state["records"]) == MAX_RECORDS:
                state["capacitySkipped"] += 1
            else:
                state["records"][key] = record
        state["throughOrdinal"] = snapshot["throughOrdinal"]
        if action in ("enable", "disable"):
            state["enabled"] = action == "enable"
        atomic_write(path, state)
        return {
            "runtime": "codex",
            "thread": thread,
            "session": session,
            "project": state["project"],
            "enabled": state["enabled"],
            "enrolledAt": state["enrolledAt"],
            "enrollmentOrdinal": state["enrollmentOrdinal"],
            "throughOrdinal": state["throughOrdinal"],
            "observedAt": now,
            "coverage": "bounded-native-insertions-only",
            "scope": SCOPE,
            "partialTailDeferred": snapshot["partialTail"],
            "capacity": MAX_RECORDS,
            "capacitySkipped": state["capacitySkipped"],
            "disabledSkipped": state["disabledSkipped"],
            **records_view(state, limit, skill),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["hook", "inspect", "list", "saved", "enable", "disable"])
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--transcript", type=Path)
    parser.add_argument("--session")
    parser.add_argument("--thread", help="explicit durable thread identity, saved query only")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--skill")
    args = parser.parse_args()
    event = None
    try:
        if not 1 <= args.limit <= 100:
            raise CoverageError("limit must be from 1 to 100")
        if args.action == "saved":
            if args.thread is None or args.transcript is not None or args.session is not None:
                raise CoverageError("saved requires --thread, without transcript or session")
            print(json.dumps(saved(args.state_root, args.thread, args.limit, args.skill)))
            return 0
        if args.thread is not None:
            raise CoverageError("--thread is only valid with saved")
        if args.action == "hook":
            raw = sys.stdin.buffer.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise CoverageError("hook payload too large")
            payload = json.loads(raw)
            event = payload.get("hook_event_name")
            if event not in EVENTS:
                raise CoverageError("unsupported skill hook event")
            if not isinstance(payload.get("transcript_path"), str):
                raise CoverageError("session-local transcript unavailable")
            transcript, session = Path(payload["transcript_path"]), payload.get("session_id")
        else:
            if args.transcript is None or args.session is None:
                raise CoverageError("controls require explicit --transcript and --session")
            transcript, session = args.transcript, args.session
        result = observe(args.state_root, transcript, session, args.action, args.limit, args.skill)
        if args.action != "hook":
            print(json.dumps(result))
        elif event == "PreCompact":
            print("{}")
        else:
            command = shlex.join(
                [
                    "python3",
                    str(Path(__file__).absolute()),
                    "list",
                    "--state-root",
                    str(args.state_root.absolute()),
                    "--transcript",
                    str(transcript),
                    "--session",
                    session_id(session),
                ]
            )
            text = (
                "[Automata Codex skill activity; current authorized session only]\n"
                f"Retained native insertion observations: {result['retainedCount']}; "
                f"enabled={result['enabled']}; capacitySkipped={result['capacitySkipped']}; "
                f"disabledSkipped={result['disabledSkipped']}. "
                + SCOPE
                + "\nQuery/control: "
                + command
                + "; optional --skill NAME --limit 1..100. Read-only historical query: "
                + shlex.join(
                    [
                        "python3",
                        str(Path(__file__).absolute()),
                        "saved",
                        "--state-root",
                        str(args.state_root.absolute()),
                        "--thread",
                        result["thread"],
                    ]
                )
                + ". Saved does not read the transcript or write state. Replace list with inspect, "
                "disable or enable. Enable starts from the current observation, not backfill. "
                "Do not infer no skill use from zero records."
            )
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": event,
                            "additionalContext": text,
                        }
                    }
                )
            )
        return 0
    except (CoverageError, OSError, ValueError, TypeError, KeyError, AttributeError):
        message = "Automata Codex skill coverage unavailable; prior records retained, not current."
        if args.action == "hook":
            output = {"systemMessage": message}
            if event in ("SessionStart", "UserPromptSubmit", "PostCompact"):
                output = {
                    "hookSpecificOutput": {"hookEventName": event, "additionalContext": message}
                }
            print(json.dumps(output))
            return 0
        print(json.dumps({"coverage": "unknown", "error": message}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
