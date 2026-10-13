"""Atomic goal-scoped publishing over trusted-local ShelfDB.

Actors are declarations, not authentication. Direct ShelfDB clients can bypass
these rules; its pickle/dill protocol must never be exposed to untrusted peers.
"""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from shelfdb.client import Client

from .models import MODELS, canonical

DEFAULT_STATE_ROOT = Path(".agents/var/apps/agent-team")


def service_url(state_root=DEFAULT_STATE_ROOT):
    return "unix://" + str(Path(state_root).resolve() / "db.sock")


def storage_key(goal, key):
    """Unambiguous namespacing, even when IDs contain separators."""
    return json.dumps([goal, key], ensure_ascii=True, separators=(",", ":"))


def now():
    return datetime.now(UTC).isoformat()


def merge(old, patch):
    result = copy.deepcopy(old)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


async def read_tx(tx, goal, kinds=MODELS):
    state = {kind: {} for kind in kinds}
    for kind in kinds:
        for item in await tx.shelf(kind).items().query():
            record = item.value
            if record["goal_id"] == goal:
                if item.key != storage_key(goal, record["id"]):
                    raise ValueError("ID/key mismatch")
                state[kind][record["id"]] = record
    return state


async def snapshot(goal, url=None, *, reports_only=False):
    client = await Client.connect(url or service_url())
    try:
        async with client.transaction() as tx:
            kinds = ("goals", "teams", "agents") if reports_only else MODELS
            state = await read_tx(tx, goal, kinds)
            if goal not in state["goals"]:
                raise ValueError("unknown goal")
            return state
    finally:
        await client.close()


def validate_state(state, goal):
    if set(state) != set(MODELS) or set(state["goals"]) != {goal}:
        raise ValueError("exactly one scoped goal required")
    for kind, records in state.items():
        for key, record in records.items():
            canonical(kind, record)
            if key != record["id"] or record["goal_id"] != goal:
                raise ValueError("ID/key mismatch or cross-goal record")

    def reference(kind, key):
        if key not in state[kind]:
            raise ValueError(f"dangling/cross-goal {kind}: {key}")
        return state[kind][key]

    goal_record = state["goals"][goal]
    reference("agents", goal_record["manager_id"])
    roots = [team for team in state["teams"].values() if team["parent_id"] is None]
    if len(roots) != 1 or roots[0]["manager_id"] != goal_record["manager_id"]:
        raise ValueError("exactly one root managed by goal manager required")
    for team in state["teams"].values():
        reference("agents", team["manager_id"])
        if team["manager_id"] not in team["agent_ids"]:
            raise ValueError("team manager must be a member")
        for aid in team["agent_ids"]:
            reference("agents", aid)
        for tid in team["task_ids"]:
            reference("tasks", tid)
        seen, current = set(), team
        while current:
            if current["id"] in seen:
                raise ValueError("team cycle")
            seen.add(current["id"])
            current = (
                reference("teams", current["parent_id"])
                if current["parent_id"] is not None
                else None
            )
    for task in state["tasks"].values():
        reference("agents", task["owner_id"])
        team = reference("teams", task["team_id"])
        if task["owner_id"] not in team["agent_ids"] or task["id"] not in team["task_ids"]:
            raise ValueError("task must link to its declared team and member")


def authorize(state, kind, key, candidate, actor):
    """Root owns graph; nested managers cannot promote themselves or outsiders."""
    old = state[kind].get(key)
    root_actor = next(iter(state["goals"].values()))["manager_id"]
    if kind == "goals":
        if actor != root_actor or candidate["manager_id"] != root_actor:
            raise ValueError("goal manager required; manager identity immutable")
    elif kind == "agents":
        if actor != key:
            raise ValueError("agent record owner required")
    elif kind == "tasks":
        if actor != candidate["owner_id"] or (old and actor != old["owner_id"]):
            raise ValueError("task owner required")
        if old and (candidate["owner_id"], candidate["team_id"]) != (
            old["owner_id"],
            old["team_id"],
        ):
            raise ValueError("task placement immutable")
        team = state["teams"].get(candidate["team_id"])
        if team is None or actor not in team["agent_ids"]:
            raise ValueError("task owner must belong to team")
    elif actor != root_actor:
        if old:
            if actor != old["manager_id"]:
                raise ValueError("team manager required")
            if (candidate["manager_id"], candidate["parent_id"]) != (
                old["manager_id"],
                old["parent_id"],
            ):
                raise ValueError("nested manager cannot change manager or parent")
        else:
            parent = state["teams"].get(candidate["parent_id"])
            if parent is None or parent["manager_id"] != actor:
                raise ValueError("new team requires parent manager")
        parent = state["teams"].get(candidate["parent_id"])
        if parent is None or not set(candidate["agent_ids"]) <= set(parent["agent_ids"]):
            raise ValueError("nested manager cannot introduce foreign membership")
        if old:
            additions = set(candidate["task_ids"]) - set(old["task_ids"])
            if any(state["tasks"].get(tid, {}).get("team_id") != key for tid in additions):
                raise ValueError("nested manager cannot add foreign task links")
        elif candidate["task_ids"]:
            raise ValueError("new nested team must start without task links")


