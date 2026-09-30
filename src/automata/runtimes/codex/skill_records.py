"""Codex 0.159.0 native selected-skill insertion evidence, never shell intent.

Only metadata-tagged response items qualify. User text shaped like <skill>, skill
catalogs and internal implicit-invocation analytics do not establish this evidence.
No skill files are read; names/paths come from the successful native insertion.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import PurePosixPath

from token_records import CoverageError, identifier

KIND = "skills.selected_skill_instructions"
NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,199}\Z")
HEADER = re.compile(r"\A<skill>\n<name>([^\n<>]+)</name>\n<path>([^\n<>]+)</path>\n")


def absolute_metadata_path(value):
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 4096
        and PurePosixPath(value).is_absolute()
        and not any(ord(char) < 32 for char in value)
    )


def event_id(message, index):
    return hashlib.sha256(json.dumps([message, index]).encode()).hexdigest()


class SkillRecords:
    """Bounded projection consumed only after the transcript scan validates."""

    def __init__(self):
        self.project = None
        self.records = {}

    def observe(self, item):
        payload = item["payload"]
        if item.get("type") == "session_meta":
            cwd = payload.get("cwd")
            if not absolute_metadata_path(cwd):
                raise CoverageError("skill project metadata unavailable")
            self.project = cwd
        if item.get("type") != "response_item" or payload.get("type") != "message":
            return
        metadata = payload.get("internal_chat_message_metadata_passthrough") or {}
        kinds = metadata.get("content_item_kinds") or []
        if KIND not in kinds:
            return
        content = payload.get("content")
        if (
            payload.get("role") != "user"
            or not isinstance(content, list)
            or len(content) != len(kinds)
        ):
            raise CoverageError("unknown selected-skill schema")
        turn = identifier(metadata.get("turn_id"))
        message = identifier(payload.get("id"))
        timestamp = item.get("timestamp")
        try:
            parsed_time = datetime.fromisoformat(timestamp)
            if parsed_time.utcoffset() is None:
                raise ValueError
        except (ValueError, TypeError):
            raise CoverageError("selected-skill timestamp unavailable") from None
        for index, (part, kind) in enumerate(zip(content, kinds, strict=True)):
            if kind != KIND:
                continue
            text = part.get("text") if part.get("type") == "input_text" else None
            match = HEADER.match(text) if isinstance(text, str) else None
            if not match or not text.endswith("</skill>"):
                raise CoverageError("unknown selected-skill wrapper")
            name, path = match.groups()
            if not NAME.fullmatch(name) or len(path) > 4096:
                raise CoverageError("unsupported selected-skill identity")
            # URI-backed skills have a different resource-access contract. Do not
            # silently classify them as local-file observations.
            if not absolute_metadata_path(path) or PurePosixPath(path).name != "SKILL.md":
                raise CoverageError("non-local selected-skill resource unsupported")
            key = event_id(message, index)
            record = {
                "eventId": key,
                "message": message,
                "part": index,
                "turn": turn,
                "skill": name,
                "path": path,
                "timestamp": timestamp,
                "ordinal": item["ordinal"],
                "evidenceKind": "native_instruction_insertion",
                "runtime": "codex",
                "project": self.project,
            }
            prior = self.records.get(key)
            if prior and any(prior[k] != record[k] for k in record if k != "ordinal"):
                raise CoverageError("conflicting selected-skill replay")
            self.records.setdefault(key, record)
