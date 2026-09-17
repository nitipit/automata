"""Loopback ASGI transport and explicitly selected public files, without UI policy."""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .protocol import Connection, JsonObject, json_bytes, parse_frame


class RouterApp:
    def __init__(
        self,
        backend: Any,
        *,
        public_root: Path | None = None,
        private_paths: tuple[Path, ...] = (),
        origins: tuple[str, ...] = (),
        legacy_roots: tuple[Path, Path] | None = None,
    ):
        self.backend = backend
        self.public_root = public_root.resolve() if public_root is not None else None
        self.private_paths = tuple(path.resolve() for path in private_paths)
        self.origins = {backend.public_url, *origins}
        self.asset_root = Path(__file__).resolve().parents[1] / "browser"
        self.legacy_roots = tuple(path.resolve() for path in legacy_roots) if legacy_roots else None
        roots = [self.public_root, *(self.legacy_roots or ())]
        for root in roots:
            if root is None:
                continue
            if not root.is_dir():
                raise ValueError("Public roots must be existing directories")
            if any(
                private.is_relative_to(root) or root.is_relative_to(private)
                for private in self.private_paths
            ):
                raise ValueError("Public and private roots must not overlap")

    async def __call__(self, scope: JsonObject, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            await self.http(scope, send)
        elif scope["type"] == "websocket":
            await self.websocket(scope, receive, send)
        else:
            raise RuntimeError("Unsupported ASGI scope")

    async def http(self, scope: JsonObject, send: Any) -> None:
        method = scope.get("method", "GET")
        if method not in {"GET", "HEAD"}:
            await self.respond(
                send, 405, b"Method not allowed\n", "text/plain", {"allow": "GET, HEAD"}
            )
            return
        path = unquote(scope.get("path", "/"))
        if path == "/health":
            await self.respond(
                send,
                200,
                json_bytes(self.backend.health()) + b"\n",
                "application/json",
                head=method == "HEAD",
            )
            return
        candidate = self.public_path(path)
        if candidate is None or not candidate.is_file():
            await self.respond(send, 404, b"Not found\n", "text/plain", head=method == "HEAD")
            return
        try:
            body = candidate.read_bytes()
        except OSError:
            await self.respond(send, 404, b"Not found\n", "text/plain", head=method == "HEAD")
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        await self.respond(send, 200, body, content_type, head=method == "HEAD")

    def public_path(self, path: str) -> Path | None:
        if path.startswith("/assets/"):
            return self.safe_child(self.asset_root, path.removeprefix("/assets/"))
        if self.legacy_roots:
            library, sessions = self.legacy_roots
            if path.startswith("/lib/"):
                return self.safe_child(library, path.removeprefix("/lib/"))
            if path.startswith("/sessions/"):
                return self.safe_child(
                    sessions,
                    path.removeprefix("/sessions/") + ("index.html" if path.endswith("/") else ""),
                )
        if self.public_root is None or not path.startswith("/"):
            return None
        return self.safe_child(
            self.public_root, path[1:] + ("index.html" if path.endswith("/") else "")
        )

    def safe_child(self, root: Path, relative: str) -> Path | None:
        # Dotfiles, traversal and escaping symlinks are never implicitly public.
        if not relative or any(
            not part or part.startswith(".") or part == "endpoint.json"
            for part in relative.split("/")
        ):
            return None
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root.resolve()):
            return None
        if any(candidate.is_relative_to(private) for private in self.private_paths):
            return None
        return candidate

    @staticmethod
    async def respond(
        send: Any,
        status: int,
        body: bytes,
        content_type: str,
        headers: dict[str, str] | None = None,
        *,
        head: bool = False,
    ) -> None:
        response_headers = [
            (b"content-type", content_type.encode()),
            (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"),
            (b"x-content-type-options", b"nosniff"),
        ]
        response_headers.extend(
            (key.encode(), value.encode()) for key, value in (headers or {}).items()
        )
        await send({"type": "http.response.start", "status": status, "headers": response_headers})
        await send({"type": "http.response.body", "body": b"" if head else body})

    async def websocket(self, scope: JsonObject, receive: Any, send: Any) -> None:
        origin = next(
            (value.decode() for key, value in scope.get("headers", []) if key == b"origin"), None
        )
        if scope.get("path") != "/ws" or (origin is not None and origin not in self.origins):
            await send(
                {"type": "websocket.close", "code": 1008, "reason": "Forbidden endpoint or origin"}
            )
            return
        connection = None
        try:
            if (await receive()).get("type") != "websocket.connect":
                raise ValueError("Expected a WebSocket connection")
            await send({"type": "websocket.accept"})
            connection = Connection(
                lambda value: send(
                    {"type": "websocket.send", "text": json_bytes(value).decode("utf-8")}
                )
            )
            first = await asyncio.wait_for(receive(), timeout=5)
            if first.get("type") != "websocket.receive":
                raise ValueError("Expected authentication hello")
            await self.backend.authenticate(connection, parse_frame(first.get("text")))
            while True:
                message = await receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("type") != "websocket.receive":
                    raise ValueError("Expected a text frame")
                if not await self.backend.packet(connection, parse_frame(message.get("text"))):
                    await send({"type": "websocket.close", "code": 1000})
                    break
        except Exception:
            # Never include raw frames, credentials, filesystem paths or arbitrary
            # transport exception strings in remote diagnostics.
            await self.backend.emit(
                connection,
                {
                    "type": "error",
                    "code": "protocol",
                    "message": "Authentication or protocol failure",
                },
            )
            try:
                await send({"type": "websocket.close", "code": 1008, "reason": "Protocol failure"})
            except Exception:
                pass  # The peer may already have closed its socket.
        finally:
            if connection is not None:
                await self.backend.disconnected(connection)
