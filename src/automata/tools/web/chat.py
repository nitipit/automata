"""One immutable native Pi session and its chat-side state."""

from __future__ import annotations

import asyncio
import contextlib
import json
import secrets
from pathlib import Path

from automata.tools.web.connector import BrowserConnector
from automata.tools.web.model_controls import (
    CONTROLS_UNAVAILABLE,
    SCOPE_EXTENSION,
    SCOPE_KEY_ENV,
    available_thinking,
    effective_thinking,
    model_key,
    model_summary,
    scope_from_status,
)
from automata.tools.web.rpc import PiRpc, RpcError, RpcRejected
from automata.tools.web.sessions import (
    PAGE_SIZE,
    SessionClaim,
    SessionRow,
    list_rows,
    read_preview,
    read_row,
)

DIALOGS = {"select", "confirm", "input", "editor"}


class ChatSession:
    def __init__(self, *, rpc=None, rpc_factory=PiRpc, on_exit=None, unavailable=None):
        self.rpc = rpc if rpc is not None else rpc_factory(self.on_event)
        self.connector = BrowserConnector()
        self.connector_token = secrets.token_urlsafe(32)
        self.admission = secrets.token_urlsafe(32)
        self.messages: list[dict] = []
        self._startup_messages: list[dict] | None = None
        self.state: dict = {"status": "idle"}
        self._scope_key = "automata.web.scope." + secrets.token_urlsafe(24)
        self._model_scope: dict | None = None
        self.dialogs: dict[str, dict] = {}
        self._dialog_timers: dict[str, asyncio.TimerHandle] = {}
        self._chat = None
        self._outbox: asyncio.Queue | None = None
        self._seen: set[str] = set()
        self._tasks: set[asyncio.Task] = set()
        self._commands: set[asyncio.Task] = set()
        self._control = asyncio.Lock()
        self._stop_lock = asyncio.Lock()
        self._project: Path | None = None
        self._session_path: Path | None = None
        self._claim: SessionClaim | None = None
        self._caller_session: Path | None = None
        self._listing: tuple[str, dict[str, SessionRow]] | None = None
        self._on_exit = on_exit
        self._unavailable = unavailable or (lambda row: None)
        self._closed = False
        self._dead = False
        self._close_task: asyncio.Task | None = None
        self._slow_close_requested = False

    @property
    def id(self):
        return self.state.get("sessionId")

    async def start(self, launch, *, origin, project, caller, route_id, target=None):
        self._project, self._caller_session = project, caller
        if target is not None:
            self._claim = SessionClaim(target.path)
            if not target.unchanged() or self._is_caller(target.path):
                raise ValueError("Session changed or is unavailable; reopen Sessions")
        self._startup_messages = []
        await self.rpc.start(
            (*launch.argv, "-e", str(SCOPE_EXTENSION)),
            cwd=launch.cwd,
            env={
                SCOPE_KEY_ENV: self._scope_key,
                "AUTOMATA_WEB_CONNECTOR_URL": origin + "/connector",
                "AUTOMATA_WEB_CONNECTOR_TOKEN": self.connector_token,
            },
        )
        native = await self.read_native(timeout=15)
        native_id, path = native.get("sessionId"), self.native_path(native)
        if not route_id(native_id) or path is None or self._is_caller(path):
            raise RpcError("Pi did not return a valid persistent native session identity")
        if target and (target.id != native_id or target.path != path):
            raise RpcError("Pi opened an unexpected session")
        if self._claim is None:
            self._claim = SessionClaim(path)
            if path.exists():
                row = await asyncio.to_thread(read_row, path, project)
                if row is None or row.id != native_id:
                    raise RpcError("Native session header does not match its project or ID")
        history = await self.rpc.command("get_messages", timeout=15)
        confirmed = await self.read_native(timeout=10)
        if (
            confirmed.get("sessionId") != native_id
            or self.native_path(confirmed) != path
            or self._dead
        ):
            raise RpcError("Native session changed or exited during startup")
        self._session_path = path
        self.state.update({key: confirmed.get(key) for key in ("sessionId", "sessionName")})
        self.state["status"] = (
            "running"
            if any(
                confirmed.get(key) for key in ("isStreaming", "isCompacting", "pendingMessageCount")
            )
            else "idle"
        )
        await self._refresh_controls(confirmed)
        self._hydrate_messages(history)
        return self

    @staticmethod
    def native_path(native):
        path = native.get("sessionFile")
        if not isinstance(path, str) or not path or "\0" in path:
            return None
        candidate = Path(path)
        if not candidate.is_absolute() or candidate.suffix != ".jsonl" or candidate.is_symlink():
            return None
        return candidate.resolve()

    async def read_native(self, *, timeout=15):
        state = await self.rpc.command("get_state", timeout=timeout)
        if not isinstance(state, dict):
            raise RpcError("Pi returned invalid session state")
        return state

    def matches_native(self, native):
        return native.get("sessionId") == self.id and self.native_path(native) == self._session_path

    async def _verify_bound_identity(self):
        if self._session_path is not None and not self.matches_native(await self.read_native()):
            self.invalidate()
            raise RpcError("Native session identity changed; chat retired")

    async def _control_native(self):
        native = await self.read_native()
        if not self.matches_native(native):
            self.invalidate()
            raise RpcError("Native session identity changed; chat retired")
        return native

    async def _native_controls(self, native):
        model = model_summary(native.get("model"))
        level = effective_thinking(native.get("thinkingLevel"))
        levels = []
        if self._model_scope is not None and model is not None and level is not None:
            data = await self.rpc.command("get_available_thinking_levels", timeout=5)
            levels = available_thinking(data, level)
        return {"model": model, "thinkingLevel": level, "thinkingLevels": levels}

    def _store_controls(self, controls):
        self.state.update(controls)
        self.state["modelChoices"] = [model for model, _ in (self._model_scope or {}).values()]
        if self._model_scope is None:
            self.state["controlsError"] = CONTROLS_UNAVAILABLE
        else:
            # Thinking availability is independent of a valid pinned-model catalog.
            self.state.pop("controlsError", None)

    async def _refresh_controls(self, native):
        try:
            controls = await self._native_controls(native)
        except (RpcError, TimeoutError):
            controls = {
                "model": model_summary(native.get("model")),
                "thinkingLevel": effective_thinking(native.get("thinkingLevel")),
                "thinkingLevels": [],
            }
        self._store_controls(controls)
        return controls

    def _require_idle_control(self, native=None):
        if (
            self._closed
            or self._dead
            or self.state["status"] != "idle"
            or (
                native is not None
                and any(
                    native.get(key)
                    for key in ("isStreaming", "isCompacting", "pendingMessageCount")
                )
            )
        ):
            raise ValueError("Agent is busy; wait before changing model or thinking")

    async def _change_control(self, kind, record):
        async with self._control:
            self._require_idle_control()
            if self._model_scope is None:
                raise ValueError(CONTROLS_UNAVAILABLE)
            native = await self._control_native()
            current = await self._refresh_controls(native)
            self._require_idle_control(native)
            if kind == "set_model":
                provider, model_id = record.get("provider"), record.get("modelId")
                if not isinstance(provider, str) or not isinstance(model_id, str):
                    raise ValueError("Select a pinned model")
                target = self._model_scope.get((provider, model_id))
                if target is None:
                    raise ValueError("Model is not in this chat's pinned selection")
                if current["model"] and (provider, model_id) == model_key(current["model"]):
                    self._status(self.state["status"])
                    return current
                payload = {"provider": provider, "modelId": model_id}
            else:
                level = effective_thinking(record.get("level"))
                if level not in current["thinkingLevels"]:
                    raise ValueError("Thinking level is not supported by the current model")
                payload = {"level": level}
            try:
                await self.rpc.command(kind, timeout=5, **payload)
                updated = await self._refresh_controls(await self._control_native())
                actual = updated["model"]
                if kind == "set_model" and actual and model_key(actual) == (provider, model_id):
                    # Native set_model selects its effective configured default. Preserve the
                    # previous level when supported, else honor an explicit scoped level if valid.
                    levels = updated["thinkingLevels"]
                    previous, hint = current["thinkingLevel"], target[1]
                    desired = previous if previous in levels else hint if hint in levels else None
                    if desired is not None and desired != updated["thinkingLevel"]:
                        readback = await self._control_native()
                        self._require_idle_control(readback)
                        actual = model_summary(readback.get("model"))
                        if actual is None or model_key(actual) != (provider, model_id):
                            raise ValueError("Native model changed during the request")
                        await self.rpc.command("set_thinking_level", timeout=5, level=desired)
                        updated = await self._refresh_controls(await self._control_native())
            except (RpcRejected, ValueError):
                # Native refusal or Stop racing a follow-up: report read-back, not the request.
                await self._refresh_controls(await self._control_native())
                self._status(self.state["status"])
                raise ValueError("Pi did not complete the model or thinking change") from None
            except (RpcError, TimeoutError, asyncio.CancelledError):
                # A late mutation could otherwise land during a subsequent prompt.
                self.invalidate()
                await self.rpc.close()
                raise
            self._status(self.state["status"])
            if kind == "set_model" and (
                not updated["model"] or model_key(updated["model"]) != (provider, model_id)
            ):
                raise ValueError("Pi did not select the requested model")
            if kind == "set_thinking_level" and (
                level not in updated["thinkingLevels"] or updated["thinkingLevel"] != level
            ):
                raise ValueError("Pi did not select the requested thinking level")
            return updated

    def _hydrate_messages(self, history):
        messages = history.get("messages") if isinstance(history, dict) else None
        if not isinstance(messages, list) or any(
            not isinstance(message, dict) for message in messages
        ):
            raise RpcError("Pi returned an invalid message snapshot")
        buffered = self._startup_messages or []
        boundary = next(
            (i for i in range(len(buffered) - 1, -1, -1) if buffered[i] in messages), -1
        )
        self.messages = [*messages, *buffered[boundary + 1 :]]
        self._startup_messages = None

    def _snapshot(self):
        return {
            "type": "snapshot",
            "messages": list(self.messages),
            "state": dict(self.state),
            "dialogs": list(self.dialogs.values()),
        }

    def _is_caller(self, path):
        return self._caller_session is not None and path == self._caller_session

    async def _list_sessions(self, offset):
        if type(offset) is not int or offset < 0 or offset % PAGE_SIZE:
            raise ValueError("Invalid Sessions page")
        current_path, current_id = self._session_path, self.id
        self._listing = None
        current = {"id": current_id, "current": True} if current_id else None
        if current_path is None or self._project is None:
            return {"current": current, "sessions": [], "persistent": False}
        try:
            rows, counts = await asyncio.to_thread(list_rows, current_path.parent, self._project)
        except OSError as error:
            raise RpcError("Could not list the project session store") from error

        def summary(row, reason=None):
            return {
                "id": row.id,
                "label": row.label,
                "snippet": row.snippet,
                "modified": row.modified,
                "unavailable": reason,
            }

        current_row = next((row for row in rows if row.path == current_path), None)
        rows = [row for row in rows if row.path != current_path]
        choices, summaries = {}, []
        if current_row and current_row.id == current_id:
            current = {**summary(current_row), "current": True}
            if counts[current_row.id] == 1:
                choices[current_row.id] = current_row  # Read-only preview of current history.
        for row in rows[offset : offset + PAGE_SIZE]:
            reason = None
            if counts[row.id] != 1 or row.id == current_id:
                reason = "Duplicate session ID"
            elif self._is_caller(row.path):
                reason = "Open in the calling Pi session"
            else:
                reason = self._unavailable(row)
            if reason is None:
                choices[row.id] = row
            summaries.append(summary(row, reason))
        receipt = secrets.token_urlsafe(24)
        self._listing = (receipt, choices)
        return {
            "current": current,
            "sessions": summaries,
            "receipt": receipt,
            "persistent": True,
            "nextOffset": offset + PAGE_SIZE if offset + PAGE_SIZE < len(rows) else None,
            "previousOffset": offset - PAGE_SIZE if offset else None,
        }

    def listed_row(self, record, listing):
        target = record.get("sessionId")
        if isinstance(target, str) and listing and record.get("receipt") == listing[0]:
            return listing[1].get(target)
        return None

    async def _preview_session(self, record):
        listing = self._listing
        row = self.listed_row(record, listing)
        if row is None or record.get("fromSessionId") != self.id:
            raise ValueError("Session is not available in this listing. Reload Sessions.")
        preview = await asyncio.to_thread(read_preview, row)
        if listing is not self._listing:
            raise ValueError("Listing changed. Reload Sessions.")
        return preview

    def _spawn(self, coro):
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def _publish(self, record):
        if self._outbox is None:
            return
        try:
            self._outbox.put_nowait(record)
        except asyncio.QueueFull:
            if self._chat and not self._slow_close_requested:
                self._slow_close_requested = True
                self._spawn(self._close_slow_chat(self._chat))

    async def _close_slow_chat(self, socket):
        from starlette.websockets import WebSocketDisconnect

        with contextlib.suppress(TimeoutError, RuntimeError, OSError, WebSocketDisconnect):
            async with asyncio.timeout(1):
                await socket.close(code=1013)

    def _status(self, status):
        self.state["status"] = status
        self._publish({"type": "host_status", **self.state})

    def invalidate(self):
        if self._dead or self._closed:
            return
        self._dead = True
        self._status("error")
        self.connector.bind(None)
        if self._on_exit:
            self._on_exit(self)

    def on_event(self, event):
        if self._closed or self._dead:
            return
        kind = event.get("type")
        if (
            kind == "extension_ui_request"
            and event.get("method") == "setStatus"
            and event.get("statusKey") == self._scope_key
        ):
            if self._startup_messages is not None:
                self._model_scope = scope_from_status(event.get("statusText"))
            return
        if kind == "message_end":
            target = self.messages if self._startup_messages is None else self._startup_messages
            target.append(event["message"])
        elif kind == "session_info_changed":
            self.state["sessionName"] = event.get("name")
        elif kind == "agent_start":
            if self.state["status"] not in {"stopping", "error"}:
                self._status("running")
        elif kind == "agent_settled":
            if self.state["status"] not in {"stopping", "error"}:
                self._status("idle")
        elif kind == "host_rpc_exit":
            self.invalidate()
            return
        elif kind == "extension_ui_request" and event.get("method") in DIALOGS:
            key = event.get("id")
            if isinstance(key, str):
                self.dialogs[key] = event
                timeout = event.get("timeout", 120000)
                if type(timeout) not in (int, float) or not 0 < timeout <= 120000:
                    timeout = 120000
                self._dialog_timers[key] = asyncio.get_running_loop().call_later(
                    timeout / 1000, lambda: self._spawn(self._cancel_dialog(key))
                )
                if (
                    self._chat is None
                    or self._outbox is None
                    or self.state["status"] in {"stopping", "error"}
                ):
                    self._spawn(self._cancel_dialog(key))
                    return
        self._publish({"type": "rpc_event", "event": event})

    def _consume_dialog(self, key):
        self.dialogs.pop(key, None)
        timer = self._dialog_timers.pop(key, None)
        if timer:
            timer.cancel()

    async def _cancel_dialog(self, key):
        if key not in self.dialogs:
            return
        self._consume_dialog(key)
        with contextlib.suppress(RpcError):
            await self.rpc.send({"type": "extension_ui_response", "id": key, "cancelled": True})
        self._publish({"type": "dialog_closed", "id": key})

    async def _dialog_response(self, record):
        key = record.get("id")
        dialog = self.dialogs.get(key) if isinstance(key, str) else None
        if dialog is None:
            raise ValueError("Dialog is expired or already answered")
        response = {"type": "extension_ui_response", "id": key}
        if record.get("cancelled") is True:
            response["cancelled"] = True
        elif dialog["method"] == "confirm" and type(record.get("confirmed")) is bool:
            response["confirmed"] = record["confirmed"]
        elif dialog["method"] in {"input", "editor", "select"}:
            value = record.get("value")
            if not isinstance(value, str) or len(value) > 65536:
                raise ValueError("Dialog requires a bounded string")
            if dialog["method"] == "select" and value not in dialog.get("options", []):
                raise ValueError("Invalid selection")
            response["value"] = value
        else:
            raise ValueError("Invalid dialog response")
        self._consume_dialog(key)
        await self.rpc.send(response)
        return {"answered": True}

    async def stop(self, *, timeout=10):
        try:
            async with asyncio.timeout(timeout):
                async with self._stop_lock:
                    if self._dead or self._closed:
                        raise RpcError("Pi is no longer available")
                    self._status("stopping")
                    self.connector.cancel_all()
                    for key in list(self.dialogs):
                        await self._cancel_dialog(key)
                    async with self._control:
                        cleared = await self.rpc.command("clear_queue")
                        await self.rpc.command("abort", timeout=timeout)
                        if not self._dead:
                            self._status("idle")
                        return cleared
        except (RpcError, TimeoutError) as error:
            self.invalidate()
            await self.rpc.close()
            raise RpcError("Stop could not be confirmed; owned Pi was shut down.") from error

    async def handle_command(self, record):
        key = record.get("id")
        try:
            if not isinstance(key, str) or not 1 <= len(key) <= 256:
                raise ValueError("Unique bounded command id required")
            if key in self._seen:
                raise ValueError("Duplicate command id; not replayed")
            if len(self._seen) >= 10000:
                raise ValueError("Command limit reached; start a new chat")
            self._seen.add(key)
            if self._closed or self._dead:
                raise RpcError("Pi is no longer available")
            kind = record.get("type")
            if (
                kind in {"prompt", "rename", "stop"}
                and "sessionId" in record
                and record["sessionId"] != self.id
            ):
                raise ValueError("Session changed; request was not sent")
            if kind in {"set_model", "set_thinking_level"}:
                if not self.id or record.get("sessionId") != self.id:
                    raise ValueError("Session changed; request was not sent")
                data = await self._change_control(kind, record)
            elif kind == "list_sessions":
                data = await self._list_sessions(record.get("offset", 0))
            elif kind == "preview_session":
                data = await self._preview_session(record)
            elif kind == "prompt":
                message = record.get("message")
                if not isinstance(message, str) or not message.strip() or len(message) > 65536:
                    raise ValueError("Nonempty bounded message required")
                async with self._control:
                    if self._closed or self._dead or self.state["status"] != "idle":
                        raise ValueError("Agent is busy; wait or Stop first")
                    await self._verify_bound_identity()
                    if self._closed or self._dead or self.state["status"] != "idle":
                        raise ValueError("Agent is busy; wait or Stop first")
                    self._status("running")
                    try:
                        data = await self.rpc.command("prompt", message=message)
                    except BaseException:
                        self._status("error")
                        raise
                    if (
                        data
                        and data.get("disposition") == "handled"
                        and self.state["status"] not in {"stopping", "error"}
                    ):
                        await self._verify_bound_identity()
                        self._status("idle")
            elif kind == "rename":
                name = record.get("name")
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("Session name cannot be empty")
                async with self._control:
                    if self._closed or self._dead:
                        raise RpcError("Pi is no longer available")
                    await self._verify_bound_identity()
                    await self.rpc.command("set_session_name", name=name.strip())
                    native = await self.read_native()
                    if self._session_path is not None and not self.matches_native(native):
                        self.invalidate()
                        raise RpcError("Native session identity changed; chat retired")
                    self.state["sessionName"] = native.get("sessionName")
                    data = {"sessionName": self.state["sessionName"]}
            elif kind == "stop":
                data = await self.stop()
            elif kind == "extension_ui_response":
                data = await self._dialog_response(record)
            else:
                raise ValueError("Unsupported browser command")
            self._publish({"type": "ack", "id": key, "success": True, "data": data})
        except (ValueError, RpcError, TimeoutError) as error:
            message = str(error) or (
                "RPC deadline exceeded; delivery outcome uncertain. Do not replay blindly."
                if isinstance(error, TimeoutError)
                else type(error).__name__
            )
            for token in (self.admission, self.connector_token):
                message = message.replace(token, "[redacted]")
            self._publish({"type": "ack", "id": key, "success": False, "error": message})

    async def serve_chat(self, socket, active, live):
        from starlette.websockets import WebSocketDisconnect

        self._chat = socket
        self._slow_close_requested = False
        outbox = self._outbox = asyncio.Queue(maxsize=256)
        writer = None
        try:
            await socket.accept()
            await socket.send_json(self._snapshot())
            active()

            async def write():
                try:
                    while True:
                        await socket.send_json(await outbox.get())
                except (RuntimeError, OSError, WebSocketDisconnect):
                    await self._close_slow_chat(socket)

            writer = asyncio.create_task(write())
            while live():
                text = await socket.receive_text()
                if not live():
                    break
                if len(text) > 100000 or len(self._commands) >= 32:
                    await socket.close(code=1008)
                    break
                record = json.loads(text)
                if not isinstance(record, dict):
                    raise ValueError("Expected command object")
                task = asyncio.create_task(self.handle_command(record))
                self._commands.add(task)
                task.add_done_callback(self._commands.discard)
        except (WebSocketDisconnect, ValueError, RuntimeError, OSError):
            pass
        finally:
            self._outbox = None
            if writer:
                writer.cancel()
                await asyncio.gather(writer, return_exceptions=True)

    def detach(self):
        self.connector.bind(None)
        self._outbox = None
        self._listing = None

    async def settle_commands(self):
        if self._commands:
            _, pending = await asyncio.wait(self._commands, timeout=1)
            if pending:
                for task in pending:
                    task.cancel()
                _, pending = await asyncio.wait(pending, timeout=1)
                if pending:
                    raise RpcError("Chat command cleanup unconfirmed")
        self._listing = None
        self._chat = None

    async def close(self):
        if self._close_task is None:
            self._closed = True
            self._close_task = asyncio.create_task(self._close())
        await asyncio.shield(self._close_task)

    async def _close(self):
        self.detach()
        for timer in self._dialog_timers.values():
            timer.cancel()
        self._dialog_timers.clear()
        self.dialogs.clear()
        try:
            if self._chat:
                with contextlib.suppress(Exception):
                    async with asyncio.timeout(1):
                        await self._chat.close(code=1001)
        finally:
            try:
                await self.rpc.close()
                if self._claim is not None:
                    self._claim.close()
                    self._claim = None
            finally:
                owned = self._tasks | self._commands
                for task in owned:
                    task.cancel()
                if owned:
                    _, unfinished = await asyncio.wait(owned, timeout=1)
                    if unfinished:
                        raise RpcError("Owned chat tasks did not stop; cleanup unconfirmed")