async def initialize(documents, actor, goal, url=None):
    """Add one complete goal graph without resetting any existing goal."""
    if type(documents) is not dict or set(documents) != set(MODELS):
        raise ValueError("four logical shelves required")
    state = {kind: {} for kind in MODELS}
    for kind, rows in documents.items():
        if type(rows) is not list:
            raise ValueError("initial shelves must contain arrays")
        for row in rows:
            record = canonical(kind, row)
            if record["id"] in state[kind]:
                raise ValueError("duplicate ID")
            state[kind][record["id"]] = record
    validate_state(state, goal)
    if state["goals"][goal]["manager_id"] != actor:
        raise ValueError("actor is not goal manager")
    client = await Client.connect(url or service_url())
    try:
        async with client.transaction(write=True) as tx:
            if any((await read_tx(tx, goal)).values()):
                raise ValueError("goal already exists")
            for kind, records in state.items():
                for key, record in records.items():
                    await tx.shelf(kind).put(storage_key(goal, key), record).query()
    finally:
        await client.close()


async def publish(kind, key, data, actor, goal, *, replace=False, url=None):
    if kind not in MODELS or type(data) is not dict:
        raise ValueError("invalid kind or document")
    if not replace and {"id", "goal_id", "status_changed_at", "updated_at"} & data.keys():
        raise ValueError("immutable/server-owned fields")
    if (
        not replace
        and kind == "agents"
        and isinstance(data.get("report"), dict)
        and "status_changed_at" in data["report"]
    ):
        raise ValueError("report status_changed_at is server-owned")
    client = await Client.connect(url or service_url())
    try:
        async with client.transaction(write=True) as tx:
            # Profiles/reports cannot change graph IDs or placement. They need no
            # task enumeration; structural/task publishers still validate the graph.
            kinds = ("goals", "agents") if kind == "agents" else MODELS
            state = await read_tx(tx, goal, kinds)
            if goal not in state["goals"]:
                raise ValueError("unknown goal")
            old = state[kind].get(key)
            if not replace and old is None:
                raise ValueError("unknown record")
            candidate = copy.deepcopy(data) if replace else merge(old, data)
            if candidate.get("id") != key or candidate.get("goal_id") != goal:
                raise ValueError("ID/goal mismatch")
            stamp = now()
            if kind in ("tasks", "agents"):
                candidate["updated_at"] = stamp
            if kind == "tasks":
                candidate["status_changed_at"] = (
                    old["status_changed_at"]
                    if old and candidate.get("status") == old["status"]
                    else stamp
                )
            if kind == "agents" and isinstance(candidate.get("report"), dict):
                old_report = old.get("report") if old else None
                report = candidate["report"]
                report["status_changed_at"] = (
                    old_report["status_changed_at"]
                    if old_report and report.get("status") == old_report["status"]
                    else stamp
                )
            candidate = canonical(kind, candidate)
            authorize(state, kind, key, candidate, actor)
            state[kind][key] = candidate
            changes = [(kind, key, candidate)]
            if kind == "tasks" and old is None:
                team = copy.deepcopy(state["teams"][candidate["team_id"]])
                if key not in team["task_ids"]:
                    team["task_ids"].append(key)
                state["teams"][team["id"]] = team
                changes.append(("teams", team["id"], team))
            if kind != "agents":
                validate_state(state, goal)
            for shelf, record_id, record in changes:
                await tx.shelf(shelf).put(storage_key(goal, record_id), record).query()
            return candidate
    finally:
        await client.close()
