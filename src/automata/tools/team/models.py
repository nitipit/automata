"""Strict canonical documents; relationships live in store.py, display in view.py."""

import json
import math
from datetime import datetime

from dictify import Field, Model


def offset_time(value):
    if value is None:
        return True
    try:
        return isinstance(value, str) and datetime.fromisoformat(value).utcoffset() is not None
    except ValueError:
        return False


def number(value):
    return value is None or (type(value) in (int, float) and math.isfinite(value) and value >= 0)


def integer(value):
    return value is None or (type(value) is int and value >= 0)


def string():
    return Field(required=True).verify(
        lambda x: type(x) is str and bool(x), "nonempty string required"
    )


def ids():
    return Field(required=True).verify(
        lambda x: (
            type(x) is list and all(type(i) is str and i for i in x) and len(x) == len(set(x))
        ),
        "unique string IDs required",
    )


class Context(Model):
    used_tokens = Field(required=True).verify(integer)
    capacity_tokens = Field(required=True).verify(lambda x: x is None or (type(x) is int and x > 0))
    observed_at = Field(required=True).verify(offset_time)
    source = Field(required=True).verify(lambda x: x in ("sample", "measured", "unavailable"))

    def post_validate(self):
        used, capacity = self["used_tokens"], self["capacity_tokens"]
        if used is not None and capacity is not None and used > capacity:
            raise ValueError("context exceeds capacity")
        if self["source"] == "unavailable" and (used is not None or capacity is not None):
            raise ValueError("unavailable context must have null counts")
        if used is not None and self["observed_at"] is None:
            raise ValueError("known context requires observation time")


class Tokens(Model):
    input = Field(required=True).verify(integer)
    output = Field(required=True).verify(integer)
    cache_read = Field(required=True).verify(integer)
    cache_write = Field(required=True).verify(integer)
    observed_at = Field(required=True).verify(offset_time)
    source = Field(required=True).verify(lambda x: x in ("sample", "measured", "unavailable"))

    def post_validate(self):
        known = any(self[k] is not None for k in ("input", "output", "cache_read", "cache_write"))
        if known and (self["source"] == "unavailable" or self["observed_at"] is None):
            raise ValueError("known token counts require source and observation time")


class Estimate(Model):
    min_seconds = Field(required=True).verify(number)
    max_seconds = Field(required=True).verify(number)
    target_finish = Field(required=True).verify(offset_time)

    def post_validate(self):
        low, high = self["min_seconds"], self["max_seconds"]
        if low is not None and high is not None and low > high:
            raise ValueError("estimate bounds reversed")


class Record(Model):
    id = string()
    goal_id = string()


class Goal(Record):
    name = string()
    manager_id = string()

    def post_validate(self):
        if self["id"] != self["goal_id"]:
            raise ValueError("goal must refer to itself")


class Team(Record):
    name = string()
    manager_id = string()
    parent_id = Field(required=True).verify(lambda x: x is None or (type(x) is str and bool(x)))
    agent_ids = ids()
    task_ids = ids()


class Report(Model):
    """One explicitly published current work report, never inferred from tasks."""

    summary = string()
    status = Field(required=True).verify(lambda x: x in ("pending", "working", "done", "blocked"))
    blocker = Field(required=True).verify(lambda x: type(x) is str)
    status_changed_at = Field(required=True).verify(offset_time)
    elapsed_seconds = Field(required=True).verify(number)
    estimate = Field(required=True).verify(lambda x: type(x) is dict)
    tokens = Field(required=True).verify(lambda x: type(x) is dict)

    def post_validate(self):
        Estimate(self["estimate"])
        Tokens(self["tokens"])
        if self["status"] == "blocked" and not self["blocker"].strip():
            raise ValueError("blocked report requires a meaningful blocker")


class Agent(Record):
    name = string()
    model = string()
    thinking = string()
    context = Field(required=True).verify(lambda x: type(x) is dict)
    updated_at = Field(required=True).verify(offset_time)
    report = Field().verify(lambda x: x is None or type(x) is dict)

    def post_validate(self):
        Context(self["context"])
        if self.get("report") is not None:
            Report(self["report"])


class Task(Record):
    name = string()
    owner_id = string()
    team_id = string()
    status = Field(required=True).verify(lambda x: x in ("pending", "working", "done", "blocked"))
    status_changed_at = Field(required=True).verify(offset_time)
    updated_at = Field(required=True).verify(offset_time)
    elapsed_seconds = Field(required=True).verify(number)
    estimate = Field(required=True).verify(lambda x: type(x) is dict)
    tokens = Field(required=True).verify(lambda x: type(x) is dict)
    note = Field(required=True).verify(lambda x: type(x) is str)

    def post_validate(self):
        Estimate(self["estimate"])
        Tokens(self["tokens"])


MODELS = {"goals": Goal, "teams": Team, "agents": Agent, "tasks": Task}


def canonical(kind, data):
    plain = MODELS[kind](data).dict()  # explicit native conversion, never persist Model
    return json.loads(json.dumps(plain, allow_nan=False))
