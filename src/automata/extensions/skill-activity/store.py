# /// script
# requires-python = ">=3.12"
# dependencies = ["shelfdb==3.0.2", "dictify==5.0.2"]
# ///
"""Local-only skill-read records. No server, conversation text, or executable queries."""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from dictify import Field, Model
from shelfdb.shelf import DB


class SkillRead(Model):
    """Strict CLI input: metadata only; unknown fields are rejected."""

    timestamp = Field(required=True).instance(str).verify(
        lambda v: datetime.fromisoformat(v).tzinfo is not None
    )
    sessionId = Field(required=True).instance(str).verify(lambda v: bool(v.strip()))
    toolCallId = Field(required=True).instance(str).verify(lambda v: bool(v.strip()))
    project = Field(required=True).instance(str).verify(lambda v: Path(v).is_absolute())
    skill = Field(required=True).instance(str).match(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
    path = Field(required=True).instance(str).verify(lambda v: Path(v).is_absolute())


class SkillActivation(SkillRead):
    """Stored record; provenance and status are assigned by the CLI."""

    source = Field(default="read").instance(str).verify(lambda v: v == "read")
    status = Field(default="loaded").instance(str).verify(lambda v: v == "loaded")


def record(path: Path, event: dict) -> bool:
    if not isinstance(event, dict):
        raise ValueError("Expected a skill-read metadata object")
    value = dict(SkillActivation(SkillRead(event)))
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = json.dumps([value["sessionId"], value["toolCallId"]])
    with DB(str(path)) as db, db.transaction(write=True) as tx:
        shelf = tx.shelf("skill_activations")
        if shelf.key(key).exists():
            return False
        shelf.put(key, value)
    return True


def records(path: Path, limit: int, project: str | None = None) -> list[dict]:
    """Return key-ordered records, filtering by exact project before limiting."""
    if not (path / "data.mdb").exists():
        return []
    result = []
    with DB(str(path)) as db, db.transaction(write=False) as tx:
        for item in tx.shelf("skill_activations").items():
            value = dict(SkillActivation(item.value))
            if project is not None and value["project"] != project:
                continue
            result.append(value)
            if len(result) >= limit:
                break
    return result


def main() -> None:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["record", "list"])
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--event", help="JSON metadata for record")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--project", help="Exact absolute project path to filter list results")
    args = parser.parse_args()
    if args.project is not None and (
        args.action != "list" or not Path(args.project).is_absolute()
    ):
        parser.error("--project requires list and an absolute project path")
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    try:
        if args.action == "record":
            if args.event is None:
                parser.error("record requires --event")
            result = {"inserted": record(args.db, json.loads(args.event))}
        else:
            result = records(args.db, args.limit, args.project)
    except (Model.Error, ValueError):
        parser.error("Invalid skill-activation metadata")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
