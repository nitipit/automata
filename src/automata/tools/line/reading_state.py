"""Private consumer checkpoints and recoverable journal commits for line.py.

A pending record is fsynced before journal replacement. Recovery compares the
before/after hashes, then commits message metadata. Never infer success from a
message timestamp or LINE's unread badge.
"""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from dictify import Field, Model


class ApiError(RuntimeError):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code = code
        self.details = details


def ensure(condition, code, message, **details):
    if not condition:
        raise ApiError(code, message, **details)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode()


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix="." + path.name + "-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        sync_dir(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class MessageStamp(Model):
    timestamp_ms = Field(required=True).instance(int)
    fingerprint = Field(required=True).instance(str)


class ChatState(Model):
    name = Field(required=True).instance(str)
    since_ms = Field(required=True).instance(int)
    anchor_id = Field(required=True).instance(str)
    last_check = Field(required=True).instance(str)
    seen = Field(required=True).instance(dict)
    coverage = Field(required=True).instance(dict)


class ConsumerState(Model):
    version = Field(required=True).instance(int)
    consumer = Field(required=True).instance(str)
    revision = Field(required=True).instance(int)
    output = Field(required=True).instance(str)
    output_size = Field(required=True).instance(int)
    output_hash = Field(required=True).instance(str)
    chats = Field(required=True).instance(dict)


class Pending(Model):
    version = Field(required=True).instance(int)
    before_hash = Field(required=True).instance(str)
    after_hash = Field(required=True).instance(str)
    append = Field(required=True).instance(str)
    next_state = Field(required=True).instance(dict)


def validate_state(value, consumer):
    try:
        ConsumerState(value)
        assert value["version"] == 1 and value["consumer"] == consumer
        assert type(value["revision"]) is int and value["revision"] >= 0
        assert type(value["output_size"]) is int and value["output_size"] >= 0
        for chat_id, entry in value["chats"].items():
            assert isinstance(chat_id, str) and chat_id
            ChatState(entry)
            assert type(entry["since_ms"]) is int and entry["since_ms"] >= 0
            for message_id, stamp in entry["seen"].items():
                assert isinstance(message_id, str) and message_id
                MessageStamp(stamp)
                assert type(stamp["timestamp_ms"]) is int and stamp["timestamp_ms"] >= 0
                assert re.fullmatch(r"[a-f0-9]{64}", stamp["fingerprint"])
            assert not entry["anchor_id"] or entry["anchor_id"] in entry["seen"]
    except (AssertionError, KeyError, TypeError, Model.Error) as exc:
        raise ApiError(
            "STATE_INVALID", "Invalid reading state; preserve it for inspection"
        ) from exc
    return value


class ReadingStore:
    def __init__(self, root, consumer):
        ensure(
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", consumer),
            "INVALID_ARGUMENT",
            "Consumer must be 1-64 letters, digits, underscore or hyphen",
        )
        self.consumer = consumer
        self.directory = Path(root) / "reading" / consumer
        self.path = self.directory / "checkpoints.json"
        self.pending = self.directory / "pending.json"

    def load(self):
        if not self.path.exists():
            return {
                "version": 1,
                "consumer": self.consumer,
                "revision": 0,
                "output": "",
                "output_size": 0,
                "output_hash": "",
                "chats": {},
            }
        try:
            value = json.loads(self.path.read_text())
        except (ValueError, OSError) as exc:
            raise ApiError("STATE_INVALID", "Cannot decode reading checkpoints") from exc
        return validate_state(value, self.consumer)

    def check_output(self, state, output):
        output = Path(output).absolute()
        ensure(not output.is_symlink(), "OUTPUT_CONFLICT", "Output must not be a symbolic link")
        output = output.resolve()
        ensure(
            not state["output"] or state["output"] == str(output),
            "OUTPUT_CONFLICT",
            "Consumer is bound to a different output; use a new consumer",
            output=state["output"],
        )
        data = output.read_bytes() if output.exists() else b""
        if state["revision"]:
            ensure(
                output.exists(), "OUTPUT_MISSING", "Saved journal is missing; checkpoints retained"
            )
            ensure(
                len(data) >= state["output_size"]
                and digest(data[: state["output_size"]]) == state["output_hash"],
                "OUTPUT_CONFLICT",
                "Previously saved journal content changed; inspect before collecting",
            )
        return output, data

    def recover(self):
        """Finish a previously authorized local append, never a LINE send."""
        if not self.pending.exists():
            return False
        try:
            pending = json.loads(self.pending.read_text())
            Pending(pending)
            ensure(pending["version"] == 1, "STATE_INVALID", "Unsupported transaction version")
            next_state = validate_state(pending["next_state"], self.consumer)
        except (ValueError, KeyError, Model.Error) as exc:
            raise ApiError("STATE_INVALID", "Invalid pending journal transaction") from exc
        state = self.load()
        ensure(
            not state["output"] or state["output"] == next_state["output"],
            "OUTPUT_CONFLICT",
            "Pending transaction targets a different output",
        )
        ensure(
            next_state["revision"] != state["revision"] or state == next_state,
            "STATE_INVALID",
            "Committed state differs from pending transaction",
        )
        ensure(
            next_state["revision"] in (state["revision"], state["revision"] + 1),
            "STATE_INVALID",
            "Pending revision does not match checkpoint",
        )
        output = Path(next_state["output"])
        ensure(
            output.is_absolute() and not output.is_symlink(),
            "OUTPUT_CONFLICT",
            "Invalid output target",
        )
        data = output.read_bytes() if output.exists() else b""
        current_hash = digest(data)
        if current_hash == pending["before_hash"]:
            data += pending["append"].encode()
            ensure(
                digest(data) == pending["after_hash"], "STATE_INVALID", "Transaction hash mismatch"
            )
            atomic(output, data)
        else:
            ensure(
                current_hash == pending["after_hash"],
                "OUTPUT_CONFLICT",
                "Journal changed during interrupted append; no automatic overwrite",
            )
        ensure(
            len(data) == next_state["output_size"] and digest(data) == next_state["output_hash"],
            "STATE_INVALID",
            "Checkpoint does not describe the saved journal",
        )
        atomic(self.path, json_bytes(next_state))
        self.pending.unlink()
        sync_dir(self.directory)
        return True

    def commit(self, state, output, section, chats):
        ensure(not self.pending.exists(), "RECOVERY_REQUIRED", "Recover previous append first")
        ensure(
            state == self.load(),
            "STATE_CONFLICT",
            "Checkpoints changed during collection; reload before committing",
        )
        output, before = self.check_output(state, output)
        after = before + section.encode()
        next_state = dict(
            state,
            revision=state["revision"] + 1,
            output=str(output),
            output_size=len(after),
            output_hash=digest(after),
            chats=chats,
        )
        validate_state(next_state, self.consumer)
        pending = {
            "version": 1,
            "before_hash": digest(before),
            "after_hash": digest(after),
            "append": section,
            "next_state": next_state,
        }
        atomic(self.pending, json_bytes(pending))
        self.recover()
        return next_state
