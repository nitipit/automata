#!/usr/bin/env python3
"""Bounded, flat Pi RPC teams. Standard library except the explicit NodalWire adapter."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import copy
import importlib.util
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

TERMINAL = {"succeeded", "failed", "stopped", "timed_out"}
THINKING = {"off", "minimal", "low", "medium", "high", "xhigh", "max"}
SCRIPT = Path(__file__).resolve()


class TeamError(Exception):
    """Expected, compact error code; details belong in private artifacts."""


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def private_log(path: Path):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    return os.fdopen(fd, "ab", buffering=0)


def append_event(run: Path, event: str, **fields: Any) -> None:
    with private_log(run / "events.jsonl") as stream:
        stream.write((json.dumps({"time": time.time(), "event": event, **fields}) + "\n").encode())


def _number(value: Any, name: str, maximum: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
        raise TeamError(f"invalid_{name}")
    return float(value)


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise TeamError(f"invalid_{name}")
    return value


def validate_spec(raw: dict) -> dict:
    """Validate without I/O side effects. Return a normalized private spec."""
    if not isinstance(raw, dict) or type(raw.get("version")) is not int or raw["version"] != 1:
        raise TeamError("unsupported_spec_version")
    spec = copy.deepcopy(raw)
    allowed = {
        "version",
        "run_dir",
        "deadline_seconds",
        "startup_timeout_seconds",
        "shutdown_grace_seconds",
        "callback",
        "workers",
        "pi_command",
    }
    if set(spec) - allowed:
        raise TeamError("unknown_spec_fields")
    run = Path(_text(spec.get("run_dir"), "run_dir")).expanduser()
    if not run.is_absolute() or run.resolve().is_relative_to(SCRIPT.parent):
        raise TeamError("run_dir_must_be_absolute_outside_tool")
    spec["run_dir"] = str(run.resolve())
    spec["deadline_seconds"] = _number(spec.get("deadline_seconds"), "deadline", 86400)
    spec["startup_timeout_seconds"] = _number(
        spec.get("startup_timeout_seconds", 30), "startup_timeout", 600
    )
    spec["shutdown_grace_seconds"] = _number(
        spec.get("shutdown_grace_seconds", 5), "shutdown_grace", 60
    )
    callback = spec.get("callback")
    if not isinstance(callback, dict) or set(callback) - {
        "name",
        "endpoint",
        "recipient",
        "timeout_seconds",
    }:
        raise TeamError("invalid_callback")
    for key in ("name", "recipient"):
        name = _text(callback.get(key), "callback_" + key)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", name):
            raise TeamError("invalid_callback_" + key)
    if callback["name"] == callback["recipient"]:
        raise TeamError("callback_names_must_differ")
    endpoint = _text(callback.get("endpoint"), "callback_endpoint")
    try:
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme != "tcp"
            or parsed.hostname not in {"127.0.0.1", "::1"}
            or not parsed.port
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError
    except ValueError as error:
        raise TeamError("callback_requires_loopback_endpoint") from error
    callback["timeout_seconds"] = _number(
        callback.get("timeout_seconds", 15), "callback_timeout", 120
    )
    workers = spec.get("workers")
    if not isinstance(workers, list) or not 1 <= len(workers) <= 32:
        raise TeamError("workers_must_have_1_to_32_entries")
    ids = set()
    for worker in workers:
        if not isinstance(worker, dict) or set(worker) != {
            "id",
            "prompt",
            "cwd",
            "provider",
            "model",
            "thinking",
        }:
            raise TeamError("invalid_worker_fields")
        for key in worker:
            _text(worker[key], "worker_" + key)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", worker["id"]) or worker["id"] in ids:
            raise TeamError("invalid_or_duplicate_worker_id")
        ids.add(worker["id"])
        cwd = Path(worker["cwd"])
        if not cwd.is_absolute() or not cwd.is_dir():
            raise TeamError("worker_cwd_must_exist_and_be_absolute")
        worker["cwd"] = str(cwd.resolve())
        if worker["thinking"] not in THINKING:
            raise TeamError("invalid_thinking")
    command = spec.setdefault("pi_command", ["pi"])
    if not isinstance(command, list) or not command:
        raise TeamError("invalid_pi_command")
    for arg in command:
        _text(arg, "pi_command")
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
    """Snapshot an owned group while a birth-verified member still anchors its ID."""
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
    identity: dict | None,
    sig: int,
    known: list[dict] | None = None,
    owner_token: str | None = None,
) -> bool:
    if not group_members(identity, known, owner_token):
        return False
    try:
        os.killpg(identity["pid"], sig)
        return True
    except ProcessLookupError:
        return False


def compact_state(state: dict) -> dict:
    """Allowlist compact fields; never return arbitrary RPC errors/content."""
    keys = {
        "version",
        "run_id",
        "run_dir",
        "status",
        "created_at",
        "deadline_at",
        "finished_at",
        "supervisor",
        "watchdog",
        "callback",
        "timings",
        "error",
        "shutdown",
        "supervisor_alive",
    }
    result = {key: state[key] for key in keys if key in state}
    worker_keys = {
        "id",
        "status",
        "identity",
        "effective",
        "prompt_id",
        "timings",
        "error",
        "stop_reason",
        "settled",
        "shutdown",
        "exit_code",
    }
    result["workers"] = {
        key: {k: v for k, v in worker.items() if k in worker_keys}
        for key, worker in state.get("workers", {}).items()
    }
    return result


class Callback:
    """Published Node adapter. No reconnect/retry or relay management."""

    def __init__(self, node: Any, config: dict):
        self.node, self.config = node, config
        self.nonce = uuid.uuid4().hex
        self.acked = asyncio.Event()
        self.reader = asyncio.create_task(self._drain())

    @classmethod
    async def connect(cls, config: dict) -> Callback:
        from nodalwire import Node

        node = await Node.connect(
            config["name"], config["endpoint"], timeout=config["timeout_seconds"]
        )
        return cls(node, config)

    async def _drain(self) -> None:
        while True:
            message = await self.node.receive()
            try:
                envelope = json.loads(message.payload)
                if envelope.get("version") != 1 or envelope.get("type") != "message":
                    continue
                value = json.loads(envelope["text"])
                if (
                    message.sender == self.config["recipient"]
                    and value.get("version") == 1
                    and value.get("type") == "pi_team_probe_ack"
                    and value.get("nonce") == self.nonce
                ):
                    self.acked.set()
            except (ValueError, AttributeError, TypeError, KeyError):
                continue

    async def send(self, value: dict) -> None:
        await self.node.send(
            self.config["recipient"],
            json.dumps({"version": 1, "type": "message", "text": json.dumps(value)}).encode(),
            timeout=self.config["timeout_seconds"],
        )

    async def probe(self, run: Path) -> None:
        await self.send(
            {
                "version": 1,
                "type": "pi_team_probe",
                "run_dir": str(run),
                "nonce": self.nonce,
                "reply_to": self.config["name"],
            }
        )
        await asyncio.wait_for(self.acked.wait(), self.config["timeout_seconds"])
        if self.reader.done():
            self.reader.result()

    async def close(self) -> None:
        self.reader.cancel()
        await asyncio.gather(self.reader, return_exceptions=True)
        await self.node.close(timeout=1)


class Worker:
    def __init__(self, owner: Supervisor, spec: dict):
        self.owner, self.spec = owner, spec
        self.id = spec["id"]
        self.view = owner.state["workers"][self.id]
        self.process: asyncio.subprocess.Process | None = None
        self.pending: dict[str, asyncio.Future] = {}
        self.settled = asyncio.Event()
        self.readers: list[asyncio.Task] = []
        self.last_assistant: dict | None = None
        self.protocol_error = False
        self.dispatched = False
        self.session_id = uuid.uuid4().hex
        self.view["ownership_token"] = uuid.uuid4().hex
        self.base = owner.run / "workers" / self.id

    async def command(self, kind: str, **fields: Any) -> dict:
        assert self.process and self.process.stdin
        request = uuid.uuid4().hex
        if kind == "prompt":
            self.view["prompt_id"] = request
            self.dispatched = True
            self.owner.save()
        future = asyncio.get_running_loop().create_future()
        self.pending[request] = future
        try:
            self.process.stdin.write(
                json.dumps({"id": request, "type": kind, **fields}).encode() + b"\n"
            )
            await self.process.stdin.drain()
            reply = await asyncio.wait_for(future, self.owner.spec["startup_timeout_seconds"])
            if not reply.get("success"):
                raise TeamError(kind + "_rejected")
            return reply.get("data") or {}
        finally:
            self.pending.pop(request, None)

    async def drain_stdout(self) -> None:
        assert self.process and self.process.stdout
        try:
            with private_log(self.base.with_suffix(".rpc.jsonl")) as log:
                while line := await self.process.stdout.readline():
                    log.write(line)
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise ValueError("RPC record must be an object")
                    kind = record.get("type")
                    if kind == "response":
                        future = self.pending.get(record.get("id"))
                        if future is not None and not future.done():
                            future.set_result(record)
                    elif kind == "message_end" and self.dispatched:
                        message = record.get("message", {})
                        if message.get("role") == "assistant":
                            self.last_assistant = message
                    elif kind == "agent_end" and self.dispatched:
                        for message in record.get("messages", []):
                            if message.get("role") == "assistant":
                                self.last_assistant = message
                    elif kind == "agent_settled" and self.dispatched:
                        self.view["settled"] = {"aborted": record.get("aborted", False)}
                        self.settled.set()
        except Exception:
            self.protocol_error = True
        finally:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(TeamError("rpc_stream_closed"))
            self.settled.set()

    async def drain_stderr(self) -> None:
        assert self.process and self.process.stderr
        with private_log(self.base.with_suffix(".stderr.log")) as log:
            while chunk := await self.process.stderr.read(65536):
                log.write(chunk)

    async def start(self) -> None:
        then = time.monotonic()
        self.view["status"] = "starting"
        self.owner.save()
        session_dir = self.owner.run / "sessions" / self.id
        session_dir.mkdir(parents=True, mode=0o700)
        command = [
            sys.executable,
            str(SCRIPT),
            "_worker",
            "--run",
            str(self.owner.run),
            "--worker",
            self.id,
            "--session-id",
            self.session_id,
        ]
        spawning = asyncio.create_task(
            asyncio.create_subprocess_exec(
                *command,
                cwd=self.spec["cwd"],
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
                env={**os.environ, "PI_TEAM_OWNER_TOKEN": self.view["ownership_token"]},
                limit=16 * 1024 * 1024,
            )
        )
        cancelled = False
        try:
            self.process = await asyncio.shield(spawning)
        except asyncio.CancelledError:
            # Cancellation must not discard a child born during subprocess setup.
            self.process = await spawning
            cancelled = True
        self.view["identity"] = process_identity(self.process.pid)
        self.view["timings"]["spawn_seconds"] = time.monotonic() - then
        self.owner.save()
        self.readers = [
            asyncio.create_task(self.drain_stdout()),
            asyncio.create_task(self.drain_stderr()),
        ]
        if cancelled:
            raise asyncio.CancelledError
        effective = await self.command("get_state")
        model = effective.get("model") or {}
        if (
            model.get("provider") != self.spec["provider"]
            or model.get("id") != self.spec["model"]
            or effective.get("thinkingLevel") != self.spec["thinking"]
        ):
            raise TeamError("effective_settings_mismatch")
        session_file = effective.get("sessionFile")
        if (
            effective.get("sessionId") != self.session_id
            or not isinstance(session_file, str)
            or not Path(session_file).resolve().is_relative_to(session_dir.resolve())
        ):
            raise TeamError("session_identity_unverified")
        if (
            effective.get("isStreaming") is not False
            or effective.get("isCompacting") is not False
            or effective.get("pendingMessageCount") != 0
            or effective.get("messageCount") != 0
        ):
            raise TeamError("worker_not_fresh_idle")
        self.view["effective"] = {
            "provider": model["provider"],
            "model": model["id"],
            "thinking": effective["thinkingLevel"],
            "session_id": effective["sessionId"],
            "session_file": session_file,
        }
        # Do not inherit automatic provider retry from a user's Pi settings.
        await self.command("set_auto_retry", enabled=False)
        self.view["timings"]["ready_seconds"] = time.monotonic() - then
        self.view["status"] = "ready"
        self.owner.save()
        append_event(self.owner.run, "worker_ready", worker=self.id)

    async def execute(self) -> None:
        then = time.monotonic()
        self.view["status"] = "dispatching"
        self.owner.save()
        try:
            reply = await self.command("prompt", message=self.spec["prompt"])
            self.view["timings"]["accept_seconds"] = time.monotonic() - then
            if reply.get("disposition") != "started":
                raise TeamError("prompt_not_started")
            self.view["status"] = "running"
            self.owner.save()
            await self.settled.wait()
            if self.protocol_error:
                raise TeamError("rpc_protocol_error")
            if "settled" not in self.view:
                raise TeamError("exited_before_settled")
            if self.view["settled"]["aborted"]:
                raise TeamError("agent_aborted")
            if self.last_assistant is None:
                raise TeamError("settled_without_assistant_evidence")
            reason = self.last_assistant.get("stopReason")
            self.view["stop_reason"] = reason
            if reason != "stop":
                raise TeamError(
                    "assistant_" + reason
                    if reason in {"error", "aborted", "length", "toolUse"}
                    else "assistant_unknown_stop"
                )
            self.view["status"] = "succeeded"
        except Exception as error:
            self.view["status"] = "failed"
            self.view["error"] = (
                str(error) if isinstance(error, TeamError) else type(error).__name__
            )
        finally:
            self.view["timings"]["execution_seconds"] = time.monotonic() - then
            if self.last_assistant:
                write_json(self.base.with_suffix(".result.json"), self.last_assistant)
            self.owner.save()

    async def close(self) -> None:
        if self.process is None:
            return
        then = time.monotonic()
        grace = self.owner.spec["shutdown_grace_seconds"]
        process = self.process
        identity = self.view.get("identity")
        token = self.view["ownership_token"]
        members = group_members(identity, owner_token=token)
        if process.returncode is None and process.stdin:
            with contextlib.suppress(BrokenPipeError, ConnectionResetError, TimeoutError):
                process.stdin.write(
                    json.dumps({"id": uuid.uuid4().hex, "type": "abort"}).encode() + b"\n"
                )
                await asyncio.wait_for(process.stdin.drain(), grace)
            process.stdin.close()
        try:
            await asyncio.wait_for(process.wait(), grace)
            shutdown = "graceful"
        except TimeoutError:
            signal_owned(self.view.get("identity"), signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), grace)
                shutdown = "terminated"
            except TimeoutError:
                signal_owned(self.view.get("identity"), signal.SIGKILL)
                try:
                    await asyncio.wait_for(process.wait(), grace)
                    shutdown = "killed"
                except TimeoutError:
                    shutdown = "unconfirmed"
        # A leader can exit gracefully while tool descendants retain the group.
        remaining = group_members(identity, members, token)
        if remaining:
            signal_owned(identity, signal.SIGTERM, remaining)
            await asyncio.sleep(grace)
            signal_owned(identity, signal.SIGKILL, remaining)
            await asyncio.sleep(0.05)
            if group_members(identity, remaining):
                shutdown = "unconfirmed"
            elif shutdown == "graceful":
                shutdown = "descendants_terminated"
        self.view["shutdown"] = shutdown
        self.view["exit_code"] = process.returncode
        self.view["timings"]["shutdown_seconds"] = time.monotonic() - then
        # Descendants holding pipes open must not make shutdown unbounded.
        try:
            await asyncio.wait_for(asyncio.gather(*self.readers, return_exceptions=True), grace)
        except TimeoutError:
            for task in self.readers:
                task.cancel()
            self.view["shutdown"] = "unconfirmed"
        self.owner.save()


class Supervisor:
    def __init__(self, run: Path):
        self.run = run
        self.spec = validate_spec(read_json(run / "spec.json"))
        self.state = read_json(run / "state.json")
        self.workers = [Worker(self, spec) for spec in self.spec["workers"]]

    def save(self) -> None:
        write_json(self.run / "state.json", self.state)

    async def run_workers(self) -> None:
        then = time.monotonic()
        readiness = await asyncio.gather(*(w.start() for w in self.workers), return_exceptions=True)
        self.state["timings"]["startup_seconds"] = time.monotonic() - then
        failures = [
            (worker, error)
            for worker, error in zip(self.workers, readiness, strict=True)
            if isinstance(error, BaseException)
        ]
        if failures:
            for worker, error in failures:
                worker.view["status"] = "failed"
                worker.view["error"] = (
                    str(error) if isinstance(error, TeamError) else type(error).__name__
                )
            raise TeamError("startup_failed")
        if self.state.get("watchdog") and not identity_alive(self.state["watchdog"]):
            raise TeamError("watchdog_unavailable")
        self.state["status"] = "running"
        self.save()
        append_event(self.run, "dispatch_started")
        await asyncio.gather(*(worker.execute() for worker in self.workers))
        self.state["status"] = (
            "succeeded" if all(w.view["status"] == "succeeded" for w in self.workers) else "failed"
        )


async def supervise(run: Path, transport_factory=None) -> None:
    """Own all workers until shutdown; injectable callback adapter for offline tests."""
    owner = Supervisor(run)
    state, spec = owner.state, owner.spec
    state["supervisor"] = process_identity(os.getpid())
    owner.save()
    callback = None
    started = time.monotonic()
    deadline = state.get("deadline_monotonic", started + max(0, state["deadline_at"] - time.time()))
    task = None
    interrupted = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, interrupted.set)

    async def active_work() -> None:
        nonlocal callback
        if state.get("watchdog"):
            async with asyncio.timeout(spec["startup_timeout_seconds"]):
                while not (run / "watchdog-ready.json").exists():
                    if not identity_alive(state["watchdog"]):
                        raise TeamError("watchdog_unavailable")
                    await asyncio.sleep(0.05)
                if read_json(run / "watchdog-ready.json") != state["watchdog"]:
                    raise TeamError("watchdog_identity_mismatch")
        factory = transport_factory or Callback.connect
        connecting = time.monotonic()
        state["callback"] = {"probe": "connecting", "notification": "pending"}
        owner.save()
        try:
            callback = await asyncio.wait_for(
                factory(spec["callback"]), spec["callback"]["timeout_seconds"]
            )
        except Exception as error:
            state["callback"].update(probe="connect_failed", error=type(error).__name__)
            raise TeamError("callback_connect_failed") from error
        finally:
            state["timings"]["callback_connect_seconds"] = time.monotonic() - connecting
            owner.save()
        probing = time.monotonic()
        state["callback"]["probe"] = "awaiting_ack"
        owner.save()
        try:
            await asyncio.wait_for(callback.probe(run), spec["callback"]["timeout_seconds"] * 2)
        except Exception as error:
            state["callback"].update(probe="ack_failed", error=type(error).__name__)
            raise TeamError("callback_probe_failed") from error
        finally:
            state["timings"]["callback_probe_ack_seconds"] = time.monotonic() - probing
            owner.save()
        state["callback"]["probe"] = "acknowledged"
        state["timings"]["callback_seconds"] = time.monotonic() - started
        owner.save()
        append_event(run, "callback_verified")
        await owner.run_workers()

    try:
        task = asyncio.create_task(active_work())
        while not task.done():
            if state.get("watchdog") and not identity_alive(state["watchdog"]):
                raise TeamError("watchdog_unavailable")
            if time.monotonic() >= deadline:
                raise TeamError("deadline_exceeded")
            if interrupted.is_set() or (run / "stop-request.json").exists():
                raise TeamError("stop_requested")
            await asyncio.wait({task}, timeout=0.2)
        await task
    except BaseException as error:
        code = str(error) if isinstance(error, TeamError) else type(error).__name__
        state["error"] = code
        state["status"] = {"stop_requested": "stopped", "deadline_exceeded": "timed_out"}.get(
            code, "failed"
        )
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    finally:
        outcome = state["status"]
        state["status"] = "stopping"
        owner.save()
        await asyncio.gather(*(worker.close() for worker in owner.workers))
        state["status"] = outcome
        for worker in owner.workers:
            if worker.view["status"] not in TERMINAL:
                worker.view["status"] = outcome if outcome != "succeeded" else "failed"
        if any(w.view.get("shutdown") == "unconfirmed" for w in owner.workers):
            state["status"] = "failed"
            state["shutdown"] = "unconfirmed"
        else:
            state["shutdown"] = "confirmed"
        state["timings"]["total_seconds"] = time.monotonic() - started
        state["finished_at"] = time.time()
        owner.save()
        if callback:
            state.setdefault("callback", {})["notification"] = "attempting"
            owner.save()  # At-most-once: watchdog never resends an ambiguous supervisor send.
            try:
                await callback.send(
                    {
                        "version": 1,
                        "type": "pi_team_result",
                        "run_dir": str(run),
                        "run_id": state["run_id"],
                        "status": state["status"],
                    }
                )
                state["callback"]["notification"] = "relay_accepted"
            except Exception as error:
                state["callback"]["notification"] = "uncertain"
                state["callback"]["error"] = type(error).__name__
            with contextlib.suppress(Exception):
                await callback.close()
        owner.save()
        append_event(run, "finished", status=state["status"])
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)


async def watchdog(run: Path) -> None:
    """Independent bounded fallback; writes overlay, never races supervisor state writes."""
    initial = read_json(run / "state.json")
    spec = read_json(run / "spec.json")
    write_json(run / "watchdog-ready.json", process_identity(os.getpid()))
    deadline = initial.get(
        "deadline_monotonic", time.monotonic() + max(0, initial["deadline_at"] - time.time())
    )
    shutdown_budget = spec["shutdown_grace_seconds"] * 6 + 2
    until = deadline + shutdown_budget + spec["shutdown_grace_seconds"] + 2
    stop_seen = None
    reason = None
    while time.monotonic() < until:
        state = read_json(run / "state.json")
        if state.get("supervisor") and not identity_alive(state["supervisor"]):
            if (
                state["status"] in TERMINAL
                and state.get("shutdown") == "confirmed"
                and state.get("callback", {}).get("notification")
                in {"attempting", "relay_accepted", "uncertain"}
            ):
                write_json(run / "watchdog.json", {"status": "complete", "time": time.time()})
                return
            reason = "supervisor_died"
            break
        now = time.monotonic()
        stop_path = run / "stop-request.json"
        if stop_path.exists() and stop_seen is None:
            stop_seen = now
        if now >= deadline and not stop_path.exists():
            write_json(stop_path, {"reason": "deadline_exceeded"})
        cutoff = min(deadline, stop_seen) if stop_seen is not None else deadline
        # Covers a responsive owner, a suspended owner, and explicit stop requests.
        if now >= cutoff + shutdown_budget:
            reason = "deadline_exceeded" if cutoff == deadline else "stop_requested"
            break
        await asyncio.sleep(min(0.2, max(0.01, until - time.monotonic())))
    state = read_json(run / "state.json")
    reason = reason or "watchdog_bound_exhausted"
    # Grace has already expired. Stop the spawner before taking the final lease
    # snapshot; otherwise a resumed owner could birth a worker during cleanup.
    signal_owned(state.get("supervisor"), signal.SIGKILL)
    await asyncio.sleep(0.1)
    state = read_json(run / "state.json")
    leases = [
        {"identity": w.get("identity"), "ownership_token": w.get("ownership_token")}
        for w in state["workers"].values()
    ]
    # Exec launchers publish independently, closing the spawn-before-owner-save gap.
    leases.extend(read_json(path) for path in (run / "workers").glob("*.lease.json"))
    identities = [lease["identity"] for lease in leases]
    snapshots = [
        group_members(lease["identity"], owner_token=lease.get("ownership_token"))
        for lease in leases
    ]
    for identity, members in zip(identities, snapshots, strict=True):
        signal_owned(identity, signal.SIGTERM, members)
    await asyncio.sleep(spec["shutdown_grace_seconds"])
    for identity, members in zip(identities, snapshots, strict=True):
        signal_owned(identity, signal.SIGKILL, members)
    await asyncio.sleep(0.1)
    evidence = {
        "status": "triggered",
        "reason": reason,
        "time": time.time(),
        "shutdown": "unconfirmed"
        if any(group_members(i, members) for i, members in zip(identities, snapshots, strict=True))
        else "confirmed",
        "notification": "not_attempted",
    }
    write_json(run / "watchdog.json", evidence)
    if state.get("callback", {}).get("notification") not in {
        "attempting",
        "relay_accepted",
        "uncertain",
    }:
        evidence["notification"] = "attempting"
        write_json(run / "watchdog.json", evidence)
        callback = None
        try:
            config = {**spec["callback"], "name": "pt-watchdog-" + uuid.uuid4().hex[:20]}
            callback = await Callback.connect(config)
            await callback.send(
                {
                    "version": 1,
                    "type": "pi_team_result",
                    "run_dir": str(run),
                    "run_id": state["run_id"],
                    "status": "failed",
                    "reason": reason,
                }
            )
            evidence["notification"] = "relay_accepted"
        except Exception as error:
            evidence["notification"] = "uncertain"
            evidence["error"] = type(error).__name__
        finally:
            if callback:
                with contextlib.suppress(Exception):
                    await callback.close()
            write_json(run / "watchdog.json", evidence)


def start(spec_path: Path) -> dict:
    spec = validate_spec(read_json(spec_path))
    if not Path("/proc/sys/kernel/random/boot_id").is_file():
        raise TeamError("linux_proc_required")
    if importlib.util.find_spec("nodalwire") is None:
        raise TeamError("missing_nodalwire_use_explicitly_prepared_python_environment")
    if shutil.which(spec["pi_command"][0]) is None:
        raise TeamError("pi_executable_not_found")
    run = Path(spec["run_dir"])
    run.mkdir(mode=0o700, parents=True, exist_ok=False)
    (run / "workers").mkdir(mode=0o700)
    now = time.time()
    state = {
        "version": 1,
        "run_id": uuid.uuid4().hex,
        "run_dir": str(run),
        "status": "starting",
        "created_at": now,
        "deadline_at": now + spec["deadline_seconds"],
        "deadline_monotonic": time.monotonic() + spec["deadline_seconds"],
        "timings": {},
        "workers": {
            w["id"]: {"id": w["id"], "status": "pending", "timings": {}} for w in spec["workers"]
        },
    }
    write_json(run / "spec.json", spec)
    write_json(run / "state.json", state)
    # Gate ensures watchdog exists before the supervisor can spawn a worker.
    processes = []
    try:
        for mode in ("_supervise", "_watchdog"):
            with private_log(run / (mode[1:] + ".log")) as log:
                process = subprocess.Popen(
                    [sys.executable, str(SCRIPT), mode, "--run", str(run)],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                    close_fds=True,
                )
                processes.append(process)
                state["supervisor" if mode == "_supervise" else "watchdog"] = process_identity(
                    process.pid
                )
        write_json(run / "state.json", state)
        write_json(run / "launch-ready.json", {"ready": True})
    except BaseException:
        for process in processes:
            signal_owned(process_identity(process.pid), signal.SIGTERM)
        state.update(status="failed", error="supervisor_launch_failed")
        write_json(run / "state.json", state)
        raise
    return compact_state(state)


def exec_worker(run: Path, worker_id: str, session_id: str) -> None:
    """Publish birth identity before exec; no model can run without an owned lease."""
    spec = read_json(run / "spec.json")
    state = read_json(run / "state.json")
    worker = next(w for w in spec["workers"] if w["id"] == worker_id)
    write_json(
        run / "workers" / (worker_id + ".lease.json"),
        {
            "identity": process_identity(os.getpid()),
            "ownership_token": os.environ.get("PI_TEAM_OWNER_TOKEN"),
        },
    )
    if not identity_alive(state.get("supervisor")):
        raise TeamError("owner_died_before_worker_exec")
    command = [
        *spec["pi_command"],
        "--mode",
        "rpc",
        "--provider",
        worker["provider"],
        "--model",
        worker["model"],
        "--thinking",
        worker["thinking"],
        "--session-dir",
        str(run / "sessions" / worker_id),
        "--session-id",
        session_id,
        "--no-approve",
        "--offline",
    ]
    os.execvpe(command[0], command, os.environ)


def status(run: Path) -> dict:
    state = read_json(run / "state.json")
    state["supervisor_alive"] = identity_alive(state.get("supervisor"))
    if (run / "watchdog.json").exists():
        evidence = read_json(run / "watchdog.json")
        if evidence.get("status") == "triggered":
            state.update(status="failed", error=evidence["reason"], shutdown=evidence["shutdown"])
        state["watchdog"] = {**(state.get("watchdog") or {}), "evidence": evidence}
    return compact_state(state)


async def await_launch(run: Path) -> None:
    until = time.monotonic() + 10
    while not (run / "launch-ready.json").exists():
        if time.monotonic() >= until:
            raise TeamError("launcher_died_before_ready")
        await asyncio.sleep(0.05)


def main(argv: list[str] | None = None) -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("start", help="Start an explicitly specified bounded team").add_argument(
        "--spec", type=Path, required=True
    )
    for name in ("status", "watch", "results", "stop", "_supervise", "_watchdog", "_worker"):
        command = commands.add_parser(
            name, help=argparse.SUPPRESS if name.startswith("_") else name
        )
        command.add_argument("--run", type=Path, required=True)
        if name == "_worker":
            command.add_argument("--worker", required=True)
            command.add_argument("--session-id", required=True)
        if name == "results":
            command.add_argument(
                "--full", action="store_true", help="Include private result content"
            )
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            result = start(args.spec)
        elif args.command == "_worker":
            exec_worker(args.run, args.worker, args.session_id)
            return 0
        elif args.command in {"_supervise", "_watchdog"}:

            async def internal():
                await await_launch(args.run)
                await (supervise(args.run) if args.command == "_supervise" else watchdog(args.run))

            asyncio.run(internal())
            return 0
        elif args.command == "watch":
            previous = None
            while True:
                current = status(args.run)
                encoded = json.dumps(current, sort_keys=True)
                if encoded != previous:
                    print(encoded, flush=True)
                    previous = encoded
                if current["status"] in TERMINAL:
                    return 0
                time.sleep(0.5)
        else:
            result = status(args.run)
            if args.command == "stop":
                if result["status"] not in TERMINAL:
                    write_json(
                        args.run / "stop-request.json",
                        {"reason": "user_requested", "time": time.time()},
                    )
                result["stop_requested"] = (args.run / "stop-request.json").exists()
            elif args.command == "results" and args.full:
                result["private_artifact_dir"] = str(args.run.resolve())
                result["results"] = {
                    path.name: read_json(path)
                    for path in (args.run / "workers").glob("*.result.json")
                }
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except KeyboardInterrupt:
        return 130
    except (TeamError, OSError, ValueError) as error:
        code = str(error) if isinstance(error, TeamError) else type(error).__name__
        print(json.dumps({"error": code}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
