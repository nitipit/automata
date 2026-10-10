"""Dictify contracts for composer receipts and bounded reading evidence."""

import re

from dictify import Field, Model
from reading_state import ApiError


class MentionIdentity(Model):
    kind = Field(required=True).instance(str).verify(lambda v: v in ("individual", "all"))
    name = Field(required=True).instance(str).verify(lambda v: bool(v.strip()))
    member_id = Field(required=True).instance((str, type(None)))

    def post_validate(self):
        if self.kind == "all":
            if self.name != "All" or self.member_id is not None:
                raise ValueError("All identity must not contain a member ID")
        elif (
            self.name == "All"
            or not isinstance(self.member_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]+", self.member_id)
        ):
            raise ValueError("Individual identity needs a valid member ID and name")


class DraftState(Model):
    version = Field(required=True).verify(lambda v: type(v) is int and v == 1)
    kind = Field(required=True).instance(str).verify(lambda v: v == "composer")
    token = Field(required=True).instance(str).verify(lambda v: bool(v))
    digest = Field(required=True).instance(str).match(r"[a-f0-9]{64}$")
    status = (
        Field(required=True)
        .instance(str)
        .verify(lambda v: v in ("prepared", "uncertain", "dispatched"))
    )
    chat_id = Field(required=True).instance(str).match(r"[A-Za-z0-9_-]+$")
    route = Field(required=True).instance(str).verify(lambda v: bool(v))
    expected_mention = Field(required=True).instance((dict, type(None)))
    verified_mention = Field(required=True).instance((dict, type(None)))

    def post_validate(self):
        for value in (self.expected_mention, self.verified_mention):
            if value is not None:
                MentionIdentity(value)
        if self.expected_mention != self.verified_mention:
            raise ValueError("Expected and verified mention identities differ")


def validate_draft(value):
    try:
        if not isinstance(value, dict):
            raise ValueError("Receipt must be a JSON object")
        return DraftState(value).dict()
    except (ValueError, TypeError, AssertionError, Model.Error) as exc:
        raise ApiError(
            "DRAFT_STATE_INVALID", "Invalid or legacy composer receipt; preserve it for inspection"
        ) from exc


class PreparedResult(Model):
    status = Field(required=True).instance(str).verify(lambda v: v == "prepared")
    chat = Field(required=True).instance(str)
    chat_id = Field(required=True).instance(str)
    token = Field(required=True).instance(str)
    characters = Field(required=True).verify(lambda v: type(v) is int and v >= 0)
    images = Field(required=True).verify(lambda v: type(v) is int and v >= 0)
    mention = Field(required=True).instance((str, type(None)))
    mention_identity = Field(required=True).instance((dict, type(None)))

    def post_validate(self):
        if self.mention_identity is not None:
            MentionIdentity(self.mention_identity)
            if self.mention != self.mention_identity["name"]:
                raise ValueError("Prepared mention label and identity differ")
        elif self.mention is not None:
            raise ValueError("Mention label without a verified identity")


class ReadWindow(Model):
    since_ms = Field(required=True).instance((int, type(None)))
    until_ms = Field(required=True).instance((int, type(None)))
    before = Field(required=True).instance((list, tuple, type(None)))
    after = Field(required=True).instance((list, tuple, type(None)))
    lower_boundary_reached = Field(required=True).instance(bool)
    upper_boundary_reached = Field(required=True).instance(bool)
    returned_all_loaded_matches = Field(required=True).instance(bool)


class ReadCoverage(Model):
    boundary_reached = Field(required=True).instance(bool)
    reason = Field(required=True).instance(str)
    checkpoint_found = Field(required=True).instance(bool)
    history_gap = Field(required=True).instance(bool)
    older_history_unverified = Field(required=True).instance(bool)
    loaded_messages = Field(required=True).verify(lambda v: type(v) is int and v >= 0)
    more = Field(required=True).instance(bool)
    result_overflow = Field(required=True).instance(bool)
    older_history_availability = Field(required=True).instance(str).verify(lambda v: v == "unknown")
    attachments_reviewed = Field(required=True).instance(bool)
    observed_at = Field(required=True).instance(str)
    newest_loaded_timestamp_ms = Field(required=True).instance((int, type(None)))
    chat_list_latest_timestamp_ms = Field(required=True).instance((int, type(None)))
    freshness = (
        Field(required=True)
        .instance(str)
        .verify(lambda v: v in ("unknown", "newer_chat_list_evidence"))
    )
    requested_window = Field(required=True).instance(dict)
    cursor_found = Field().instance(bool)
    code = Field().instance(str)

    def post_validate(self):
        ReadWindow(self.requested_window)
        if self.more != self.result_overflow:
            raise ValueError("more is the compatibility alias for result_overflow")
