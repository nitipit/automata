"""Private, bounded Unix-socket protocol for the Web UI local launcher."""

from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import stat
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path

_VERSION = 1
_LIMIT = 4096
_MAX_CONNECTIONS = 32
_READ_SECONDS = 2
_REPLY_SECONDS = 2
_CREATE_SECONDS = 50  # The host owns the native worker's shorter startup deadline.
_OPTIONS = ("provider", "model", "thinking")
_ID = re.compile(r"[A-Za-z0-9_-]{1,256}")
_ORIGIN = re.compile(r"http://127\.0\.0\.1:([1-9][0-9]{0,4})")
_URL = re.compile(
    r"(http://127\.0\.0\.1:[0-9]{1,5})/chat/sessions/([^/]+)/#admission=[A-Za-z0-9_-]{1,512}"
)
_ERRORS = {
    "runtime_unavailable": "A private local Web UI runtime directory is unavailable.",
    "startup_failed": "The Web UI server could not start.",
    "startup_timeout": "The Web UI server did not become ready in time.",
    "port_mismatch": "The running Web UI server is using a different port.",
    "incompatible": "The Web UI control socket is untrusted, in use, or incompatible.",
    "not_running": "There is no running Web UI server at the control socket.",
    "server_unavailable": "Web UI control did not confirm the request. Do not retry automatically.",
    "request_timeout": "The Web UI control request timed out. Do not replay it automatically.",
    "invalid_request": "Invalid Web UI control request.",
    "busy": "The Web UI control socket is busy.",
    "capacity": "Web UI session limit reached. Close an unused tab before requesting another.",
    "host_closed": "The Web UI server is shutting down.",
    "native_unavailable": "Pi could not start a new session. Existing chats were not changed.",
}
_WIRE_ERRORS = frozenset(
    {
        "incompatible",
        "invalid_request",
        "busy",
        "capacity",
        "host_closed",
        "native_unavailable",
        "request_timeout",
    }
)
_HOST_ERRORS = frozenset({"capacity", "host_closed", "native_unavailable", "invalid_request"})


