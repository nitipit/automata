"""Browser-first Pi application hosted on the existing WebRuntime FastAPI app."""

from __future__ import annotations

import asyncio
import contextlib
import json
import secrets
import signal
import webbrowser
from pathlib import Path

from automata.tools.web.connector import BrowserConnector, ConnectorError
from automata.tools.web.launch import prepare_launch
from automata.tools.web.rpc import PiRpc, RpcError

PACKAGE = Path(__file__).resolve().parent
DIALOGS = {"select", "confirm", "input", "editor"}


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
            # Exact flat build output only; never mount frontend/node_modules/repo.
            if (
                name not in {"index.js", "adaptive.css"}
                or not (PACKAGE / "public" / name).is_file()
            ):
                return Response(status_code=404)
            return FileResponse(PACKAGE / "public" / name, headers={"Cache-Control": "no-store"})

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

        async def chat(socket: WebSocket):
            await self._chat_socket(socket)

        # These imports are local to keep non-web CLI paths optional-dependency free.
        # FastAPI resolves annotations in globals; assign concrete runtime types.
        index.__annotations__["request"] = Request
        asset.__annotations__["request"] = Request
        connector.__annotations__["request"] = Request
        chat.__annotations__["socket"] = WebSocket
        app.add_api_route("/", index, methods=["GET"])
        app.add_api_route("/assets/{name}", asset, methods=["GET"])
        app.add_api_route("/connector/{operation}", connector, methods=["POST"])
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
            state = await self.rpc.command("get_state", timeout=30)
            self.state.update(
                {
                    key: state.get(key)
                    for key in ("sessionId", "sessionName", "model", "thinkingLevel")
                }
            )
            history = await self.rpc.command("get_messages", timeout=30)
            self._hydrate_messages(history)
            self._monitor = asyncio.create_task(self._monitor_browser())
            return self
        except BaseException:
            await self.close()
            raise

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
        if kind == "message_end":
            target = self.messages if self._startup_messages is None else self._startup_messages
            target.append(event["message"])
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
            if kind == "prompt":
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
            await socket.send_json(
                {
                    "type": "snapshot",
                    "messages": list(self.messages),
                    "state": dict(self.state),
                    "dialogs": list(self.dialogs.values()),
                }
            )

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
            webbrowser.open(host.runtime.url)
        print(f"Automata browser mode running at {host.runtime.origin} (admission URL private).")
        await stopped.wait()
    finally:
        await host.close()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)


def run(**kwargs):
    """Synchronous root-CLI entry; no independent CLI module or second server."""
    asyncio.run(serve(**kwargs))
