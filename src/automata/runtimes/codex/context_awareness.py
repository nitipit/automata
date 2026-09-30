"""Sequence-linked context/timestamp snapshots on the existing hook boundary."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from context_records import RECENT_LIMIT, identity, timestamp

COVERAGE = (
    "Last native context observation, not live request size or billing usage. "
    "Pressure is raw last.total_tokens/window, not Codex UI baseline-adjusted remaining percent. "
    "Incoming input and later hook text may not be included. Native item lifecycle timestamps "
    "are not human composition or delivery times. Elapsed is wall time from the labelled anchor, "
    "not active work. Input observations retain eight turns; after eviction a re-observation "
    "gets a new ID. Recent restored facts are not an active-branch history projection."
)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def elapsed(anchor, now):
    if anchor is None or anchor.get("at") is None:
        return None
    difference = (
        datetime.fromisoformat(now) - datetime.fromisoformat(anchor["at"])
    ).total_seconds()
    return round(difference, 3) if difference >= 0 else None


def pressure(percent):
    if percent is None:
        return "unknown"
    if percent >= 95:
        return "critical"
    if percent >= 90:
        return "high"
    if percent >= 75:
        return "elevated"
    if percent >= 50:
        return "moderate"
    return "low"


def load(value):
    if value is None:
        return {"version": 1, "anchors": [], "packet": None, "sourceKey": None}
    try:
        if not isinstance(value, dict) or set(value) != {
            "version",
            "anchors",
            "packet",
            "sourceKey",
        }:
            raise ValueError
        if (
            value["version"] != 1
            or not isinstance(value["anchors"], list)
            or len(value["anchors"]) > 8
        ):
            raise ValueError
        for anchor in value["anchors"]:
            if (
                not isinstance(anchor, dict)
                or set(anchor) != {"id", "turn", "at", "kind"}
                or identity(anchor["id"]) is None
                or identity(anchor["turn"]) is None
                or timestamp(anchor["at"]) != anchor["at"]
                or anchor["kind"] != "first-hook-observation-of-turn-input"
            ):
                raise ValueError
        packet = value["packet"]
        key = value["sourceKey"]
        if (packet is None and key is not None) or (
            packet is not None
            and (not isinstance(key, str) or len(key) != 64 or identity(key) is None)
        ):
            raise ValueError
        if packet is not None:
            if not isinstance(packet, dict) or packet.get("coverage") != COVERAGE:
                raise ValueError
            contents = {key: item for key, item in packet.items() if key != "packetId"}
            if packet.get("packetId") != digest(contents):
                raise ValueError
            facts = {
                name: item
                for name, item in contents.items()
                if name not in {"observedAt", "elapsedWallSecondsAtObservation"}
            }
            if key != digest(facts):
                raise ValueError
            if timestamp(packet["observedAt"]) != packet["observedAt"]:
                raise ValueError
            if (
                not isinstance(packet["recentMessages"], list)
                or len(packet["recentMessages"]) > RECENT_LIMIT
            ):
                raise ValueError
        return value
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise ValueError("invalid saved awareness state") from error


def update(state, snapshot, records, event, turn, now, *, inspecting=False):
    saved = load(state.get("awareness"))
    prior = saved["packet"]
    if event == "UserPromptSubmit":
        turn = identity(turn)
        if turn is None:
            raise ValueError("input observation turn unavailable")
        anchor = next((entry for entry in saved["anchors"] if entry["turn"] == turn), None)
        if anchor is None:
            # A re-observation after bounded anchor eviction is a NEW observation,
            # not the same timestamp identity silently assigned a different clock.
            observation_id = digest([snapshot["thread"], turn, "input-observation", now])[:24]
            anchor = {
                "id": observation_id,
                "turn": turn,
                "at": now,
                "kind": "first-hook-observation-of-turn-input",
            }
            saved["anchors"] = (saved["anchors"] + [anchor])[-8:]
    else:
        anchor = saved["anchors"][-1] if saved["anchors"] else None
    observations = snapshot["observations"]
    if anchor is None and observations["latestUser"] is not None:
        user = observations["latestUser"]
        anchor = {
            "id": user["item"],
            "turn": user["turn"],
            "at": user["startedAt"] or user["completedAt"] or user["recordedAt"],
            "kind": (
                "native-user-item-lifecycle"
                if user["startedAt"] or user["completedAt"]
                else "native-user-item-record-time"
            ),
        }
    if anchor is None and prior is not None:
        anchor = prior["inputAnchor"]  # Restored last-known anchor, not a new input clock.
    recent = list(prior["recentMessages"]) if prior else []
    current_keys = set()
    for entry in observations["recentMessages"]:
        key = (entry["turn"], entry["item"])
        current_keys.add(key)
        previous = next((item for item in recent if (item["turn"], item["item"]) == key), None)
        if previous is not None:
            if any(previous[name] != entry[name] for name in ("role", "startedAt", "completedAt")):
                raise ValueError("conflicting native timestamp identity")
            entry = previous  # Preserve original observed log location/time across replay.
        recent = [item for item in recent if (item["turn"], item["item"]) != key] + [entry]
    recent = recent[-RECENT_LIMIT:]
    restored = sum((item["turn"], item["item"]) not in current_keys for item in recent)
    context = observations["nativeContext"]
    context_availability = "current-transcript-observation"
    if context is None and prior and prior["context"] is not None:
        context = prior["context"]
        context_availability = "restored-last-known-observation"
    elif context is None:
        context_availability = "unknown"
    matching = [
        record for record in records.values() if anchor and record["turn"] == anchor["turn"]
    ]
    usage = {
        name: sum(record["usage"][name] for record in matching)
        for name in ("input", "output", "cacheRead", "cacheWrite")
    }
    ordinal_candidates = [item["recordOrdinal"] for item in recent]
    if context:
        ordinal_candidates.append(context["recordOrdinal"])
    task = observations["latestTask"]
    if task:
        ordinal_candidates.append(task["recordOrdinal"])
    facts = {
        "thread": snapshot["thread"],
        "session": snapshot["session"],
        "throughRelevantRecordOrdinal": max(ordinal_candidates, default=None),
        "inputAnchor": anchor,
        "nativeTask": task,
        "context": context,
        "contextAvailability": context_availability,
        "pressureBand": pressure(context["percent"] if context else None),
        "recentMessages": recent,
        "restoredRecentMessages": restored,
        "anchorUsage": {
            "normalized": usage,
            "counted": usage["input"] + usage["output"] + usage["cacheWrite"],
            "measuredResponses": len(matching),
            "throughResponse": matching[-1]["response"] if matching else None,
            "scope": "Observed completed compaction-free responses in anchor turn only; "
            "unfinished/mixed turns and unreported telemetry excluded",
        },
        "partialTailDeferred": snapshot["partialTail"],
        "malformedMetadata": observations["malformedMetadata"],
        "coverage": COVERAGE,
    }
    key = digest(facts)
    if saved["sourceKey"] != key or prior is None:
        packet = {
            **facts,
            "observedAt": now,
            "elapsedWallSecondsAtObservation": elapsed(anchor, now),
        }
        packet["packetId"] = digest(packet)
        saved["packet"] = packet
        saved["sourceKey"] = key
    state["awareness"] = saved
    packet = saved["packet"]
    if inspecting:
        return {**packet, "inspectedAt": now, "elapsedWallSecondsAtInspect": elapsed(anchor, now)}
    return packet
