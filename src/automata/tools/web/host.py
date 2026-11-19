"""One loopback listener for independently owned native Pi Web Chat sessions."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl

from automata.tools.web.chat import ChatSession
from automata.tools.web.connector import ConnectorError
from automata.tools.web.launch import prepare_launch
from automata.tools.web.rpc import PiRpc, RpcError
from automata.tools.web.runtime_adapter import SharedRuntime
from automata.tools.web.sessions import SessionRow, list_rows, read_row, recorded_project

PACKAGE = Path(__file__).resolve().parent
_ROUTE_ID = re.compile(r"[A-Za-z0-9_-]{1,256}")
_PRIVATE = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
_TRUST_COOKIE = "__Secure-automata-web-chat-create"
_SESSIONS = "/chat/sessions"
_LEGACY_SESSIONS = "/sessions"
_TRUST_PATH = f"{_SESSIONS}/trust/"
_LEGACY_TRUST_PATH = f"{_LEGACY_SESSIONS}/trust/"
_PROOF = re.compile(r"[a-f0-9]{64}")
_LANDING_HEADERS = {
    **_PRIVATE,
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; connect-src 'self'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
}
_BROWSER_OPEN = """import sys, webbrowser
try:
    opened = webbrowser.open(sys.stdin.read())
except BaseException:
    sys.exit(2)
