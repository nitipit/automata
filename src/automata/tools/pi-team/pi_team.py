#!/usr/bin/env python3
"""Thin persistent Pi RPC I/O. Agents choose commands, interpret records and stop workers."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import copy
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve()
THINKING = {"off", "minimal", "low", "medium", "high", "xhigh", "max"}
MAX_CONTROL = 64 * 1024 * 1024
MAX_OUTSTANDING = 128


class TeamError(Exception):
    """Compact mechanical error; never a task-success classification."""


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _number(value: Any, name: str, maximum: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
        raise TeamError("invalid_" + name)
    return float(value)


def _integer(value: Any, name: str, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise TeamError("invalid_" + name)
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise TeamError("invalid_" + name)
    return value


def validate_spec(raw: dict) -> dict:
    """Version 2 is deliberately not a compatibility interpretation of batch specs."""
    if not isinstance(raw, dict) or type(raw.get("version")) is not int or raw["version"] != 2:
        raise TeamError("requires_version_2_thin_rpc_spec_see_README")
    spec = copy.deepcopy(raw)
    required = {
        "version",
        "run_dir",
        "cwd",
        "provider",
        "model",
        "thinking",
        "resources",
        "persist_session",
        "storage",
    }
    if not required <= set(spec) or set(spec) - required - {
        "pi_command",
        "startup_timeout_seconds",
        "shutdown_grace_seconds",
    }:
        raise TeamError("invalid_spec_fields")
    run = Path(_text(spec["run_dir"], "run_dir")).expanduser()
    if not run.is_absolute() or run.resolve().is_relative_to(SCRIPT.parent):
        raise TeamError("run_dir_must_be_absolute_outside_tool")
    spec["run_dir"] = str(run.resolve())
    cwd = Path(_text(spec["cwd"], "cwd"))
    if not cwd.is_absolute() or not cwd.is_dir():
        raise TeamError("cwd_must_exist_and_be_absolute")
    spec["cwd"] = str(cwd.resolve())
    for key in ("provider", "model", "thinking"):
        _text(spec[key], key)
    if spec["thinking"] not in THINKING or type(spec["persist_session"]) is not bool:
        raise TeamError("invalid_thinking_or_session_choice")
    # Explicit resources cannot smuggle prompts or override owned I/O/session flags.
    resources = spec["resources"]
    if not isinstance(resources, list):
        raise TeamError("resources_must_be_argument_list")
    switches = {
        "--no-extensions",
        "--no-mcp",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--approve",
        "--no-approve",
        "--offline",
        "--no-tools",
        "--no-builtin-tools",
    }
    valued = {
        "--extension",
        "--skill",
        "--prompt-template",
        "--theme",
        "--tools",
        "--exclude-tools",
        "--system-prompt",
        "--append-system-prompt",
        "--name",
    }
    index = 0
    while index < len(resources):
        arg = _text(resources[index], "resource_arg")
        if arg in valued and index + 1 < len(resources):
            _text(resources[index + 1], "resource_value")
            index += 2
        elif arg in switches:
            index += 1
        else:
            raise TeamError("unsupported_resource_arg")
    command = spec.setdefault("pi_command", ["pi"])
    if not isinstance(command, list) or not command:
        raise TeamError("invalid_pi_command")
    for arg in command:
        _text(arg, "pi_command")
    for key, default, ceiling in (
        ("startup_timeout_seconds", 30, 600),
        ("shutdown_grace_seconds", 5, 60),
    ):
        spec[key] = _number(spec.get(key, default), key, ceiling)
    storage = spec["storage"]
    ceilings = {
        "segment_bytes": 64 * 1024 * 1024,
        "max_segments": 1024,
        "max_record_bytes": 8 * 1024 * 1024,
        "max_read_bytes": 16 * 1024 * 1024,
        "max_read_records": 10000,
    }
    if not isinstance(storage, dict) or set(storage) != set(ceilings):
        raise TeamError("explicit_storage_limits_required")
    for key, ceiling in ceilings.items():
        _integer(storage[key], key, ceiling)
    if storage["segment_bytes"] < storage["max_record_bytes"] * 6 + 1024:
        raise TeamError("segment_too_small_for_encoded_record")
    return spec


def process_identity(pid: int) -> dict | None:
    """Linux boot and process birth identity, not a PID-only ownership claim."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if stat[0] == "Z":
            return None
        return {
            "pid": pid,
            "start_ticks": stat[19],
            "pgrp": int(stat[2]),
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        }
    except (OSError, ValueError, IndexError):
        return None


