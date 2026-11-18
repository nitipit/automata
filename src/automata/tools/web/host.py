"""Browser-first Pi application hosted on the existing WebRuntime FastAPI app."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import secrets
import signal
import sys
from pathlib import Path

from automata.tools.web.connector import BrowserConnector, ConnectorError
from automata.tools.web.launch import prepare_launch
from automata.tools.web.rpc import PiRpc, RpcError
from automata.tools.web.sessions import (
    PAGE_SIZE,
    SessionClaim,
    SessionRow,
    list_rows,
    read_preview,
    recorded_project,
)

PACKAGE = Path(__file__).resolve().parent
DIALOGS = {"select", "confirm", "input", "editor"}

# Keep browser selection in stdlib (including BROWSER), but outside the host loop.
# The private admission URL travels over stdin, never process arguments or output.
_BROWSER_OPEN = """import sys, webbrowser
try:
    opened = webbrowser.open(sys.stdin.read())
except BaseException:
    sys.exit(2)
sys.exit(0 if opened else 1)
"""


async def _open_browser(url: str):
    """Own/reap only the launcher helper, never terminate a user's browser tree."""
    process = None
    # Shield creation so cancellation cannot lose a just-created owned process.
    launching = asyncio.create_task(
        asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            _BROWSER_OPEN,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
    )
    try:
        process = await asyncio.shield(launching)
        await process.communicate(url.encode("utf-8"))
        if process.returncode:
            print("Browser auto-open failed (admission URL remains private).", file=sys.stderr)
    except OSError:
        # A configured command/exception may echo credentials. Never relay it.
        print("Browser auto-open failed (admission URL remains private).", file=sys.stderr)
    finally:
        if process is None:
            with contextlib.suppress(OSError):
                process = await launching
        if process is not None and process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 1)
            except TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                await process.wait()


