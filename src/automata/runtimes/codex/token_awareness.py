#!/usr/bin/env python3
"""Session-local Codex awareness hook with inspect/set/context controls. Stdlib only.

The installer supplies --state-root. Hooks supply transcript_path/session_id; CLI
controls require both explicitly. No session discovery or daemon access occurs.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shlex
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from context_awareness import update as update_awareness
from token_records import (
    CATEGORIES,
    MAX_INTEGER,
    CoverageError,
    counted,
    identifier,
    scan,
    session_id,
)

DEFAULT_THRESHOLD = 100_000
MAX_THRESHOLD = 1_000_000_000
SCOPE = (
    "Measured response records in this supplied local transcript, from completed "
    "turns without compaction. Entire compaction-containing turns (including main "
    "work), unfinished turns, unreported usage and unavailable inherited history "
    "are excluded. Retained ledger is lifetime observations for this thread, NOT "
    "active-branch totals after rollback/rewrite. Not an exact whole-thread total. "
    "Historical purpose without surviving hook/native compaction markers is uncertified. "
    "Provider-defaulted zero fields may mean missing telemetry. "
    "Observation time is not measured-through time."
)
EVENTS = {"UserPromptSubmit", "SessionStart", "PreCompact", "PostCompact"}


def atomic_write(path: Path, value: dict):
    descriptor, temporary = tempfile.mkstemp(prefix=".tokens-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_state(path: Path, identity: str) -> dict:
    if not path.exists():
        return {
            "version": 1,
            "thread": identity,
            "threshold": DEFAULT_THRESHOLD,
            "records": {},
            "compactionTurns": [],
            "checkpointCounted": 0,
            "latest": None,
        }
    try:
        value = json.loads(path.read_text())
        if (
            value["version"] != 1
            or value["thread"] != identity
            or not isinstance(value["records"], dict)
            or type(value["threshold"]) is not int
            or not 1 <= value["threshold"] <= MAX_THRESHOLD
        ):
            raise ValueError
        for key, record in value["records"].items():
            if not isinstance(record, dict) or key != (
                f"{session_id(record['thread'])}:{identifier(record['response'])}"
            ):
                raise ValueError
            identifier(record["turn"])
            if type(record["ordinal"]) is not int or record["ordinal"] < 0:
                raise ValueError
            usage = record["usage"]
            if not isinstance(usage, dict) or set(usage) != set(CATEGORIES):
                raise ValueError
            if any(
                type(number) is not int or not 0 <= number <= MAX_INTEGER
                for number in usage.values()
            ):
                raise ValueError
        if not isinstance(value["compactionTurns"], list):
            raise ValueError
        for turn in value["compactionTurns"]:
            identifier(turn)
        baseline = value["checkpointCounted"]
        total = sum(counted(record["usage"]) for record in value["records"].values())
        if type(baseline) is not int or not 0 <= baseline <= total <= MAX_INTEGER:
            raise ValueError
        latest = value["latest"]
        if latest is None:
            if baseline != 0:
                raise ValueError
        elif (
            not isinstance(latest, dict)
            or latest["thread"] != identity
            or latest["counted"] != baseline
            or not isinstance(latest["cumulative"], dict)
            or set(latest["cumulative"]) != set(CATEGORIES)
            or counted(latest["cumulative"]) != baseline
        ):
            raise ValueError
        if latest is not None:
            identifier(latest["checkpointId"])
            numeric = {
                "threshold",
                "counted",
                "measuredResponses",
                "zeroResponses",
                "throughRecordOrdinal",
                "excludedCompactionRecords",
                "unclassifiedRecords",
                "retainedRecordsNotInCurrentSnapshot",
                "deltaCounted",
            }
            fields = numeric | {
                "checkpointId",
                "thread",
                "session",
                "cumulative",
                "throughResponse",
                "throughResponseThread",
                "observedAt",
                "scope",
                "baseline",
                "partialTailDeferred",
            }
            if set(latest) != fields or any(
                type(latest[key]) is not int or latest[key] < 0 for key in numeric
            ):
                raise ValueError
            if not 1 <= latest["threshold"] <= MAX_THRESHOLD or latest["scope"] != SCOPE:
                raise ValueError
            if latest["baseline"] != "local-observed-records-only; inherited completeness unknown":
                raise ValueError
            if type(latest["partialTailDeferred"]) is not bool:
                raise ValueError
            session_id(latest["session"])
            datetime.fromisoformat(latest["observedAt"])
            prefix = list(value["records"].values())[: latest["measuredResponses"]]
            if not prefix or len(prefix) != latest["measuredResponses"]:
                raise ValueError
            if latest["cumulative"] != {
                name: sum(r["usage"][name] for r in prefix) for name in CATEGORIES
            }:
                raise ValueError
            if (
                latest["throughResponse"] != prefix[-1]["response"]
                or latest["throughResponseThread"] != prefix[-1]["thread"]
                or latest["throughRecordOrdinal"] != prefix[-1]["ordinal"]
                or not latest["threshold"] <= latest["deltaCounted"] <= baseline
            ):
                raise ValueError
        return value
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise CoverageError("invalid saved token state; not reset") from error


def observe(
    state_root: Path,
    transcript: Path,
    identity: str,
    action: str,
    threshold: int | None = None,
    compaction_turn: str | None = None,
    event: str | None = None,
    turn: str | None = None,
) -> dict:
    session = session_id(identity)
    snapshot = scan(transcript, session)
    identity = snapshot["thread"]
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_path = state_root / f"{identity}.json"
    lock_path = state_root / f"{identity}.lock"
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_state(state_path, identity)
        if compaction_turn is not None:
            turn = identifier(compaction_turn)
            if turn not in state.setdefault("compactionTurns", []):
                state["compactionTurns"].append(turn)
            # Persist provenance before Codex proceeds to the compaction request.
            atomic_write(state_path, state)
        excluded = set(state.get("compactionTurns", []))
        snapshot["excludedCompactionRecords"] += sum(
            record["turn"] in excluded for record in snapshot["records"].values()
        )
        snapshot["records"] = {
            key: record
            for key, record in snapshot["records"].items()
            if record["turn"] not in excluded
        }
        for key, record in snapshot["records"].items():
            old = state["records"].get(key)
            if old and any(old[name] != record[name] for name in ("turn", "usage")):
                raise CoverageError("response identity changed; state retained")
            state["records"].setdefault(key, record)
        totals = {
            name: sum(record["usage"][name] for record in state["records"].values())
            for name in CATEGORIES
        }
        if sum(totals.values()) > MAX_INTEGER or any(
            type(value) is not int or not 0 <= value <= MAX_INTEGER for value in totals.values()
        ):
            raise CoverageError("invalid cumulative usage")
        if action == "set":
            if type(threshold) is not int or not 1 <= threshold <= MAX_THRESHOLD:
                raise CoverageError("threshold must be an integer from 1 to 1000000000")
            state["threshold"] = threshold
        now = datetime.now(UTC).isoformat()
        last = next(reversed(state["records"].values()), None)
        result = {
            "thread": identity,
            "session": session,
            "retainedRecordsNotInCurrentSnapshot": len(
                set(state["records"]) - set(snapshot["records"])
            ),
            "threshold": state["threshold"],
            "cumulative": totals,
            "counted": counted(totals),
            "measuredResponses": len(state["records"]),
            "zeroResponses": sum(
                not any(record["usage"].values()) for record in state["records"].values()
            ),
            "throughResponse": last["response"] if last else None,
            "throughResponseThread": last["thread"] if last else None,
            "throughRecordOrdinal": last["ordinal"] if last else None,
            "observedAt": now,
            "scope": SCOPE,
            "partialTailDeferred": snapshot["partialTail"],
            "excludedCompactionRecords": snapshot["excludedCompactionRecords"],
            "unclassifiedRecords": snapshot["unclassifiedRecords"],
            "baseline": "local-observed-records-only; inherited completeness unknown",
        }
        # Setting a threshold retains accrued usage; checkpoint only at a hook.
        pending = result["counted"] - state["checkpointCounted"] >= state["threshold"]
        if action == "hook" and pending:
            digest = hashlib.sha256(
                json.dumps([identity, list(state["records"]), totals], sort_keys=True).encode()
            ).hexdigest()[:24]
            state["latest"] = {
                **result,
                "checkpointId": digest,
                "deltaCounted": result["counted"] - state["checkpointCounted"],
            }
            state["checkpointCounted"] = result["counted"]
        result["pending"] = pending
        result["latestCheckpoint"] = state["latest"]
        result["contextStatus"] = update_awareness(
            state, snapshot, state["records"], event, turn, now, inspecting=action != "hook"
        )
        atomic_write(state_path, state)
        return result


def hook_output(status: dict, event: str) -> dict:
    checkpoint = status.get("latestCheckpoint")
    if not checkpoint:
        return {}
    # Replay the SAME latest checkpoint, not a new landmark, after resume/compact
    # and on later prompts. Durable-before-output makes retry/crash replay safe.
    text = "[Codex token checkpoint; replay of latest snapshot, not current usage]\n"
    text += json.dumps(checkpoint, sort_keys=True)
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["hook", "inspect", "set", "context"])
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--transcript", type=Path)
    parser.add_argument("--session")
    parser.add_argument("--threshold", type=int)
    args = parser.parse_args()
    try:
        event = None
        if args.action == "hook":
            raw = sys.stdin.buffer.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise CoverageError("hook payload too large")
            payload = json.loads(raw)
            event = payload.get("hook_event_name")
            if not isinstance(event, str) or event not in EVENTS:
                raise CoverageError("unsupported token hook event")
            if not isinstance(payload.get("transcript_path"), str):
                raise CoverageError("session-local transcript unavailable")
            transcript = Path(payload["transcript_path"])
            identity = payload.get("session_id")
        else:
            if args.transcript is None or args.session is None:
                raise CoverageError("controls require explicit --transcript and --session")
            transcript, identity = args.transcript, args.session
        if args.action != "set" and args.threshold is not None:
            raise CoverageError("threshold is only valid with set")
        compaction_turn = payload.get("turn_id") if event in {"PreCompact", "PostCompact"} else None
        if event in {"PreCompact", "PostCompact"} and compaction_turn is None:
            raise CoverageError("compaction turn identity unavailable")
        result = observe(
            args.state_root,
            transcript,
            identity,
            "inspect" if event == "PreCompact" else args.action,
            args.threshold,
            compaction_turn,
            event=event,
            turn=payload.get("turn_id") if event else None,
        )
        if event == "PreCompact":
            print("{}")  # Provenance only; no pre-compaction prompt insertion.
        elif event:
            output = hook_output(result, event)
            control = shlex.join(
                [
                    "python3",
                    str(Path(__file__).absolute()),
                    "inspect",
                    "--state-root",
                    str(args.state_root.absolute()),
                    "--transcript",
                    str(transcript),
                    "--session",
                    session_id(identity),
                ]
            )
            instructions = (
                "[Automata token/context controls, current authorized session only] "
                + control
                + "; use set instead of inspect with --threshold N, "
                "or context for context/timestamps. "
                "No session discovery is authorized."
            )
            if not output:
                output = {
                    "hookSpecificOutput": {
                        "hookEventName": event,
                        "additionalContext": instructions,
                    }
                }
            else:
                output["hookSpecificOutput"]["additionalContext"] += "\n" + instructions
            awareness = (
                "[Codex context/timestamp snapshot; sequence-linked, may be replayed]\n"
                + json.dumps(result["contextStatus"], sort_keys=True)
            )
            output["hookSpecificOutput"]["additionalContext"] += "\n" + awareness
            print(json.dumps(output))
        else:
            print(json.dumps(result["contextStatus"] if args.action == "context" else result))
        return 0
    except (CoverageError, OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        # Never echo parser exceptions, paths, raw JSON or conversation content.
        reason = (
            str(error) if isinstance(error, CoverageError) else "runtime observation unavailable"
        )
        if args.action == "hook":
            message = (
                f"Automata token/context coverage unavailable: {reason}; "
                "prior snapshots are not current."
            )
            if isinstance(event, str) and event in {
                "SessionStart",
                "UserPromptSubmit",
                "PostCompact",
            }:
                print(
                    json.dumps(
                        {
                            "hookSpecificOutput": {
                                "hookEventName": event,
                                "additionalContext": message,
                            }
                        }
                    )
                )
            else:
                print(json.dumps({"systemMessage": message}))
            return 0
        print(json.dumps({"error": reason, "coverage": "unknown"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