def identity_alive(identity: dict | None) -> bool:
    return bool(identity and process_identity(identity["pid"]) == identity)


def group_members(
    identity: dict | None, known: list[dict] | None = None, owner_token: str | None = None
) -> list[dict]:
    """Snapshot an owned group while a birth-verified member anchors its ID."""
    if not identity or identity["pgrp"] != identity["pid"]:
        return []
    anchors = [identity, *(known or [])]
    anchored = any(identity_alive(item) and item["pgrp"] == identity["pid"] for item in anchors)
    members = []
    for path in Path("/proc").iterdir():
        if path.name.isdigit():
            item = process_identity(int(path.name))
            if item and item["pgrp"] == identity["pid"]:
                members.append(item)
                if (
                    not anchored
                    and owner_token
                    and item["boot_id"] == identity["boot_id"]
                    and int(item["start_ticks"]) >= int(identity["start_ticks"])
                ):
                    with contextlib.suppress(OSError):
                        environment = (path / "environ").read_bytes().split(b"\x00")
                        if ("PI_TEAM_OWNER_TOKEN=" + owner_token).encode() in environment:
                            anchored = True
    return members if anchored else []


def signal_owned(
    identity: dict | None, sig: int, known: list[dict] | None = None, owner_token: str | None = None
) -> bool:
    if not group_members(identity, known, owner_token):
        return False
    try:
        os.killpg(identity["pid"], sig)
        return True
    except ProcessLookupError:
        return False