class BrowserHost:
    """Own one runtime/server, one native RPC session and one browser chat client."""

    def __init__(self, *, port: int = 0, runtime=None, rpc=None):
        from automata_web_runtime import WebRuntime

        self.runtime = runtime or WebRuntime(port=port)
        self.rpc = rpc or PiRpc(self.on_event)
        self.connector = BrowserConnector()
        self.connector_token = secrets.token_urlsafe(32)
        self.messages: list[dict] = []
        self._startup_messages: list[dict] | None = None
        self.state: dict = {"status": "idle"}
        self.dialogs: dict[str, dict] = {}
        self._dialog_timers: dict[str, asyncio.TimerHandle] = {}
        self._chat = None
        self._outbox: asyncio.Queue | None = None
        self._seen: set[str] = set()
        self._tasks: set[asyncio.Task] = set()
        self._monitor: asyncio.Task | None = None
        self._control = asyncio.Lock()
        self._project: Path | None = None
        self._session_path: Path | None = None
        self._claim: SessionClaim | None = None
        self._caller_session = os.environ.get("PI_SESSION_FILE")
        self._listing: tuple[str, dict[str, SessionRow]] | None = None
        self._switching = False
        self._switch_failed = False
        self._closed = False
        self._close_task: asyncio.Task | None = None
        self._slow_close_requested = False
        self._install_routes()

    def _install_routes(self):
        from fastapi import Request, WebSocket
        from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        app = self.runtime.app
        # Replace GET / only, preserving upstream bridge and WebSocket routes.
        app.router.routes[:] = [
            route for route in app.router.routes if getattr(route, "path", None) != "/"
        ]
        templates = Environment(
            loader=FileSystemLoader(PACKAGE / "frontend"), autoescape=select_autoescape()
        )

        async def index(request: Request):
            if not self.runtime._local_request(request):
                return Response(status_code=403)
            return HTMLResponse(
                templates.get_template("index.html").render(),
                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
            )

        async def asset(name: str, request: Request):
            if not self.runtime._local_request(request):
                return Response(status_code=403)
            # Reviewed flat ESM graph only; never mount frontend/node_modules/repo.
            allowed = name in {
                "index.js",
                "ui.js",
                "connection-bootstrap.js",
                "adaptive.css",
                "adapter-LICENSE.txt",
                "third-party-LICENSES.txt",
            } or re.fullmatch(r"chunk-[A-Z0-9]{8}\.js", name)
            path = PACKAGE / "public" / name
            if not allowed or not path.is_file() or path.is_symlink():
                return Response(status_code=404)
            return FileResponse(path, headers={"Cache-Control": "no-store"})

        async def connector(operation: str, request: Request):
            expected = f"Bearer {self.connector_token}"
            if (
                not self.runtime._local_request(request)
                or request.headers.get("origin") is not None
                or not secrets.compare_digest(request.headers.get("authorization", ""), expected)
            ):
                return JSONResponse(
                    {
                        "ok": False,
                        "error": {"code": "forbidden", "message": "Connector access denied"},
                    },
                    status_code=403,
                )
            try:
                if len(await request.body()) > 300000:
                    raise ConnectorError("invalid_request", "Request is too large")
                body = await request.json()
                if not isinstance(body, dict):
                    raise ConnectorError("invalid_request", "JSON object required")
                if operation == "execute":
                    result = await self.connector.execute(body)
                elif operation == "subscribe":
                    result = self.connector.subscribe(body)
                elif operation == "wait":
                    result = await self.connector.wait(body)
                elif operation == "unsubscribe":
                    result = self.connector.unsubscribe(body)
                else:
                    raise ConnectorError("invalid_request", "Unknown connector operation")
                return JSONResponse(result)
            except (ValueError, UnicodeError):
                return JSONResponse(
                    {
                        "ok": False,
                        "error": {"code": "invalid_request", "message": "Invalid JSON object"},
                    },
                    status_code=400,
                )
            except ConnectorError as error:
                return JSONResponse(
                    {
                        "ok": False,
                        "error": {
                            "code": error.code,
                            "message": str(error),
                            "uncertain": error.uncertain,
                        },
                    }
                )

        async def connection(request: Request):
            # Read-only admission probe: distinguish invalid credentials from the
            # previous chat's reserved interrupt/command cleanup, before retrying.
            expected = f"Bearer {self.runtime.token}"
            if (
                not self.runtime._local_request(request)
                or request.headers.get("origin") != self.runtime.origin
                or not secrets.compare_digest(request.headers.get("authorization", ""), expected)
            ):
                return JSONResponse(
                    {"error": "Access credential rejected or expired"}, status_code=403
                )
            if self._closed:
                return JSONResponse({"error": "Host is closed"}, status_code=410)
            if self._chat is not None or self._startup_messages is not None:
                return JSONResponse(
                    {"error": "Previous connection is still stopping"}, status_code=409
                )
            return JSONResponse({"ready": True}, headers={"Cache-Control": "no-store"})

        async def chat(socket: WebSocket):
            await self._chat_socket(socket)

        # These imports are local to keep non-web CLI paths optional-dependency free.
        # FastAPI resolves annotations in globals; assign concrete runtime types.
        index.__annotations__["request"] = Request
        asset.__annotations__["request"] = Request
        connector.__annotations__["request"] = Request
        connection.__annotations__["request"] = Request
        chat.__annotations__["socket"] = WebSocket
        app.add_api_route("/", index, methods=["GET"])
        app.add_api_route("/assets/{name}", asset, methods=["GET"])
        app.add_api_route("/connector/{operation}", connector, methods=["POST"])
        app.add_api_route("/chat/connection", connection, methods=["POST"])
        app.add_api_websocket_route("/chat", chat)

    async def start(
        self,
        *,
        pi: str = "pi",
        cwd: Path | None = None,
        provider: str | None = None,
        model: str | None = None,
        thinking: str | None = None,
        session: Path | None = None,
        session_inactive: bool = False,
        extra_args: tuple[str, ...] = (),
    ):
        try:
            extension = (
                PACKAGE.parents[1] / "runtimes" / "pi" / "extensions" / "web-ui" / "index.ts"
            )
            launch = prepare_launch(
                pi=pi,
                extension=extension,
                cwd=cwd,
                provider=provider,
                model=model,
                thinking=thinking,
                session=session,
                session_inactive=session_inactive,
                extra_args=extra_args,
            )
            self._project = launch.cwd
            if session is not None:
                selected = Path(launch.argv[launch.argv.index("--session") + 1])
                # Explicit resume uses the recorded directory, not the launch directory.
                self._project = recorded_project(selected)
                self._claim = SessionClaim(selected)
            self._startup_messages = []
            await self.runtime.start()
            await self.rpc.start(
                launch.argv,
                cwd=launch.cwd,
                env={
                    "AUTOMATA_WEB_CONNECTOR_URL": self.runtime.origin + "/connector",
                    "AUTOMATA_WEB_CONNECTOR_TOKEN": self.connector_token,
                },
            )
            state = await self._read_native_state(timeout=30)
            path = self._native_path(state)
            if self._claim and self._claim.path != path:
                raise RpcError("Pi opened an unexpected session")
            if path is not None and self._claim is None:
                self._claim = SessionClaim(path)
                if path.is_file():
                    self._project = recorded_project(path)
            self._session_path = path
            self._update_session(state)
            history = await self.rpc.command("get_messages", timeout=30)
            self._hydrate_messages(history)
            self._monitor = asyncio.create_task(self._monitor_browser())
            return self
        except BaseException:
            await self.close()
            raise

    @staticmethod
    def _native_path(native: dict) -> Path | None:
        path = native.get("sessionFile")
        return Path(path).resolve() if isinstance(path, str) and path else None

    def _update_session(self, native: dict):
        self.state.update(
            {key: native.get(key) for key in ("sessionId", "sessionName", "model", "thinkingLevel")}
        )

    def _snapshot(self):
        return {
            "type": "snapshot",
            "messages": list(self.messages),
            "state": dict(self.state),
            "dialogs": list(self.dialogs.values()),
        }

    def _is_caller(self, path: Path) -> bool:
        return bool(
            self._caller_session and path == Path(self._caller_session).expanduser().resolve()
        )

    async def _list_sessions(self, offset):
        if type(offset) is not int or offset < 0 or offset % PAGE_SIZE:
            raise ValueError("Invalid Sessions page")
        current_path, current_id = self._session_path, self.state.get("sessionId")
        self._listing = None
        current = {"id": current_id, "current": True} if current_id else None
        if current_path is None or self._project is None:
            return {"current": current, "sessions": [], "persistent": False}
        try:
            rows, counts = await asyncio.to_thread(list_rows, current_path.parent, self._project)
        except OSError as error:
            raise RpcError("Could not list the project session store") from error
        if current_path != self._session_path or self._switching:
            raise ValueError("Session changed; reopen Sessions")

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
        page = rows[offset : offset + PAGE_SIZE]
        receipt = secrets.token_urlsafe(24)
        choices, summaries = {}, []
        if current_row and current_row.id == current_id:
            current = {**summary(current_row), "current": True}
            choices[current_row.id] = current_row
        for row in page:
            reason = None
            if counts[row.id] != 1 or row.id == current_id:
                reason = "Duplicate session ID"
            elif self._is_caller(row.path):
                reason = "Open in the calling Pi session"
            if reason is None:
                choices[row.id] = row
            summaries.append(summary(row, reason))
        self._listing = (receipt, choices)
        return {
            "current": current,
            "sessions": summaries,
            "receipt": receipt,
            "persistent": True,
            "nextOffset": offset + PAGE_SIZE if offset + PAGE_SIZE < len(rows) else None,
            "previousOffset": offset - PAGE_SIZE if offset else None,
        }

    def _listed_row(self, record: dict, listing) -> SessionRow | None:
        target = record.get("sessionId")
        if isinstance(target, str) and listing and record.get("receipt") == listing[0]:
            return listing[1].get(target)
        return None

    async def _preview_session(self, record: dict):
        listing = self._listing
        current = self.state.get("sessionId")
        row = self._listed_row(record, listing)
        if row is None or record.get("fromSessionId") != current:
            raise ValueError("Session is not available in this listing. Reload Sessions.")
        preview = await asyncio.to_thread(read_preview, row)
        if listing is not self._listing or current != self.state.get("sessionId"):
            raise ValueError("Session changed. Reload Sessions.")
        return preview

    def _ensure_switch_ready(self):
        if (
            self._closed
            or (self._chat is not None and self._outbox is None)
            or self.state["status"] != "idle"
            or self.dialogs
        ):
            raise ValueError("Pi is busy or disconnected; no session was switched")

    async def _read_native_state(self, *, timeout=15) -> dict:
        state = await self.rpc.command("get_state", timeout=timeout)
        if not isinstance(state, dict):
            raise RpcError("Pi returned an invalid session state")
        return state

    async def _switch_session(self, record: dict):
        if (
            self._control.locked()
            or self._switching
            or self.state["status"] != "idle"
            or self.dialogs
        ):
            raise ValueError("Pi is busy; wait for the reply or use Stop before switching")
        async with self._control:
            target = record.get("sessionId")
            if not isinstance(target, str) or record.get("fromSessionId") != self.state.get(
                "sessionId"
            ):
                raise ValueError("Session changed; reopen Sessions")
            if target == self.state.get("sessionId"):
                return {"unchanged": True}
            listing, self._listing = self._listing, None
            row = self._listed_row(record, listing)
            if row is None:
                raise ValueError("Session is not selectable in this listing; reopen Sessions")
            self._switching = True
            claim = None
            dispatched = False
            try:
                native = await self._read_native_state()
                self._ensure_switch_ready()
                if (
                    native.get("isStreaming") is not False
                    or native.get("isCompacting") is not False
                    or native.get("pendingMessageCount") != 0
                ):
                    raise ValueError("Pi is busy; no session was switched")
                if (
                    native.get("sessionId") != self.state.get("sessionId")
                    or self._native_path(native) != self._session_path
                ):
                    raise ValueError("Native session changed outside the picker; restart Web Chat")
                claim = SessionClaim(row.path)
                if not row.unchanged() or self._is_caller(row.path):
                    raise ValueError("Session changed or is unavailable; reopen Sessions")
                # Pi owns rebind and persistence. Never use abort as part of switching.
                self._status("switching")
                dispatched = True
                result = await self.rpc.command(
                    "switch_session", sessionPath=str(row.path), timeout=30
                )
                if isinstance(result, dict) and result.get("cancelled") is True:
                    dispatched = False
                    self._status("idle")
                    raise ValueError("Pi cancelled the session switch")
                if not isinstance(result, dict) or result.get("cancelled") is not False:
                    raise RpcError("Pi did not confirm the switch")
                self._startup_messages = []
                history = await self.rpc.command("get_messages")
                native = await self._read_native_state()
                if native.get("sessionId") != row.id or self._native_path(native) != row.path:
                    raise RpcError("Pi opened an unexpected session")
                if self._closed or self.state["status"] == "error":
                    raise RpcError("Pi closed while restoring the selected session")
                self._hydrate_messages(history)
                self._update_session(native)
                self._session_path = row.path
                if self._claim:
                    self._claim.close()
                self._claim, claim = claim, None
                self.connector.cancel_all("session_changed", "Chat switched to another Pi session")
                self.state["status"] = (
                    "running"
                    if native.get("isStreaming")
                    or native.get("isCompacting")
                    or native.get("pendingMessageCount")
                    else "idle"
                )
                self._publish(self._snapshot())
                return {"sessionId": row.id}
            except (RpcError, TimeoutError) as error:
                if dispatched:
                    # Mutation may have happened. Keep the prior labeled transcript,
                    # but do not accept more prompts against an unverified binding.
                    self._startup_messages = None
                    self._switch_failed = True
                    self._status("error")
                    self.connector.cancel_all(
                        "rpc_unavailable", "Session switch outcome unconfirmed"
                    )
                    await self.rpc.close()
                    raise RpcError(
                        "Session switch could not be verified. Pi stopped; restart Web Chat."
                    ) from error
                raise
            finally:
                if claim:
                    claim.close()
                self._switching = False

    def _hydrate_messages(self, history: dict):
        """Reconcile startup events with native history without stripping tool metadata."""
        messages = history.get("messages") if isinstance(history, dict) else None
        if not isinstance(messages, list) or any(not isinstance(m, dict) for m in messages):
            raise RpcError("Pi returned an invalid message snapshot")
        buffered = self._startup_messages or []
        # Events may arrive after the get_messages response but before this coroutine
        # resumes. The last event represented in the snapshot is the merge boundary.
        boundary = -1
        for index in range(len(buffered) - 1, -1, -1):
            if buffered[index] in messages:
                boundary = index
                break
        self.messages = [*messages, *buffered[boundary + 1 :]]
        self._startup_messages = None

    def _spawn(self, coro):
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def _publish(self, record: dict):
        if self._outbox is None:
            return
        try:
            self._outbox.put_nowait(record)
        except asyncio.QueueFull:
            # A slow UI cannot block stdout or allocate an unbounded close-task storm.
            if self._chat and not self._slow_close_requested:
                self._slow_close_requested = True
                self._spawn(self._close_slow_chat(self._chat))

    async def _close_slow_chat(self, socket):
        with contextlib.suppress(TimeoutError, RuntimeError, OSError):
            async with asyncio.timeout(1):
                await socket.close(code=1013)
        if self._chat is socket and not self._closed:
            with contextlib.suppress(RpcError, TimeoutError):
                await self.stop()

    def _status(self, status: str):
        self.state["status"] = status
        self._publish({"type": "host_status", **self.state})

    def on_event(self, event: dict):
        kind = event.get("type")
        if (
            self._switching
            and self.state["status"] in {"switching", "error"}
            and kind not in {"extension_ui_request", "host_rpc_exit"}
        ):
            if kind == "message_end" and self._startup_messages is not None:
                self._startup_messages.append(event["message"])
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
            self._status("error")
            self.connector.cancel_all("rpc_unavailable", "Pi RPC exited")
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
                    or self._closed
                    or self.state["status"] in {"stopping", "error"}
                ):
                    # A cancelled extension command may sequentially request more
                    # native dialogs while its prompt still holds _control. Fail
                    # every later request closed so Stop can acquire that lock.
                    self._spawn(self._cancel_dialog(key))
                    return
        self._publish({"type": "rpc_event", "event": event})

    async def _monitor_browser(self):
        while not self._closed:
            try:
                session = await self.runtime.wait_for_browser(timeout=1)
            except TimeoutError:
                continue
            self.connector.bind(session)
            while session.is_connected and not self._closed:
                await asyncio.sleep(0.1)
            self.connector.bind(None)

    async def _cancel_dialog(self, key: str):
        if key not in self.dialogs:
            return
        self.dialogs.pop(key)
        timer = self._dialog_timers.pop(key, None)
        if timer:
            timer.cancel()
        with contextlib.suppress(RpcError):
            await self.rpc.send({"type": "extension_ui_response", "id": key, "cancelled": True})
        self._publish({"type": "dialog_closed", "id": key})

    async def _dialog_response(self, record: dict):
        key = record.get("id")
        dialog = self.dialogs.get(key)
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
        # Consume before await: duplicate response can never reach Pi twice.
        self.dialogs.pop(key)
        timer = self._dialog_timers.pop(key, None)
        if timer:
            timer.cancel()
        await self.rpc.send(response)
        return {"answered": True}

    async def stop(self, *, timeout: float = 10):
        if self._switching:
            # A transport disconnect must not race an accepted switch's rebind.
            for key in list(self.dialogs):
                await self._cancel_dialog(key)
            async with self._control:
                pass
        if self._switch_failed:
            raise RpcError("Session switch outcome unconfirmed; restart Web Chat")
        self._status("stopping")
        self.connector.cancel_all()
        try:
            # Includes control-lock acquisition, dialog writes, clear response and
            # abort settlement. A stuck prompt/pipe must not postpone Stop forever.
            async with asyncio.timeout(timeout):
                for key in list(self.dialogs):
                    await self._cancel_dialog(key)
                async with self._control:
                    # abort alone allows queued work to continue. Clear first.
                    cleared = await self.rpc.command("clear_queue")
                    await self.rpc.command("abort", timeout=timeout)
                    self._status("idle")
                    return cleared
        except (RpcError, TimeoutError) as error:
            # Cannot prove queue clearance/abort. Retire the owned process rather
            # than leave queued work alive or pretend the app is idle. No resend.
            self._status("error")
            await self.rpc.close()
            raise RpcError(
                "Stop could not be confirmed; owned Pi was shut down. Restart browser mode."
            ) from error

    async def handle_command(self, record: dict):
        key = record.get("id")
        try:
            if not isinstance(key, str) or not 1 <= len(key) <= 256:
                raise ValueError("Unique bounded command id required")
            if key in self._seen:
                raise ValueError("Duplicate command id; not replayed")
            if len(self._seen) >= 10000:
                raise ValueError("Command limit reached; start a new application")
            self._seen.add(key)
            kind = record.get("type")
            if self._switching and kind != "extension_ui_response":
                raise ValueError("A session switch is in progress")
            if (
                kind in {"prompt", "rename"}
                and "sessionId" in record
                and record["sessionId"] != self.state.get("sessionId")
            ):
                raise ValueError("Session changed; request was not sent")
            if kind == "list_sessions":
                data = await self._list_sessions(record.get("offset", 0))
            elif kind == "preview_session":
                data = await self._preview_session(record)
            elif kind == "switch_session":
                data = await self._switch_session(record)
            elif kind == "prompt":
                message = record.get("message")
                if not isinstance(message, str) or not message.strip() or len(message) > 65536:
                    raise ValueError("Nonempty bounded message required")
                async with self._control:
                    if self.state["status"] != "idle":
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
                        self._status("idle")
            elif kind == "rename":
                name = record.get("name")
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("Session name cannot be empty")
                async with self._control:
                    if self._switch_failed:
                        raise ValueError("Session switch outcome unconfirmed; restart Web Chat")
                    await self.rpc.command("set_session_name", name=name.strip())
                    native = await self.rpc.command("get_state")
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
            # Redact both secrets even if Pi errors happen to echo a URL.
            message = str(error) or (
                "RPC deadline exceeded; delivery outcome uncertain. Do not replay blindly."
                if isinstance(error, TimeoutError)
                else type(error).__name__
            )
            message = message.replace(self.runtime.token, "[redacted]")
            message = message.replace(self.connector_token, "[redacted]")
            self._publish({"type": "ack", "id": key, "success": False, "error": message})

    async def _chat_socket(self, socket):
        from fastapi import WebSocketDisconnect

        if (
            self._closed
            or self._startup_messages is not None
            or self._chat is not None
            or not self.runtime._local_request(socket)
            or socket.headers.get("origin") != self.runtime.origin
            or not secrets.compare_digest(socket.query_params.get("token", ""), self.runtime.token)
        ):
            await socket.close(code=1008)
            return
        self._chat = socket
        self._slow_close_requested = False
        self._outbox = asyncio.Queue(maxsize=256)
        command_tasks = set()
        writer = None
        try:
            await socket.accept()
            await socket.send_json(self._snapshot())

            async def write():
                while True:
                    await socket.send_json(await self._outbox.get())

            writer = asyncio.create_task(write())
            while True:
                text = await socket.receive_text()
                if len(text) > 100000 or len(command_tasks) >= 32:
                    await socket.close(code=1008)
                    break
                record = json.loads(text)
                if not isinstance(record, dict):
                    raise ValueError("Expected command object")
                task = asyncio.create_task(self.handle_command(record))
                command_tasks.add(task)
                task.add_done_callback(command_tasks.discard)
        except (WebSocketDisconnect, ValueError, RuntimeError):
            pass
        finally:
            if writer:
                writer.cancel()
                await asyncio.gather(writer, return_exceptions=True)
            self._outbox = None
            # Reserve admission through cleanup so old acknowledgements/status cannot
            # leak into a newly admitted chat. Do not cancel accepted commands; stop
            # behind them so anything accepted before disconnect is then aborted.
            if not self._closed:
                with contextlib.suppress(RpcError, TimeoutError):
                    await self.stop()
            if command_tasks:
                await asyncio.gather(*command_tasks, return_exceptions=True)
            self._listing = None
            self._chat = None

    async def close(self):
        if self._close_task is None:
            self._closed = True
            self._close_task = asyncio.create_task(self._close())
        # Shared shielded cleanup, not a boolean early-return: cancellation of any
        # caller cannot poison later close calls or abandon the owned Pi process.
        await asyncio.shield(self._close_task)

    async def _close(self):
        self.connector.cancel_all("closed", "Application closed")
        if self._monitor:
            self._monitor.cancel()
        for timer in self._dialog_timers.values():
            timer.cancel()
        try:
            if self._chat:
                with contextlib.suppress(Exception):
                    async with asyncio.timeout(1):
                        await self._chat.close(code=1001)
        finally:
            try:
                await self.rpc.close()
            finally:
                try:
                    if self._claim is not None:
                        self._claim.close()
                        self._claim = None
                    await self.runtime.close()
                finally:
                    owned = set(self._tasks)
                    if self._monitor:
                        owned.add(self._monitor)
                    for task in owned:
                        task.cancel()
                    if owned:
                        _, unfinished = await asyncio.wait(owned, timeout=1)
                        if unfinished:
                            raise RpcError("Owned host tasks did not stop; cleanup unconfirmed")


async def serve(
    *,
    cwd: Path | None = None,
    pi: str = "pi",
    port: int = 0,
    provider: str | None = None,
    model: str | None = None,
    thinking: str | None = None,
    session: Path | None = None,
    session_inactive: bool = False,
    open_browser: bool = True,
):
    host = BrowserHost(port=port)
    opener = None
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stopped.set)
    try:
        await host.start(
            pi=pi,
            cwd=cwd,
            provider=provider,
            model=model,
            thinking=thinking,
            session=session,
            session_inactive=session_inactive,
        )
        if open_browser:
            opener = asyncio.create_task(_open_browser(host.runtime.url))
        print(f"Automata browser mode running at {host.runtime.origin} (admission URL private).")
        await stopped.wait()
    finally:
        try:
            if opener is not None:
                opener.cancel()
                await asyncio.gather(opener, return_exceptions=True)
        finally:
            try:
                await host.close()
            finally:
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.remove_signal_handler(sig)


def run(**kwargs):
    """Synchronous root-CLI entry; no independent CLI module or second server."""
    asyncio.run(serve(**kwargs))
