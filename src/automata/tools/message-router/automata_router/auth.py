"""Opt-in same-origin browser sessions and private event-driven operator control."""
from __future__ import annotations

import asyncio
import os
import stat
import time
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import urlsplit

from .auth_store import AuthStore
from .auth_requests import PairingRequests, RequestLimit
from .auth_request_http import REQUEST_PATHS, request_packet
from .protocol import json_bytes, parse_frame

COOKIE = "automata_router_session"


class SessionAuth:
    def __init__(self, store: AuthStore, public_url: str):
        self.store = store
        self.requests = PairingRequests(store)
        self.origin = public_url
        self.host = urlsplit(public_url).netloc
        if urlsplit(public_url).hostname != "127.0.0.1":
            raise ValueError("Session auth supports exact local 127.0.0.1 origin only")
        self.control_path = store.directory / "control.sock"
        if len(os.fsencode(self.control_path)) > 107:
            raise ValueError("Private Unix control path too long; choose a shorter auth directory")
        self.control = None
        self.watchers: dict[str, set[asyncio.Event]] = {}
        self.failed = False

    async def start(self) -> None:
        # Store's exclusive lifetime lock proves no second auth owner is running.
        if self.control_path.exists() or self.control_path.is_symlink():
            if not stat.S_ISSOCK(self.control_path.lstat().st_mode):
                raise ValueError("Private control path collision; explicit repair required")
            self.control_path.unlink()
        self.control = await asyncio.start_unix_server(
            self.operator, path=self.control_path, limit=1024)
        self.control_path.chmod(0o600)

    async def close(self) -> None:
        self.fail_closed()
        if self.control:
            self.control.close()
            await self.control.wait_closed()
            self.control_path.unlink(missing_ok=True)
        self.store.close()

    def fail_closed(self) -> None:
        self.failed = True
        for events in self.watchers.values():
            for event in events:
                event.set()

    @staticmethod
    def headers(scope: dict) -> dict[str, str]:
        headers = {}
        for key, value in scope.get("headers", []):
            name = key.decode("latin1").lower()
            if name in headers:
                raise ValueError("Duplicate headers")
            headers[name] = value.decode("latin1")
        return headers

    def authorize_origin(self, scope: dict, *, mandatory: bool) -> dict[str, str]:
        headers = self.headers(scope)
        if (self.failed or headers.get("host") != self.host
                or (mandatory and headers.get("origin") != self.origin)
                or ("origin" in headers and headers["origin"] != self.origin)):
            raise ValueError("Forbidden origin or host")
        return headers

    @staticmethod
    def token(headers: dict[str, str]) -> str:
        try:
            cookies = SimpleCookie()
            cookies.load(headers.get("cookie", ""))
            value = cookies.get(COOKIE)
            token = value.value if value else ""
            return token if len(token) <= 256 else ""
        except Exception:
            return ""

    def session(self, scope: dict) -> dict[str, Any]:
        headers = self.authorize_origin(scope, mandatory=True)
        session = self.store.session(self.token(headers))
        if not session:
            raise ValueError("Session expired or revoked")
        return session

    def watch(self, session: dict[str, Any]) -> tuple[asyncio.Event, Any]:
        event = asyncio.Event()
        events = self.watchers.setdefault(session["id"], set())
        events.add(event)
        timer = asyncio.get_running_loop().call_later(
            max(0, session["expiresAt"] - time.time()), event.set)

        def release():
            timer.cancel()
            events.discard(event)
            if not events:
                self.watchers.pop(session["id"], None)
        return event, release

    def revoke(self, **selection: Any) -> int:
        ids = self.store.revoke(**selection)
        for identity in ids:
            for event in self.watchers.get(identity, ()):
                event.set()
        return len(ids)

    async def operator(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            packet = parse_frame((await asyncio.wait_for(reader.readline(), 5)).decode())
            if self.failed:
                raise ValueError("Auth unavailable")
            if (len(json_bytes(packet)) > 1024
                    or any(not isinstance(value, str) for value in packet.values())):
                raise ValueError("Invalid bounded operator fields")
            if packet.get("action") == "pair" and set(packet) == {"action", "participant"}:
                result = self.store.pair_code(packet["participant"])
            elif packet.get("action") == "approve-request" and set(packet) == {
                "action", "request", "participant",
            }:
                result = self.requests.approve(packet["request"], packet["participant"])
            elif packet.get("action") == "request-status" and set(packet) == {"action", "request"}:
                result = self.requests.view(self.requests.lookup(packet["request"]))
            elif packet.get("action") == "cancel-request" and set(packet) == {"action", "request"}:
                result = self.requests.cancel(packet["request"])
            elif packet.get("action") == "revoke" and set(packet) in (
                {"action", "participant"}, {"action", "sessionId"},
            ):
                selection = ({"participant": packet["participant"]} if "participant" in packet
                             else {"session_id": packet["sessionId"]})
                result = {"revoked": self.revoke(**selection)}
            else:
                raise ValueError("Unknown operator command")
            writer.write(json_bytes({"ok": True, **result}) + b"\n")
        except OSError:
            self.fail_closed()
            writer.write(b'{"ok":false,"error":"Private auth persistence failed"}\n')
        except Exception:
            writer.write(b'{"ok":false,"error":"Invalid operator command or auth capacity"}\n')
        finally:
            try:
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

    def cookie(self, token: str = "") -> str:
        # Plain local HTTP: no Secure claim and no port-level isolation. Host-only.
        age = self.store.session_seconds if token else 0
        return f"{COOKIE}={token}; Path=/session; Max-Age={age}; HttpOnly; SameSite=Strict"

    async def http(self, scope: dict, receive: Any, send: Any, respond: Any) -> None:
        path, method = scope.get("path"), scope.get("method")
        try:
            headers = self.authorize_origin(scope, mandatory=method != "GET")
        except ValueError:
            await respond(send, 403, b'{"error":"Forbidden origin or host"}', "application/json")
            return
        if path == "/session/status" and method == "GET":
            session = self.store.session(self.token(headers))
            value = {"authenticated": bool(session)}
            if session:
                value.update(participant=session["participant"], expiresAt=session["expiresAt"])
            await respond(send, 200, json_bytes(value), "application/json")
            return
        if path not in {"/session/pair", "/session/logout", *REQUEST_PATHS} or method != "POST":
            await respond(send, 404, b'{"error":"Unknown session endpoint"}', "application/json")
            return
        if headers.get("content-type", "").split(";", 1)[0] != "application/json":
            await respond(send, 415, b'{"error":"JSON required"}', "application/json")
            return
        try:
            body = b""
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 5
            while True:
                message = await asyncio.wait_for(receive(), timeout=max(0, deadline - loop.time()))
                if message.get("type") != "http.request":
                    raise ValueError("Missing request")
                body += message.get("body", b"")
                if len(body) > 1024:
                    raise ValueError("Request too large")
                if not message.get("more_body"):
                    break
            packet = parse_frame(body.decode())
            if path in REQUEST_PATHS:
                value, token = request_packet(self, path, packet, headers)
                await respond(send, 200, json_bytes(value), "application/json",
                              {"set-cookie": self.cookie(token)} if token else None)
                return
            if path == "/session/logout":
                if packet != {}:
                    raise ValueError("Unexpected logout fields")
                self.revoke(token=self.token(headers))
                value, token = {"authenticated": False}, ""
            else:
                if set(packet) != {"code"} or not isinstance(packet["code"], str):
                    raise ValueError("Pairing requires code only")
                if self.store.session(self.token(headers)):
                    raise ValueError("Forget existing pairing before pairing again")
                token, session = self.store.exchange(packet["code"])
                value = {"authenticated": True, "participant": session["participant"],
                         "expiresAt": session["expiresAt"]}
            await respond(send, 200, json_bytes(value), "application/json",
                          {"set-cookie": self.cookie(token)})
        except RequestLimit:
            await respond(send, 429, b'{"error":"Request limit reached; no automatic retry"}',
                          "application/json")
        except OSError:
            self.fail_closed()
            await respond(send, 503, b'{"error":"Private auth persistence failed"}',
                          "application/json")
        except Exception:
            await respond(send, 400, b'{"error":"Invalid, expired or consumed pairing/request"}',
                          "application/json")