class Capture:
    """Bounded whole-record segments. Loss is explicit and never stops pipe drainage."""

    def __init__(self, directory: Path, limits: dict):
        self.directory, self.limits = directory, limits
        directory.mkdir(mode=0o700, exist_ok=True)
        self.next_cursor = 1
        self.segments: list[dict] = []
        self.error: str | None = None
        self.lost_records = 0
        self.lost_bytes = 0
        self.partial_tail = False
        self._recover()

    def _recover(self) -> None:
        # Reads are bounded by configured segment/record ceilings, never read the entire log.
        for path in sorted(self.directory.glob("*.jsonl")):
            first = last = None
            size = 0
            with path.open("rb") as stream:
                while line := stream.readline(self.limits["segment_bytes"] + 1):
                    size += len(line)
                    if not line.endswith(b"\n"):
                        self.partial_tail = True
                        break
                    entry = json.loads(line)
                    cursor = entry["cursor"]
                    first = cursor if first is None else first
                    last = cursor
                    self.next_cursor = max(self.next_cursor, cursor + 1)
            if first is not None:
                self.segments.append({"path": path, "first": first, "last": last, "size": size})
        # Recover is used for read-only offline inspection; no rewriting of damaged tails.

    def facts(self) -> dict:
        return {
            "limits": self.limits,
            "earliest_cursor": self.segments[0]["first"] if self.segments else self.next_cursor,
            "next_cursor": self.next_cursor,
            "capture_error": self.error,
            "lost_records": self.lost_records,
            "lost_bytes": self.lost_bytes,
            "partial_tail": self.partial_tail,
        }

    def loss(self, size: int, error: str) -> None:
        self.next_cursor += 1
        self.lost_records += 1
        self.lost_bytes += size
        self.error = error

    def append(self, stream: str, raw: bytes) -> int | None:
        if self.error == "storage_io_error":
            self.loss(len(raw), self.error)
            return None
        if len(raw) > self.limits["max_record_bytes"]:
            self.loss(len(raw), "oversized_record")
            return None
        cursor = self.next_cursor
        # raw preserves original JSON whitespace and unknown fields. Stderr uses reversible hex.
        value = {
            "cursor": cursor,
            "stream": stream,
            "time": time.time(),
            "raw": raw.decode("utf-8") if stream == "stdout" else raw.hex(),
        }
        encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode() + b"\n"
        try:
            if (
                not self.segments
                or self.segments[-1]["size"] + len(encoded) > self.limits["segment_bytes"]
            ):
                path = self.directory / f"{cursor:020d}.jsonl"
                self.segments.append({"path": path, "first": cursor, "last": cursor, "size": 0})
                # Evict before adding bytes so the configured disk ceiling is never exceeded.
                while len(self.segments) > self.limits["max_segments"]:
                    self.segments[0]["path"].unlink()
                    self.segments.pop(0)
            segment = self.segments[-1]
            fd = os.open(segment["path"], os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(fd, "ab", buffering=0) as output:
                output.write(encoded)
            segment["size"] += len(encoded)
            segment["last"] = cursor
            self.next_cursor += 1
            return cursor
        except OSError:
            self.loss(len(raw), "storage_io_error")
            return None

    def read(self, cursor: int, limit: int, max_bytes: int) -> dict:
        if type(cursor) is not int or cursor < 0 or cursor >= self.next_cursor:
            raise TeamError("invalid_cursor")
        _integer(limit, "limit", self.limits["max_read_records"])
        _integer(max_bytes, "max_bytes", self.limits["max_read_bytes"])
        entries, used, blocked = [], 0, None
        next_cursor = cursor
        earliest = self.facts()["earliest_cursor"]
        gap = cursor < earliest - 1
        for segment in self.segments:
            if segment["last"] <= cursor:
                continue
            with segment["path"].open("rb") as stream:
                while line := stream.readline(self.limits["segment_bytes"] + 1):
                    if not line.endswith(b"\n"):
                        self.partial_tail = True
                        break
                    value = json.loads(line)
                    if value["cursor"] <= cursor:
                        continue
                    if len(entries) >= limit or used + len(line) > max_bytes:
                        blocked = {"cursor": value["cursor"], "required_bytes": len(line)}
                        break
                    gap = gap or value["cursor"] > next_cursor + 1
                    entries.append(value)
                    used += len(line)
                    next_cursor = value["cursor"]
                if blocked:
                    break
        if blocked is None and next_cursor < self.next_cursor - 1:
            gap = True
            next_cursor = self.next_cursor - 1
        return {
            "records": entries,
            "cursor": next_cursor,
            "gap": gap,
            "read_bytes": used,
            "blocked": blocked,
            **self.facts(),
        }


class Controller:
    def __init__(self, run: Path):
        self.run = run
        self.spec = validate_spec(read_json(run / "spec.json"))
        self.state = read_json(run / "state.json")
        self.capture = Capture(run / "capture", self.spec["storage"])
        self.process: asyncio.subprocess.Process | None = None
        self.pending: dict[str, asyncio.Future | None] = {}
        self.write_lock = asyncio.Lock()
        self.stopping = asyncio.Event()
        self.readers: list[asyncio.Task] = []
        self.clients: set[asyncio.Task] = set()

    def save(self) -> None:
        self.state["capture"] = self.capture.facts()
        try:
            write_json(self.run / "state.json", self.state)
        except OSError:
            # Disk/state failure must not strand the pipe readers behind backpressure.
            self.capture.error = "storage_io_error"
            self.state["state_error"] = "state_io_error"
            self.state["capture"] = self.capture.facts()

    def notify_capture_loss(self, before: int) -> None:
        if self.capture.lost_records != before:
            for future in self.pending.values():
                if future is not None and not future.done():
                    future.set_exception(
                        TeamError("capture_loss_outcome_unknown_read_events_and_status")
                    )

    async def stdout(self) -> None:
        assert self.process and self.process.stdout
        buffer = bytearray()
        oversized = 0
        maximum = self.spec["storage"]["max_record_bytes"]
        try:
            while chunk := await self.process.stdout.read(65536):
                before = self.capture.lost_records
                for piece_index, piece in enumerate(chunk.split(b"\n")):
                    if piece_index:
                        if oversized:
                            self.capture.loss(oversized, "oversized_record")
                        elif buffer:
                            await self.record(bytes(buffer))
                        else:
                            self.capture.loss(0, "empty_stdout_frame")
                        buffer.clear()
                        oversized = 0
                    if oversized:
                        oversized += len(piece)
                    elif len(buffer) + len(piece) > maximum:
                        oversized = len(buffer) + len(piece)
                        buffer.clear()
                    else:
                        buffer.extend(piece)
                self.notify_capture_loss(before)
                self.save()
            if buffer or oversized:
                before = self.capture.lost_records
                self.capture.loss(len(buffer) + oversized, "partial_stdout_frame")
                self.notify_capture_loss(before)
        except (OSError, ValueError, UnicodeError):
            self.state["stream_error"] = "stdout_reader_error"
        finally:
            self.state["stdout_closed"] = True
            for future in self.pending.values():
                if future is not None and not future.done():
                    future.set_exception(TeamError("rpc_stream_closed_outcome_unknown"))
            self.save()

    async def record(self, raw: bytes) -> None:
        try:
            record = json.loads(raw)
            if not isinstance(record, dict):
                raise ValueError
            self.capture.append("stdout", raw)
        except (ValueError, UnicodeError):
            self.capture.loss(len(raw), "invalid_stdout_record")
            return
        if record.get("type") == "response" and isinstance(record.get("id"), str):
            future = self.pending.pop(record["id"], None)
            if future is not None and not future.done():
                future.set_result(record)

    async def stderr(self) -> None:
        assert self.process and self.process.stderr
        maximum = min(65536, self.spec["storage"]["max_record_bytes"])
        while chunk := await self.process.stderr.read(maximum):
            self.capture.append("stderr", chunk)
            self.save()

    async def rpc(self, command: dict, timeout: float, send_only: bool = False) -> dict:
        if not isinstance(command, dict) or not isinstance(command.get("type"), str):
            raise TeamError("command_must_be_object_with_type")
        command = dict(command)
        if command["type"] == "extension_ui_response":
            if not send_only or not isinstance(command.get("id"), str):
                raise TeamError("extension_ui_response_requires_id_and_send_only")
        elif send_only:
            raise TeamError("send_only_only_for_extension_ui_response")
        request = command.setdefault("id", uuid.uuid4().hex)
        if not isinstance(request, str) or not request or len(request) > 256:
            raise TeamError("invalid_request_id")
        _number(timeout, "timeout", 3600)
        encoded = json.dumps(command, ensure_ascii=False).encode() + b"\n"
        if len(encoded) > self.spec["storage"]["max_record_bytes"]:
            raise TeamError("command_exceeds_max_record_bytes")
        if (
            not self.process
            or self.process.returncode is not None
            or self.state.get("stdout_closed")
        ):
            raise TeamError("worker_io_unavailable_not_sent")
        assert self.process.stdin
        future = asyncio.get_running_loop().create_future()
        async with self.write_lock:
            # Only pending/ambiguous IDs are retained. Completed-ID uniqueness is caller-owned.
            if not send_only:
                if request in self.pending:
                    raise TeamError("request_id_in_flight_or_unresolved_do_not_resend")
                if len(self.pending) >= MAX_OUTSTANDING:
                    raise TeamError("outstanding_request_limit_not_sent")
                self.pending[request] = future
            try:
                self.process.stdin.write(encoded)
                await asyncio.wait_for(self.process.stdin.drain(), timeout)
            except (OSError, TimeoutError) as error:
                if not send_only:
                    self.pending[request] = None
                return {
                    "transport_error": "write_outcome_unknown",
                    "request_id": request,
                    "retry": False,
                    "detail": type(error).__name__,
                }
        if send_only:
            return {
                "transport": "stdin_drained",
                "request_id": request,
                "pi_acknowledgement": False,
            }
        try:
            return await asyncio.wait_for(future, timeout)
        except (TimeoutError, TeamError) as error:
            return {
                "transport_error": "response_timeout_outcome_unknown"
                if isinstance(error, TimeoutError)
                else str(error),
                "request_id": request,
                "retry": False,
                "recover": "events",
            }
        finally:
            if request in self.pending:
                self.pending[request] = (
                    None  # Bounded ambiguous ID, cleared only by its late response.
                )

    async def start(self) -> None:
        self.process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(SCRIPT),
            "_worker",
            "--worker",
            str(self.run),
            cwd=self.spec["cwd"],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
            env={**os.environ, "PI_TEAM_OWNER_TOKEN": self.state["ownership_token"]},
        )
        self.state["identity"] = process_identity(self.process.pid)
        self.save()
        self.readers = [asyncio.create_task(self.stdout()), asyncio.create_task(self.stderr())]
        reply = await self.rpc({"type": "get_state"}, self.spec["startup_timeout_seconds"])
        data = reply.get("data", {})
        model = data.get("model") or {}
        if (
            reply.get("success") is not True
            or model.get("provider") != self.spec["provider"]
            or model.get("id") != self.spec["model"]
            or data.get("thinkingLevel") != self.spec["thinking"]
        ):
            raise TeamError("effective_settings_unverified")
        if (
            data.get("isStreaming") is not False
            or data.get("isCompacting") is not False
            or data.get("pendingMessageCount") != 0
            or data.get("messageCount") != 0
        ):
            raise TeamError("worker_not_fresh_idle")
        if self.spec["persist_session"]:
            session_file = data.get("sessionFile")
            if (
                data.get("sessionId") != self.state["session_id"]
                or not isinstance(session_file, str)
                or not Path(session_file)
                .resolve()
                .is_relative_to((self.run / "sessions").resolve())
            ):
                raise TeamError("session_identity_unverified")
        self.state["effective"] = {
            "provider": model["provider"],
            "model": model["id"],
            "thinking": data["thinkingLevel"],
            "persist_session": self.spec["persist_session"],
        }
        self.state["status"] = "open"
        self.save()

    async def close(self) -> None:
        if not self.process:
            self.state.update(status="closed", shutdown="no_child")
            self.save()
            return
        self.state["status"] = "closing"
        self.save()
        grace = self.spec["shutdown_grace_seconds"]
        identity = self.state.get("identity")
        token = self.state["ownership_token"]
        members = group_members(identity, owner_token=token)
        if self.process.stdin:
            self.process.stdin.close()
        shutdown = "eof"
        for sig, label in (
            (None, "eof"),
            (signal.SIGTERM, "terminated"),
            (signal.SIGKILL, "killed"),
        ):
            if sig:
                signal_owned(identity, sig, members, token)
            try:
                await asyncio.wait_for(self.process.wait(), grace)
                shutdown = label
                break
            except TimeoutError:
                shutdown = "unconfirmed"
        remaining = group_members(identity, members, token)
        if remaining:
            signal_owned(identity, signal.SIGTERM, remaining, token)
            await asyncio.sleep(grace)
            signal_owned(identity, signal.SIGKILL, remaining, token)
            await asyncio.sleep(0.05)
            shutdown = (
                "unconfirmed"
                if group_members(identity, remaining, token)
                else "descendants_terminated"
            )
        try:
            await asyncio.wait_for(asyncio.gather(*self.readers, return_exceptions=True), grace)
        except TimeoutError:
            shutdown = "unconfirmed"
        self.state.update(status="closed", shutdown=shutdown, exit_code=self.process.returncode)
        self.save()

    async def client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        if len(self.clients) >= MAX_OUTSTANDING:
            writer.close()
            return
        self.clients.add(task)
        try:
            raw = await asyncio.wait_for(reader.readline(), 10)
            if len(raw) > MAX_CONTROL or not raw.endswith(b"\n"):
                raise TeamError("invalid_control_frame")
            request = json.loads(raw)
            kind = request.get("op")
            if kind == "rpc":
                if self.state["status"] != "open":
                    raise TeamError("worker_not_open_not_sent")
                response = await self.rpc(
                    request["command"], request["timeout"], request.get("send_only", False)
                )
                result = {"rpc_response": response, "capture": self.capture.facts()}
            elif kind == "events":
                result = self.capture.read(
                    request["cursor"], request["limit"], request["max_bytes"]
                )
            elif kind == "stop":
                self.stopping.set()
                result = {"stop_requested": True}
            else:
                raise TeamError("unknown_control_operation")
        except (TeamError, ValueError, KeyError, OSError, TimeoutError) as error:
            result = {
                "transport_error": str(error)
                if isinstance(error, TeamError)
                else type(error).__name__
            }
        try:
            writer.write(json.dumps(result, ensure_ascii=True).encode() + b"\n")
            await asyncio.wait_for(writer.drain(), 10)
        except (OSError, TimeoutError):
            pass  # Client loss cannot cancel or resend a command already written to Pi.
        finally:
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()
            self.clients.discard(task)