class ServerError(Exception):
    """Fixed public diagnostics, never derived from untrusted or private input."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(_ERRORS[code])


@dataclass(frozen=True)
class Admission:
    """An opaque browser credential; pass `.url` directly to a trusted launcher."""

    session_id: str
    url: str = field(repr=False)


def valid_id(value):
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def origin_port(value):
    match = _ORIGIN.fullmatch(value) if isinstance(value, str) else None
    if match is None or not 1 <= int(match[1]) <= 65535:
        raise ServerError("incompatible")
    return int(match[1])


def admission_from(result):
    if set(result) == {"session_id", "url"}:
        session_id, url = result["session_id"], result["url"]
        match = _URL.fullmatch(url) if isinstance(url, str) else None
        if valid_id(session_id) and match is not None and match[2] == session_id:
            origin_port(match[1])
            return Admission(session_id, url)
    raise ServerError("incompatible")


def selection(options):
    if set(options) - set(_OPTIONS) or any(
        value is not None
        and (
            not isinstance(value, str)
            or not 1 <= len(value) <= 128
            or not value.isprintable()
            or value.startswith("-")
            or value != value.strip()
        )
        for value in options.values()
    ):
        raise ServerError("invalid_request")
    return {key: options.get(key) for key in _OPTIONS}


def socket_info(path: Path):
    """Absence is distinct from an unsafe or inaccessible filesystem object."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        raise ServerError("incompatible") from None
    if (
        not stat.S_ISSOCK(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
    ):
        raise ServerError("incompatible")
    return info


def _same_user(peer):
    # Linux SO_PEERCRED is attached by the kernel, not presented as a wire field.
    try:
        _, uid, _ = struct.unpack("iII", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    except (AttributeError, OSError, struct.error):
        return False
    return uid == os.geteuid()


def _encode(payload):
    packet = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"
    if len(packet) > _LIMIT:
        raise ServerError("invalid_request")
    return packet


def _unique(pairs):
    obj = dict(pairs)
    if len(pairs) != len(obj):
        raise ValueError
    return obj


def _decode(packet):
    if len(packet) > _LIMIT or not packet.endswith(b"\n") or packet.count(b"\n") != 1:
        raise ValueError
    obj = json.loads(packet.decode(), object_pairs_hook=_unique)
    if not isinstance(obj, dict):
        raise ValueError
    return obj


def _envelope(key, **fields):
    return {"version": _VERSION, "project": key, **fields}


def _check_envelope(payload, key):
    version = payload.pop("version", None)
    if type(version) is not int or version != _VERSION or payload.get("project") != key:
        raise ServerError("incompatible")


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError
    return remaining


def exchange(path, key, op, *, timeout, **body):
    """One request per connection; no automatic replay after dispatch."""
    deadline = time.monotonic() + timeout
    packet = _encode(_envelope(key, op=op, **body))
    if socket_info(path) is None:
        raise ServerError("not_running")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
            peer.settimeout(_remaining(deadline))
            try:
                peer.connect(os.fspath(path))
            except (FileNotFoundError, ConnectionRefusedError):
                raise ServerError("not_running") from None
            if not _same_user(peer):
                raise ServerError("incompatible")
            peer.settimeout(_remaining(deadline))
            peer.sendall(packet)
            response = bytearray()
            while b"\n" not in response and len(response) <= _LIMIT:
                peer.settimeout(_remaining(deadline))
                chunk = peer.recv(min(1024, _LIMIT + 1 - len(response)))
                if not chunk:
                    break
                response.extend(chunk)
    except TimeoutError:
        raise ServerError("request_timeout") from None
    except OSError:
        raise ServerError("server_unavailable") from None
    if not response:
        raise ServerError("server_unavailable")
    try:
        payload = _decode(response)
    except (ValueError, RecursionError):
        raise ServerError("incompatible") from None
    _check_envelope(payload, key)
    if set(payload) == {"project", "error"}:
        code = payload["error"]
        if isinstance(code, str) and code in _WIRE_ERRORS:
            raise ServerError(code)
    if set(payload) == {"project", "result"} and isinstance(payload["result"], dict):
        return payload["result"]
    raise ServerError("incompatible")


class Control:
    def __init__(self, key, host):
        self._key = key
        self._host = host
        self._tasks = {}
        self._server = None
        self._closing = False

    async def start(self, listener):
        self._server = await asyncio.start_unix_server(self._accept, sock=listener, limit=_LIMIT)

    async def close(self):
        if self._server is None:
            return
        self._closing = True
        self._server.close()
        tasks = tuple(self._tasks.items())
        for task, writer in tasks:
            writer.transport.abort()
            task.cancel()
        await asyncio.gather(*(task for task, _ in tasks), return_exceptions=True)
        await self._server.wait_closed()

    def _accept(self, reader, writer):
        peer = writer.get_extra_info("socket")
        if self._closing or peer is None or not _same_user(peer):
            writer.close()
        elif len(self._tasks) >= _MAX_CONNECTIONS:
            writer.write(_encode(_envelope(self._key, error="busy")))
            writer.close()
        else:
            task = asyncio.create_task(self._handle(reader, writer))
            self._tasks[task] = writer
            task.add_done_callback(self._tasks.pop)

    async def _request(self, reader):
        try:
            async with asyncio.timeout(_READ_SECONDS):
                payload = _decode(await reader.readuntil(b"\n"))
        except TimeoutError:
            raise ServerError("request_timeout") from None
        except (ValueError, RecursionError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            raise ServerError("invalid_request") from None
        _check_envelope(payload, self._key)
        payload.pop("project")
        return await self._dispatch(payload.pop("op", None), payload)

    async def _handle(self, reader, writer):
        try:
            try:
                response = _envelope(self._key, result=await self._request(reader))
            except ServerError as error:
                response = _envelope(self._key, error=error.code)
            except OSError:
                return
            except Exception:
                # No request data or adapter exceptions in logs or on the wire.
                response = _envelope(self._key, error="native_unavailable")
            async with asyncio.timeout(_REPLY_SECONDS):
                writer.write(_encode(response))
                await writer.drain()
        except (OSError, TimeoutError):
            pass
        finally:
            writer.close()

    async def _dispatch(self, op, body):
        if op == "ping" and not body:
            return {"port": origin_port(self._host.runtime.origin)}
        if op == "connected" and set(body) == {"session_id"} and valid_id(body["session_id"]):
            return {"connected": await self._host.wait_for_pair(body["session_id"], timeout=0)}
        if op == "create":
            options = selection(body)
            try:
                async with asyncio.timeout(_CREATE_SECONDS):
                    admitted = await self._host.admit_session(**options)
                result = {"session_id": admitted.session_id, "url": admitted.url}
                admission_from(result)
                return result
            except TimeoutError:
                raise ServerError("request_timeout") from None
            except Exception as error:
                # Never serialize an adapter exception, which could contain an admission.
                code = getattr(error, "code", None)
                raise ServerError(
                    code if isinstance(code, str) and code in _HOST_ERRORS else "native_unavailable"
                ) from None
        raise ServerError("invalid_request")