sys.exit(0 if opened else 1)
"""


def _safe_id(value):
    return isinstance(value, str) and _ROUTE_ID.fullmatch(value) is not None


def _exact_path(request, path):
    return request.scope.get("raw_path", request.scope["path"].encode()) == path.encode()


def _match(value, expected):
    return (
        isinstance(value, str)
        and len(value) <= 512
        and secrets.compare_digest(value.encode(), expected.encode())
    )


@dataclass(eq=False)
class _Pair:
    bridge: object
    deadline: float
    expiry: asyncio.TimerHandle | None = None
    bridge_task: asyncio.Task | None = None
    chat_task: asyncio.Task | None = None
    chat_socket: object | None = None
    ready: bool = False
    cleanup: asyncio.Task | None = None
    nonces: set[str] = field(default_factory=set)

    @property
    def ticket(self):
        return self.bridge.token


@dataclass(frozen=True)
class AdmittedSession:
    """Native identity and a private URL for opening its first browser writer."""

    session_id: str
    url: str = field(repr=False)


@dataclass(eq=False)
class _Entry:
    chat: ChatSession
    initial: bool = False
    joined: bool = False
    pair: _Pair | None = None
    idle_timer: asyncio.TimerHandle | None = None
    retiring: asyncio.Task | None = None
    pair_ready: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def url(self):
        return f"{_SESSIONS}/{self.chat.id}/#admission={self.chat.admission}"


class SessionAdmissionError(RpcError):
    """Local session creation refused with a stable machine-readable code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class _Refusal(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


@dataclass
class _BrowserGrant:
    token: str
    monotonic_deadline: float
    wall_deadline: float

    def expired(self, monotonic, wall):
        return monotonic >= self.monotonic_deadline or wall >= self.wall_deadline


class _BrowserTrust:
    """Bounded, per-host grant and create replay state, independent of tab admission."""

    duration = 30 * 60
    landing_seconds = 10 * 60
    max_grants = 64
    max_landings = 4096

    def __init__(self, *, clock=None):
        self.clock = clock or (lambda: (time.monotonic(), time.time()))
        self.grants: dict[str, _BrowserGrant] = {}
        self.used: dict[str, tuple[int, int]] = {}
        self.signer = secrets.token_bytes(32)

    @staticmethod
    def _digest(proof):
        if not isinstance(proof, str) or _PROOF.fullmatch(proof) is None:
            raise _Refusal(400, "invalid_proof", "Invalid browser proof")
        return hashlib.sha256(bytes.fromhex(proof)).hexdigest()

    def renew(self, proof):
        key = self._digest(proof)
        monotonic, wall = self.clock()
        for stale in [key for key, grant in self.grants.items() if grant.expired(monotonic, wall)]:
            del self.grants[stale]
        grant = self.grants.get(key)
        if grant is None and len(self.grants) >= self.max_grants:
            raise _Refusal(409, "capacity", "Browser trust capacity reached")
        token = grant.token if grant else secrets.token_urlsafe(32)
        self.grants[key] = _BrowserGrant(token, monotonic + self.duration, wall + self.duration)
        return token

    def authorize(self, proof, cookie):
        key = self._digest(proof)
        grant = self.grants.get(key)
        if grant is None or grant.expired(*self.clock()) or not _match(cookie, grant.token):
            raise _Refusal(403, "browser_untrusted", "Browser trust is missing or expired")

    def landing(self):
        monotonic, wall = self.clock()
        data = f"{int(monotonic) + self.landing_seconds}.{int(wall) + self.landing_seconds}"
        data += "." + secrets.token_hex(16)
        signature = hmac.digest(self.signer, data.encode(), "sha256").hex()
        return f"{data}.{signature}"

    def claim(self, intent):
        if not isinstance(intent, str) or not re.fullmatch(
            r"[0-9]{1,16}\.[0-9]{1,16}\.[a-f0-9]{32}\.[a-f0-9]{64}", intent
        ):
            raise _Refusal(400, "invalid_intent", "Invalid landing request")
        data, signature = intent.rsplit(".", 1)
        expected = hmac.digest(self.signer, data.encode(), "sha256").hex()
        mono_deadline, wall_deadline, _ = data.split(".")
        deadline = (int(mono_deadline), int(wall_deadline))
        monotonic, wall = self.clock()
        if not _match(signature, expected) or monotonic >= deadline[0] or wall >= deadline[1]:
            raise _Refusal(403, "invalid_intent", "This landing request is no longer available")
        for stale in [key for key, (m, w) in self.used.items() if monotonic >= m or wall >= w]:
            del self.used[stale]
        if intent in self.used:
            raise _Refusal(409, "replayed_request", "This landing request was already submitted")
        if len(self.used) >= self.max_landings:
            raise _Refusal(409, "capacity", "Landing request capacity reached")
        self.used[intent] = deadline


async def _open_browser(url: str):
    """Pass the private URL over stdin; own/reap only the launcher helper."""
    process = None
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
    def __init__(
        self, *, port=0, rpc_factory=PiRpc, max_sessions=4, pair_seconds=10, idle_seconds=120
    ):
        self._runtime = SharedRuntime(port=port)
        self.runtime = self._runtime.parent
        self._rpc_factory = rpc_factory
        self._max_sessions, self._pair_seconds, self._idle_seconds = (
            max_sessions,
            pair_seconds,
            idle_seconds,
        )
        self._entries: dict[str, _Entry] = {}
        self._tickets: dict[str, tuple[_Entry, _Pair]] = {}
        self._connectors: dict[str, _Entry] = {}
        self._owned: set[ChatSession] = set()
        self._starts: set[asyncio.Task] = set()
        self._starting_ids: set[str] = set()
        self._browser_trust = _BrowserTrust()
        self._initial: _Entry | None = None
        self._project: Path | None = None
        self._launch_options: dict = {}
        inherited = os.environ.get("PI_SESSION_FILE")
        self._caller_session = Path(inherited).expanduser().resolve() if inherited else None
        self._started = False
        self._closed = False
        self._close_task: asyncio.Task | None = None
        self._cleanup_failed = False
        self._install_routes()

    @property
    def admission_url(self):
        if self._initial is None or self._closed or self._initial.retiring:
            raise RuntimeError("Initial Web Chat admission is unavailable")
        return self.runtime.origin + self._initial.url

    @property
    def sessions_url(self) -> str:
        return f"{self.runtime.origin}{_SESSIONS}/"

    @property
    def initial_session(self):
        """Initial native context, for owned tooling and isolated integration fixtures."""
        return self._initial.chat if self._initial else None

    def _origin_ok(self, request):
        return (
            self._runtime.local_request(request)
            and request.headers.get("origin") == self.runtime.origin
        )

    @staticmethod
    def _session_path_allowed(request, id, suffix):
        if not _safe_id(id):
            return False
        return any(
            _exact_path(request, f"{prefix}/{id}{suffix}")
            for prefix in (_SESSIONS, _LEGACY_SESSIONS)
        )

    def _authenticate(self, request, id, suffix, proof):
        entry = self._entries.get(id)
        if (
            not self._session_path_allowed(request, id, suffix)
            or not self._origin_ok(request)
            or entry is None
            or not _match(proof, entry.chat.admission)
        ):
            raise _Refusal(403, "forbidden", "Web Chat admission was rejected")
        if self._closed:
            raise _Refusal(410, "host_closed", "Web Chat is shutting down")
        if entry.retiring or entry.chat._dead:
            raise _Refusal(403, "forbidden", "Web Chat admission is no longer available")
        return entry

    @staticmethod
    async def _read_body(request, limit):
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > limit:
                raise ValueError("Request is too large")
            body.extend(chunk)
        return body

    @staticmethod
    def _bearer(request):
        value = request.headers.get("authorization", "")
        return value[7:] if value.startswith("Bearer ") else ""

    def _new_pair(self, entry):
        current = entry.pair
        if current:
            code = (
                "cleanup_pending"
                if current.cleanup
                else "writer_active"
                if current.ready
                else "pair_reserved"
            )
            message = {
                "cleanup_pending": "Previous connection is still stopping",
                "writer_active": "This Pi session already has a writer",
                "pair_reserved": "Another browser connection is pairing",
            }[code]
            raise _Refusal(409, code, message)
        loop = asyncio.get_running_loop()
        pair = _Pair(self._runtime.new_bridge(), loop.time() + self._pair_seconds)
        entry.pair = pair
        self._tickets[pair.ticket] = (entry, pair)
        pair.expiry = loop.call_at(pair.deadline, self._drop_pair, entry, pair)
        return pair

    def _lookup_pair(self, socket):
        if self._closed or not self._origin_ok(socket):
            return None
        supplied = socket.query_params.getlist("token")
        if len(supplied) != 1:
            return None
        found = self._tickets.get(supplied[0])
        if found:
            entry, pair = found
            if (
                entry.pair is pair
                and not entry.retiring
                and not entry.chat._dead
                and not pair.cleanup
                and (pair.ready or asyncio.get_running_loop().time() < pair.deadline)
            ):
                return found
        return None

    def _mutation_pair(self, entry, body):
        pair = entry.pair
        if (
            self._closed
            or entry.retiring
            or entry.chat._dead
            or pair is None
            or not pair.ready
            or pair.cleanup
            or not _match(body.get("ticket"), pair.ticket)
        ):
            raise _Refusal(403, "forbidden", "This request is not from the current writer")
        nonce = body.get("nonce")
        if not _safe_id(nonce):
            raise _Refusal(400, "invalid_request", "A valid request nonce is required")
        if nonce in pair.nonces:
            raise _Refusal(
                409, "replayed_request", "This request was already submitted; it was not replayed"
            )
        if len(pair.nonces) >= 64:
            raise _Refusal(
                409, "capacity", "Request limit reached. Reconnect before opening another chat."
            )
        pair.nonces.add(nonce)
        return pair

    def _install_routes(self):
        from fastapi import Request, WebSocket
        from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        from starlette.requests import ClientDisconnect

        app = self.runtime.app
        app.router.routes[:] = [
            route for route in app.router.routes if getattr(route, "path", None) != "/"
        ]
        templates = Environment(
            loader=FileSystemLoader(PACKAGE / "frontend"), autoescape=select_autoescape()
        )

        def refusal(error):
            return JSONResponse(
                {"code": error.code, "error": str(error)},
                status_code=error.status,
                headers=_PRIVATE,
            )

        async def root(request: Request):
            if not self._runtime.local_request(request):
                return Response(status_code=403, headers=_PRIVATE)
            return HTMLResponse(
                templates.get_template("entry.html").render(sessions_url=f"{_SESSIONS}/"),
                headers=_PRIVATE,
            )

        async def index(id: str, request: Request):
            if not self._runtime.local_request(request):
                return Response(status_code=403, headers=_PRIVATE)
            if not self._session_path_allowed(request, id, "/"):
                return Response(status_code=404, headers=_PRIVATE)
            if _exact_path(request, f"{_LEGACY_SESSIONS}/{id}/"):
                # The redirect has no fragment: browsers inherit the original
                # fragment without exposing it to the host or copying query data.
                return Response(
                    status_code=307, headers={**_PRIVATE, "Location": f"{_SESSIONS}/{id}/"}
                )
            return HTMLResponse(
                templates.get_template("index.html").render(),
                headers={**_PRIVATE, "Referrer-Policy": "same-origin"},
            )

        async def trust_json(request, fields):
            if (
                request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                != "application/json"
            ):
                raise ValueError("Expected JSON")
            body = json.loads(await self._read_body(request, 4096))
            if not isinstance(body, dict) or set(body) != fields:
                raise ValueError("Invalid browser trust request")
            return body

        async def landing(request: Request):
            if not self._runtime.local_request(request) or not any(
                _exact_path(request, f"{prefix}/") for prefix in (_SESSIONS, _LEGACY_SESSIONS)
            ):
                return Response(status_code=403, headers=_PRIVATE)
            if self._closed:
                return Response(status_code=410, headers=_PRIVATE)
            auto = (
                not request.url.query
                and all(
                    request.headers.getlist(key) == [value]
                    for key, value in (
                        ("sec-fetch-mode", "navigate"),
                        ("sec-fetch-dest", "document"),
                        ("sec-fetch-site", "none"),
                        ("sec-fetch-user", "?1"),
                    )
                )
                and not any(name in request.headers for name in ("sec-purpose", "purpose"))
            )
            return HTMLResponse(
                '<!doctype html><html lang="en"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                "<title>Automata — New chat</title><main><h1>New chat</h1>"
                f'<p id="trust-status" role="status" data-intent="{self._browser_trust.landing()}" '
                f'data-auto="{int(auto)}">Start a new Pi session in this tab.</p>'
                '<button id="trust-create" type="button" disabled>Create a new chat</button>'
                "<noscript><p>JavaScript is needed to verify browser trust.</p></noscript></main>"
                '<script type="module" src="/assets/browser-trust-landing.js"></script></html>',
                headers=_LANDING_HEADERS,
            )

        async def renew_trust(id: str, request: Request):
            try:
                entry = self._authenticate(request, id, "/browser-trust", self._bearer(request))
                body = await trust_json(request, {"proof", "ticket"})
                if not _match(self._bearer(request), entry.chat.admission):
                    raise _Refusal(403, "forbidden", "Web Chat admission was rejected")
                pair = entry.pair
                if (
                    self._closed
                    or entry.retiring
                    or entry.chat._dead
                    or pair is None
                    or not pair.ready
                    or pair.cleanup is not None
                    or not _match(body["ticket"], pair.ticket)
                ):
                    raise _Refusal(403, "forbidden", "This request is not from the current writer")
                token = self._browser_trust.renew(body["proof"])
                response = Response(status_code=204, headers=_PRIVATE)
                # The same grant works at either exact creation path; neither
                # cookie is sent to chat, asset, connector or root routes.
                for path in (_TRUST_PATH, _LEGACY_TRUST_PATH):
                    response.set_cookie(
                        _TRUST_COOKIE,
                        token,
                        max_age=self._browser_trust.duration,
                        path=path,
                        secure=True,
                        httponly=True,
                        samesite="strict",
                    )
                return response
            except _Refusal as error:
                return refusal(error)
            except (ValueError, UnicodeError, ClientDisconnect, RecursionError):
                return refusal(_Refusal(400, "invalid_request", "Invalid browser trust renewal"))

        async def create_trusted(request: Request):
            try:
                if not self._origin_ok(request) or not any(
                    _exact_path(request, path + "create")
                    for path in (_TRUST_PATH, _LEGACY_TRUST_PATH)
                ):
                    raise _Refusal(403, "forbidden", "Browser trust origin was rejected")
                if self._closed:
                    raise _Refusal(410, "host_closed", "Web Chat is shutting down")
                body = await trust_json(request, {"proof", "intent"})
                self._browser_trust.authorize(body["proof"], request.cookies.get(_TRUST_COOKIE))
                # No await between replay claim and the owned slot reservation.
                self._browser_trust.claim(body["intent"])
                child = await self._await_start(self._start_worker())
                return JSONResponse({"url": child.url}, headers=_PRIVATE)
            except _Refusal as error:
                return refusal(error)
            except (ValueError, UnicodeError, ClientDisconnect, RecursionError):
                return refusal(_Refusal(400, "invalid_request", "Invalid new chat request"))

        async def asset(name: str, request: Request):
            if not self._runtime.local_request(request):
                return Response(status_code=403)
            allowed = name in {
                "index.js",
                "ui.js",
                "connection-bootstrap.js",
                "browser-trust-landing.js",
                "adaptive.css",
                "adapter-LICENSE.txt",
                "third-party-LICENSES.txt",
            } or re.fullmatch(r"chunk-[A-Z0-9]{8}\.js", name)
            path = PACKAGE / "public" / name
            if not allowed or not path.is_file() or path.is_symlink():
                return Response(status_code=404)
            return FileResponse(path, headers=_PRIVATE)

        async def connection(id: str, request: Request):
            try:
                entry = self._authenticate(request, id, "/chat/connection", self._bearer(request))
                return JSONResponse({"ticket": self._new_pair(entry).ticket}, headers=_PRIVATE)
            except _Refusal as error:
                return refusal(error)

        async def bridge(socket: WebSocket):
            matched = self._lookup_pair(socket)
            if matched is None or matched[1].bridge_task is not None:
                await socket.close(code=1008)
                return
            entry, pair = matched
            pair.bridge_task = asyncio.current_task()
            try:
                # Dispatch the unchanged /ws request to the real upstream endpoint.
                await pair.bridge.app(socket.scope, socket.receive, socket.send)
            finally:
                self._drop_pair(entry, pair)

        async def chat(id: str, socket: WebSocket):
            matched = self._lookup_pair(socket)
            if (
                matched is None
                or not self._session_path_allowed(socket, id, "/chat")
                or matched[0].chat.id != id
                or matched[1].bridge_task is None
                or matched[1].chat_task is not None
            ):
                await socket.close(code=1008)
                return
            entry, pair = matched
            pair.chat_task, pair.chat_socket = asyncio.current_task(), socket
            try:
                remaining = pair.deadline - asyncio.get_running_loop().time()
                browser = await pair.bridge.wait_for_browser(timeout=remaining)
                async with asyncio.timeout_at(pair.deadline):
                    native = await entry.chat.read_native(timeout=5)
                if not entry.chat.matches_native(native):
                    entry.chat.invalidate()
                    return

                def active():
                    if (
                        self._closed
                        or entry.pair is not pair
                        or entry.retiring
                        or entry.chat._dead
                        or pair.cleanup
                        or not browser.is_connected
                    ):
                        raise RuntimeError("Pair expired before chat became active")
                    entry.chat.connector.bind(browser)
                    pair.ready = entry.joined = True
                    entry.pair_ready.set()
                    if pair.expiry:
                        pair.expiry.cancel()
                    self._cancel_idle(entry)

                await entry.chat.serve_chat(socket, active, lambda: pair.cleanup is None)
            except (RpcError, RuntimeError, TimeoutError, OSError):
                pass
            finally:
                self._drop_pair(entry, pair)

        async def connector(operation: str, request: Request):
            proof = self._bearer(request)
            entry = self._connectors.get(proof)
            if (
                not self._runtime.local_request(request)
                or request.headers.get("origin") is not None
                or entry is None
                or self._closed
                or entry.retiring
            ):
                return JSONResponse(
                    {
                        "ok": False,
                        "error": {"code": "forbidden", "message": "Connector access denied"},
                    },
                    status_code=403,
                    headers=_PRIVATE,
                )
            try:
                body = json.loads(await self._read_body(request, 300000))
                if not isinstance(body, dict):
                    raise ValueError("Expected a JSON object")
                client = entry.chat.connector
                if operation == "execute":
                    result = await client.execute(body)
                elif operation == "subscribe":
                    result = client.subscribe(body)
                elif operation == "wait":
                    result = await client.wait(body)
                elif operation == "unsubscribe":
                    result = client.unsubscribe(body)
                else:
                    raise ConnectorError("invalid_request", "Unknown connector operation")
                return JSONResponse(result, headers=_PRIVATE)
            except (ValueError, UnicodeError, ClientDisconnect, RecursionError):
                return JSONResponse(
                    {
                        "ok": False,
                        "error": {
                            "code": "invalid_request",
                            "message": "Invalid or oversized JSON object",
                        },
                    },
                    status_code=400,
                    headers=_PRIVATE,
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
                    },
                    headers=_PRIVATE,
                )

        async def opened(id: str, request: Request):
            try:
                entry = self._authenticate(request, id, "/open", self._bearer(request))
                if (
                    request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    != "application/json"
                ):
                    raise ValueError("Expected JSON")
                body = json.loads(await self._read_body(request, 4096))
                if (
                    not isinstance(body, dict)
                    or set(body) != {"ticket", "nonce", "receipt", "sessionId", "inactiveConfirmed"}
                    or body["inactiveConfirmed"] is not True
                    or not _safe_id(body["sessionId"])
                    or not _safe_id(body["receipt"])
                ):
                    raise ValueError("Invalid picker selection")
                pair = self._mutation_pair(entry, body)
                target = await self._open_saved(entry, pair, body)
                return JSONResponse(
                    {"sessionId": target.chat.id, "url": target.url}, headers=_PRIVATE
                )
            except _Refusal as error:
                return refusal(error)
            except (ValueError, UnicodeError, ClientDisconnect, RecursionError):
                return refusal(_Refusal(400, "invalid_request", "Invalid saved session selection"))

        async def new_session(request: Request):
            from html import escape

            try:
                if not self._origin_ok(request) or not any(
                    _exact_path(request, path) for path in (f"{_SESSIONS}/", _LEGACY_SESSIONS)
                ):
                    raise _Refusal(403, "forbidden", "Web Chat admission was rejected")
                if (
                    request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    != "application/x-www-form-urlencoded"
                ):
                    raise ValueError("Expected URL-encoded form")
                fields = parse_qsl(
                    (await self._read_body(request, 4096)).decode(),
                    keep_blank_values=True,
                    strict_parsing=True,
                    errors="strict",
                    max_num_fields=4,
                )
                body = dict(fields)
                if len(fields) != 4 or set(body) != {
                    "sourceSessionId",
                    "admission",
                    "ticket",
                    "nonce",
                }:
                    raise ValueError("Invalid new chat form")
                id = body["sourceSessionId"]
                entry = self._entries.get(id) if _safe_id(id) else None
                if entry is None or not _match(body["admission"], entry.chat.admission):
                    raise _Refusal(403, "forbidden", "Web Chat admission was rejected")
                if self._closed:
                    raise _Refusal(410, "host_closed", "Web Chat is shutting down")
                self._mutation_pair(entry, body)
                child = await self._await_start(self._start_worker())
                return Response(status_code=303, headers={**_PRIVATE, "Location": child.url})
            except (ValueError, UnicodeError, ClientDisconnect, _Refusal) as error:
                if not isinstance(error, _Refusal):
                    error = _Refusal(400, "invalid_request", "Invalid new chat request")
                return HTMLResponse(
                    "<!doctype html><meta charset=utf-8>"
                    "<title>Web Chat — New chat unavailable</title>"
                    "<h1>New chat unavailable</h1><p>" + escape(str(error)) + "</p>"
                    "<p>Return to the original tab to continue.</p>",
                    status_code=error.status,
                    headers=_PRIVATE,
                )

        # Annotations in these local route closures are postponed at import time.
        for endpoint in (
            root,
            index,
            asset,
            connection,
            connector,
            opened,
            new_session,
            landing,
            renew_trust,
            create_trusted,
        ):
            endpoint.__annotations__["request"] = Request
        for endpoint in (bridge, chat):
            endpoint.__annotations__["socket"] = WebSocket
        app.add_api_route("/", root, methods=["GET"])
        app.add_api_route("/assets/{name}", asset, methods=["GET"])
        app.add_api_route("/connector/{operation}", connector, methods=["POST"])
        app.add_api_websocket_route("/ws", bridge)
        app.add_api_route(f"{_SESSIONS}/", new_session, methods=["POST"])
        app.add_api_route(_LEGACY_SESSIONS, new_session, methods=["POST"])
        for prefix in (_SESSIONS, _LEGACY_SESSIONS):
            app.add_api_route(f"{prefix}/", landing, methods=["GET"])
            app.add_api_route(f"{prefix}/{{id}}/", index, methods=["GET"])
            app.add_api_route(f"{prefix}/{{id}}/browser-trust", renew_trust, methods=["POST"])
            app.add_api_route(f"{prefix}/trust/create", create_trusted, methods=["POST"])
            app.add_api_route(f"{prefix}/{{id}}/chat/connection", connection, methods=["POST"])
            app.add_api_route(f"{prefix}/{{id}}/open", opened, methods=["POST"])
            app.add_api_websocket_route(f"{prefix}/{{id}}/chat", chat)

    async def start(
        self,
        *,
        pi="pi",
        cwd=None,
        provider=None,
        model=None,
        thinking=None,
        session=None,
        session_inactive=False,
        extra_args=(),
        create_initial=True,
    ):
        if not create_initial and session is not None:
            raise ValueError("Resuming a session requires an initial Web Chat worker")
        extension = PACKAGE.parents[1] / "runtimes" / "pi" / "extensions" / "web-ui" / "index.ts"
        if any(
            arg.split("=", 1)[0] in {"--session", "--continue", "--no-session", "-c"}
            for arg in extra_args
        ):
            raise ValueError("Native session selection is owned by Web Chat")
        self._launch_options = dict(
            pi=pi,
            extension=extension,
            cwd=cwd,
            provider=provider,
            model=model,
            thinking=thinking,
            extra_args=extra_args,
        )
        try:
            launch = prepare_launch(
                **self._launch_options, session=session, session_inactive=session_inactive
            )
            self._project = launch.cwd
            target = None
            if session is not None:
                path = Path(launch.argv[launch.argv.index("--session") + 1])
                self._project = recorded_project(path)
                target = await asyncio.to_thread(read_row, path, self._project)
                if target is None or not _safe_id(target.id):
                    raise ValueError("Saved session does not have a valid native Web Chat identity")
                self._launch_options["cwd"] = self._project
            else:
                self._launch_options["cwd"] = launch.cwd
            await self.runtime.start()
            if create_initial:
                self._initial = await asyncio.shield(
                    self._start_worker(target=target, initial=True, launch=launch)
                )
            self._started = True
            return self
        except BaseException:
            await self.close()
            raise

    async def admit_session(self, *, provider=None, model=None, thinking=None) -> AdmittedSession:
        """Create a fresh native session, inheriting any unspecified host launch options."""
        if not self._started or self._closed:
            raise SessionAdmissionError("host_closed")
        options = self._launch_options | {
            name: value
            for name, value in (("provider", provider), ("model", model), ("thinking", thinking))
            if value is not None
        }
        launch = prepare_launch(**options)
        try:
            entry = await self._await_start(self._start_worker(launch=launch))
        except _Refusal as error:
            raise SessionAdmissionError(error.code) from None
        return AdmittedSession(entry.chat.id, self.runtime.origin + entry.url)

    async def wait_for_pair(self, session_id: str, *, timeout: float) -> bool:
        """Observe both transports for this live session without acquiring a writer."""
        from starlette.websockets import WebSocketState

        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError("Pair timeout must be finite and nonnegative")
        entry = self._entries.get(session_id)
        if entry is None:
            return False
        try:
            async with asyncio.timeout(timeout):
                while not (self._closed or entry.retiring or entry.chat._dead):
                    pair = entry.pair
                    browser = entry.chat.connector.session
                    if (
                        pair
                        and pair.ready
                        and not pair.cleanup
                        and browser
                        and browser.is_connected
                        and pair.chat_socket.client_state is WebSocketState.CONNECTED
                        and pair.chat_socket.application_state is WebSocketState.CONNECTED
                    ):
                        return True
                    # A transport may have closed before its handler starts pair
                    # cleanup. Wait for a subsequent ready pair or retirement.
                    entry.pair_ready.clear()
                    await entry.pair_ready.wait()
        except TimeoutError:
            pass
        return False

    def _start_worker(self, target=None, *, initial=False, launch=None):
        if self._closed:
            raise _Refusal(410, "host_closed", "Web Chat is shutting down")
        if len(self._owned) >= self._max_sessions:
            raise _Refusal(
                409,
                "capacity",
                "Web Chat is at its session limit. Close an unused tab and retry after cleanup.",
            )
        if target is not None and (target.id in self._starting_ids or target.id in self._entries):
            raise _Refusal(409, "target_unavailable", "Session is already open or starting")
        chat = ChatSession(
            rpc_factory=self._rpc_factory,
            on_exit=self._rpc_exited,
            unavailable=self._row_unavailable,
        )
        self._owned.add(chat)  # Atomic reservation before the first await.
        if target is not None:
            self._starting_ids.add(target.id)
        task = asyncio.create_task(self._spawn_worker(chat, target, initial, launch))
        self._starts.add(task)

        def finished(completed):
            self._starts.discard(completed)
            if not completed.cancelled():
                completed.exception()  # Request may have disconnected after dispatch.

        task.add_done_callback(finished)
        return task

    async def _spawn_worker(self, chat, target, initial, launch):
        try:
            if self._closed:
                raise _Refusal(410, "host_closed", "Web Chat is shutting down")
            async with asyncio.timeout(45):
                if target is not None:
                    rows, counts = await asyncio.to_thread(
                        list_rows, target.path.parent, self._project
                    )
                    if counts[target.id] != 1 or not any(
                        row.id == target.id
                        and row.path == target.path
                        and row.revision == target.revision
                        for row in rows
                    ):
                        raise ValueError("Session changed or its native ID is no longer unique")
                if launch is None:
                    launch = prepare_launch(
                        **self._launch_options,
                        session=target.path if target else None,
                        session_inactive=target is not None,
                    )
                await chat.start(
                    launch,
                    origin=self.runtime.origin,
                    project=self._project,
                    caller=self._caller_session,
                    route_id=_safe_id,
                    target=target,
                )
            if (
                self._closed
                or chat.id in self._entries
                or (target is None and chat.id in self._starting_ids)
            ):
                raise RpcError("Native session could not be published uniquely")
            entry = _Entry(chat, initial=initial)
            self._entries[chat.id] = entry
            self._connectors[chat.connector_token] = entry
            self._arm_idle(entry)
            return entry
        except BaseException:
            try:
                await chat.close()
                self._owned.discard(chat)
            except (RpcError, TimeoutError, OSError):
                self._cleanup_failed = True
            raise
        finally:
            if target is not None:
                self._starting_ids.discard(target.id)

    async def _await_start(self, task):
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if self._closed and task.cancelled():
                raise _Refusal(410, "host_closed", "Web Chat is shutting down") from None
            raise
        except ValueError:
            raise _Refusal(
                409,
                "target_unavailable",
                "Session changed or could not be claimed; reload Sessions",
            ) from None
        except (RpcError, TimeoutError, OSError):
            raise _Refusal(
                503,
                "native_unavailable",
                "Pi could not start the requested session. The source chat was not changed.",
            ) from None

    def _row_unavailable(self, row: SessionRow):
        if not _safe_id(row.id):
            return "Native session ID is not routable in Web Chat"
        entry = self._entries.get(row.id)
        if row.id in self._starting_ids or (
            entry
            and (
                entry.pair
                or entry.retiring
                or entry.chat._dead
                or entry.chat._session_path != row.path
            )
        ):
            return "Session is owned by another Web Chat connection"
        return None

    async def _open_saved(self, entry, pair, body):
        source = entry.chat
        if source._control.locked() or source.state["status"] != "idle" or source.dialogs:
            raise _Refusal(
                409, "source_busy", "Wait for the reply or use Stop before opening a session"
            )
        task = None
        async with source._control:
            listing = source._listing
            row = source.listed_row(body, listing)
            if row is None or row.id == source.id:
                raise _Refusal(
                    409,
                    "stale_receipt",
                    "Session is not selectable in this listing; reload Sessions",
                )
            try:
                native = await source.read_native(timeout=5)
            except (RpcError, TimeoutError):
                raise _Refusal(
                    503, "native_unavailable", "The source native session could not be verified"
                ) from None
            if not source.matches_native(native):
                source.invalidate()
                raise _Refusal(
                    503, "native_unavailable", "The source native session changed and was retired"
                )
            if (
                entry.pair is not pair
                or pair.cleanup
                or source._dead
                or source.state["status"] != "idle"
                or source.dialogs
                or native.get("isStreaming") is not False
                or native.get("isCompacting") is not False
                or native.get("pendingMessageCount") != 0
            ):
                raise _Refusal(409, "source_busy", "Source no longer idle; reopen Sessions")
            if listing is not source._listing or not row.unchanged() or source._is_caller(row.path):
                raise _Refusal(409, "stale_receipt", "Saved session changed; reload Sessions")
            if self._row_unavailable(row):
                raise _Refusal(
                    409, "target_unavailable", "Session is owned by another Web Chat connection"
                )
            target = self._entries.get(row.id)
            if target is not None:
                # Detached target: revalidate uniqueness before replacing admission.
                try:
                    async with asyncio.timeout(5):
                        _, counts = await asyncio.to_thread(
                            list_rows, row.path.parent, self._project
                        )
                except (OSError, TimeoutError):
                    raise _Refusal(
                        409, "target_unavailable", "Could not verify the saved target"
                    ) from None
                if (
                    counts[row.id] != 1
                    or not row.unchanged()
                    or self._entries.get(row.id) is not target
                    or self._row_unavailable(row)
                    or entry.pair is not pair
                    or pair.cleanup
                    or source._listing is not listing
                    or self._closed
                ):
                    raise _Refusal(
                        409, "target_unavailable", "Saved target changed; reopen Sessions"
                    )
                source._listing = None
                target.chat.admission = secrets.token_urlsafe(32)
                self._arm_idle(target)
                return target
            task = self._start_worker(row)
            source._listing = None
        return await self._await_start(task)

    @staticmethod
    def _cancel_idle(entry):
        if entry.idle_timer:
            entry.idle_timer.cancel()
            entry.idle_timer = None

    def _arm_idle(self, entry):
        if self._closed or entry.retiring or (entry.initial and not entry.joined):
            return
        self._cancel_idle(entry)
        entry.idle_timer = asyncio.get_running_loop().call_later(
            self._idle_seconds, self._retire, entry
        )

    def _rpc_exited(self, chat):
        if self._closed or chat.id is None:
            return  # Startup sees the failure; shutdown already owns cleanup.
        entry = self._entries.get(chat.id)
        if entry and entry.chat is chat:
            self._retire(entry)

    def _drop_pair(self, entry, pair):
        if entry.pair is not pair or pair.cleanup:
            return
        self._tickets.pop(pair.ticket, None)
        if pair.expiry:
            pair.expiry.cancel()
        entry.chat.detach()
        entry.pair_ready.clear()
        pair.cleanup = asyncio.create_task(self._finish_pair(entry, pair))

    async def _finish_pair(self, entry, pair):
        from starlette.websockets import WebSocketDisconnect

        chat = entry.chat

        async def close_chat_socket():
            if pair.chat_socket is not None:
                with contextlib.suppress(WebSocketDisconnect, RuntimeError, OSError, TimeoutError):
                    async with asyncio.timeout(1):
                        await pair.chat_socket.close(code=1001)

        try:
            await asyncio.gather(close_chat_socket(), pair.bridge.close(timeout=2))
            handlers = {
                task
                for task in (pair.chat_task, pair.bridge_task)
                if task is not None and not task.done()
            }
            if handlers:
                _, pending = await asyncio.wait(handlers, timeout=1)
                for task in pending:
                    task.cancel()
                if pending:
                    _, pending = await asyncio.wait(pending, timeout=1)
                    if pending:
                        raise RpcError("Browser socket cleanup unconfirmed")
            if pair.ready and not (self._closed or chat._dead or entry.retiring):
                await chat.stop()
            await chat.settle_commands()
        except Exception:
            # Failed cleanup retires this Pi rather than admitting another writer.
            self._retire(entry)
        finally:
            if entry.pair is pair:
                entry.pair = None
                if pair.ready:
                    self._arm_idle(entry)

    def _retire(self, entry):
        if entry.retiring is None:
            self._cancel_idle(entry)
            self._connectors.pop(entry.chat.connector_token, None)
            entry.retiring = asyncio.create_task(self._finish_retire(entry))
            entry.pair_ready.set()
        return entry.retiring

    async def _finish_retire(self, entry):
        chat = entry.chat
        try:
            if entry.pair:
                pair = entry.pair
                self._drop_pair(entry, pair)
                await pair.cleanup
            await chat.close()
        except Exception:
            self._cleanup_failed = True
        else:
            if self._entries.get(chat.id) is entry:
                self._entries.pop(chat.id)
            self._owned.discard(chat)

    async def close(self):
        if self._close_task is None:
            self._closed = True
            self._close_task = asyncio.create_task(self._close())
        await asyncio.shield(self._close_task)

    async def _close(self):
        try:
            # Stop exposing resources immediately; cleanup of all children is concurrent.
            retiring = [self._retire(entry) for entry in tuple(self._entries.values())]
            # A reservation created just before shutdown must enter the worker's
            # finally block before cancellation, even if its RPC has not started.
            await asyncio.sleep(0)
            starting = [task for task in self._starts if not task.done()]
            for task in starting:
                task.cancel()
            if retiring or starting:
                done, pending = await asyncio.wait([*retiring, *starting], timeout=22)
                self._cleanup_failed |= bool(
                    pending
                    or any(
                        task in retiring and not task.cancelled() and task.exception()
                        for task in done
                    )
                )
        finally:
            await self.runtime.close()
        if self._cleanup_failed or self._owned:
            raise RpcError("One or more owned Web Chat resources did not confirm shutdown")


async def serve(
    *,
    cwd=None,
    pi="pi",
    port=0,
    provider=None,
    model=None,
    thinking=None,
    session=None,
    session_inactive=False,
    open_browser=True,
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
            opener = asyncio.create_task(_open_browser(host.admission_url))
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
    asyncio.run(serve(**kwargs))