async def control(run: Path) -> None:
    # Launch gate prevents a stale parent state write from overwriting controller facts.
    until = time.monotonic() + 10
    while not (run / "launch-ready.json").exists():
        if time.monotonic() >= until:
            return
        await asyncio.sleep(0.02)
    owner = Controller(run)
    owner.state["controller"] = process_identity(os.getpid())
    owner.save()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, owner.stopping.set)
    server = await asyncio.start_unix_server(
        owner.client, path=owner.state["socket"], limit=MAX_CONTROL
    )
    try:
        try:
            await owner.start()
        except Exception as error:
            owner.state["startup_error"] = (
                str(error) if isinstance(error, TeamError) else type(error).__name__
            )
            await owner.close()  # Failed birth/settings verification, not ordinary run settlement.
            return
        await owner.stopping.wait()  # No run/task/deadline interpretation here.
        await owner.close()
    finally:
        server.close()
        await server.wait_closed()
        for task in list(owner.clients):
            task.cancel()
        await asyncio.gather(*owner.clients, return_exceptions=True)
        with contextlib.suppress(OSError):
            Path(owner.state["socket"]).unlink()
            Path(owner.state["socket"]).parent.rmdir()


def exec_worker(run: Path) -> None:
    spec, state = read_json(run / "spec.json"), read_json(run / "state.json")
    write_json(
        run / "worker-lease.json",
        {"identity": process_identity(os.getpid()), "ownership_token": state["ownership_token"]},
    )
    if not identity_alive(state.get("controller")):
        raise TeamError("controller_died_before_exec")
    command = [
        *spec["pi_command"],
        "--mode",
        "rpc",
        "--provider",
        spec["provider"],
        "--model",
        spec["model"],
        "--thinking",
        spec["thinking"],
        *spec["resources"],
    ]
    if spec["persist_session"]:
        command.extend(
            ["--session-dir", str(run / "sessions"), "--session-id", state["session_id"]]
        )
    else:
        command.append("--no-session")
    os.execvpe(command[0], command, os.environ)


def status(run: Path) -> dict:
    state = read_json(run / "state.json")
    keys = {
        "version",
        "worker",
        "status",
        "created_at",
        "controller",
        "identity",
        "effective",
        "capture",
        "shutdown",
        "exit_code",
        "startup_error",
        "stream_error",
        "stdout_closed",
    }
    result = {key: value for key, value in state.items() if key in keys}
    result["controller_alive"] = identity_alive(state.get("controller"))
    result["worker_alive"] = identity_alive(state.get("identity"))
    if not result["controller_alive"] and result["status"] != "closed":
        result["status"] = "controller_unavailable"
    return result


async def request(run: Path, value: dict, timeout: float) -> dict:
    state = read_json(run / "state.json")
    if not identity_alive(state.get("controller")):
        raise TeamError("controller_unavailable_not_sent")
    try:
        async with asyncio.timeout(timeout):
            reader, writer = await asyncio.open_unix_connection(state["socket"], limit=MAX_CONTROL)
            try:
                encoded = json.dumps(value, ensure_ascii=True).encode() + b"\n"
                if len(encoded) > MAX_CONTROL:
                    raise TeamError("control_request_too_large_not_sent")
                writer.write(encoded)
                await writer.drain()
                raw = await reader.readline()
                if not raw.endswith(b"\n"):
                    raise TeamError("controller_response_lost_outcome_unknown")
                return json.loads(raw)
            finally:
                writer.close()
                with contextlib.suppress(OSError):
                    await writer.wait_closed()
    except (OSError, TimeoutError) as error:
        # Connection errors may be prewrite; conservative unknown avoids accidental duplicate work.
        raise TeamError("controller_transport_unavailable_outcome_unknown_do_not_resend") from error


def create(spec_path: Path) -> dict:
    spec = validate_spec(read_json(spec_path))
    if not Path("/proc/sys/kernel/random/boot_id").is_file():
        raise TeamError("linux_proc_required")
    if shutil.which(spec["pi_command"][0]) is None:
        raise TeamError("pi_executable_not_found")
    run = Path(spec["run_dir"])
    run.mkdir(parents=True, mode=0o700, exist_ok=False)
    for name in ("sessions",):
        (run / name).mkdir(mode=0o700)
    socket_dir = Path(tempfile.mkdtemp(prefix="pi-team-"))
    state = {
        "version": 2,
        "worker": str(run),
        "status": "starting",
        "created_at": time.time(),
        "socket": str(socket_dir / "io.sock"),
        "session_id": uuid.uuid4().hex,
        "ownership_token": uuid.uuid4().hex,
    }
    write_json(run / "spec.json", spec)
    write_json(run / "state.json", state)
    process = subprocess.Popen(
        [sys.executable, str(SCRIPT), "_controller", "--worker", str(run)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    state["controller"] = process_identity(process.pid)
    write_json(run / "state.json", state)
    write_json(run / "launch-ready.json", {"ready": True})
    until = time.monotonic() + spec["startup_timeout_seconds"] + 2
    while time.monotonic() < until:
        current = status(run)
        if current["status"] in {"open", "closed", "controller_unavailable"}:
            return current
        if process.poll() is not None:
            return status(run)
        time.sleep(0.02)
    return {**status(run), "create_wait_expired": True, "recover": "status"}


def stop(run: Path) -> dict:
    state = read_json(run / "state.json")
    grace = read_json(run / "spec.json")["shutdown_grace_seconds"]
    if identity_alive(state.get("controller")):
        try:
            asyncio.run(request(run, {"op": "stop"}, 2))
        except TeamError:
            # Explicit stop authorizes shutdown; SIGTERM tells the owner to close.
            signal_owned(state["controller"], signal.SIGTERM)
        until = time.monotonic() + grace * 6 + 2
        while identity_alive(state.get("controller")) and time.monotonic() < until:
            time.sleep(0.02)
        if identity_alive(state.get("controller")):
            # Freeze the spawner before lease snapshot; birth verification prevents PID reuse.
            signal_owned(state["controller"], signal.SIGKILL)
            time.sleep(0.05)
    if identity_alive(state.get("controller")):
        return {**status(run), "shutdown": "unconfirmed"}
    # Controller may have died before saving birth identity; exec publishes independent lease.
    state = read_json(run / "state.json")
    lease = read_json(run / "worker-lease.json") if (run / "worker-lease.json").exists() else {}
    identity = lease.get("identity", state.get("identity"))
    token = state["ownership_token"]
    members = group_members(identity, owner_token=token)
    if members:
        signal_owned(identity, signal.SIGTERM, members, token)
        time.sleep(grace)
        signal_owned(identity, signal.SIGKILL, members, token)
        time.sleep(0.05)
    if group_members(identity, members, token):
        return {**status(run), "shutdown": "unconfirmed"}
    if state.get("status") != "closed":
        state.update(status="closed", shutdown="explicit_orphan_cleanup")
        write_json(run / "state.json", state)
    with contextlib.suppress(OSError):
        Path(state["socket"]).unlink()
        Path(state["socket"]).parent.rmdir()
    return status(run)


def main(argv: list[str] | None = None) -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser(
        "create", help="Create one idle worker; never dispatch a prompt"
    ).add_argument("--spec", type=Path, required=True)
    for name in ("rpc", "events", "status", "stop", "_controller", "_worker"):
        command = commands.add_parser(
            name, help=argparse.SUPPRESS if name.startswith("_") else name
        )
        command.add_argument("--worker", type=Path, required=True)
        if name == "rpc":
            command.add_argument(
                "--command", type=Path, required=True, help="Original Pi command JSON file"
            )
            command.add_argument("--timeout", type=float, default=30)
            command.add_argument("--send-only", action="store_true")
        elif name == "events":
            command.add_argument("--cursor", type=int, required=True)
            command.add_argument("--limit", type=int, required=True)
            command.add_argument("--max-bytes", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "create":
            result = create(args.spec)
        elif args.action == "_worker":
            exec_worker(args.worker)
            return 0
        elif args.action == "_controller":
            asyncio.run(control(args.worker))
            return 0
        elif args.action == "status":
            result = status(args.worker)
        elif args.action == "stop":
            result = stop(args.worker)
        elif args.action == "rpc":
            _number(args.timeout, "timeout", 3600)
            result = asyncio.run(
                request(
                    args.worker,
                    {
                        "op": "rpc",
                        "command": read_json(args.command),
                        "timeout": args.timeout,
                        "send_only": args.send_only,
                    },
                    args.timeout * 2 + 2,
                )
            )
        else:
            value = {
                "op": "events",
                "cursor": args.cursor,
                "limit": args.limit,
                "max_bytes": args.max_bytes,
            }
            if status(args.worker)["controller_alive"]:
                result = asyncio.run(request(args.worker, value, 10))
            else:
                spec = read_json(args.worker / "spec.json")
                capture = Capture(args.worker / "capture", spec["storage"])
                saved = read_json(args.worker / "state.json").get("capture", {})
                capture.next_cursor = max(capture.next_cursor, saved.get("next_cursor", 1))
                capture.error = saved.get("capture_error")
                capture.lost_records = saved.get("lost_records", 0)
                capture.lost_bytes = saved.get("lost_bytes", 0)
                result = capture.read(args.cursor, args.limit, args.max_bytes)
                result["controller_unavailable"] = True
                result["last_controller_capture"] = read_json(args.worker / "state.json").get(
                    "capture"
                )
        if args.action == "rpc" and "rpc_response" in result:
            if result["capture"]["capture_error"]:
                print(json.dumps({"capture": result["capture"]}), file=sys.stderr)
            result = result["rpc_response"]
        print(json.dumps(result, ensure_ascii=True))
        return 1 if "transport_error" in result else 0
    except KeyboardInterrupt:
        return 130
    except (TeamError, OSError, ValueError) as error:
        code = str(error) if isinstance(error, TeamError) else type(error).__name__
        print(json.dumps({"transport_error": code}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
