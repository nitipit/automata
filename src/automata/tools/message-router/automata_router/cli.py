"""Explicit setup/serve/status and private endpoint-record ownership."""

from __future__ import annotations

import json
import os
import secrets
import signal
import socket
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from cyclopts import App, Parameter

from .auth import SessionAuth
from .auth_store import AuthStore
from .legacy import Broker
from .protocol import (
    MAX_FRAME_BYTES,
    SESSION_RE,
    reject_json_constant,
    strict_object_pairs,
    utc_now,
)
from .router import Router, validate_config
from .server import RouterApp

# Preserve the historical default: renaming the capability does not migrate credentials.
DEFAULT_STATE_ROOT = Path(
    os.environ.get(
        "AUTOMATA_MESSAGE_ROUTER_STATE",
        os.environ.get("AUTOMATA_AGENT_ROUTER_STATE", ".agents/var/tools/agent-router"),
    )
).expanduser()


def private_write(path: Path, value: Any) -> None:
    """Create exclusively with private permissions *before* writing credentials."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=True, indent=2) + "\n")


class EndpointRecords:
    def __init__(self, records: dict[Path, dict[str, Any]]):
        self.generation = str(uuid.uuid4())
        self.records = {
            path: {**value, "serverId": self.generation} for path, value in records.items()
        }
        self.created: list[Path] = []

    def create(self) -> None:
        try:
            for path, record in self.records.items():
                private_write(path, record)
                self.created.append(path)
        except OSError:
            self.cleanup()
            raise RuntimeError(
                "Refusing to overwrite endpoint records; inspect the existing owner first"
            ) from None

    def cleanup(self) -> None:
        for path in self.created:
            try:
                if json.loads(path.read_text()).get("serverId") == self.generation:
                    path.unlink()
            except (OSError, ValueError, AttributeError):
                pass
        self.created.clear()


class PublishedServer(uvicorn.Server):
    def __init__(self, config: uvicorn.Config, records: EndpointRecords):
        super().__init__(config)
        self.records = records

    async def startup(self, sockets: Any = None) -> None:
        await super().startup(sockets=sockets)
        if self.started:
            try:
                application = self.config.app
                if application.auth:
                    await application.auth.start()
                self.records.create()
            except Exception:
                await self.shutdown(sockets=sockets)
                raise


def run_server(application: RouterApp, records: EndpointRecords, port: int) -> None:
    server = PublishedServer(
        uvicorn.Config(
            application,
            host="127.0.0.1",
            port=port,
            lifespan="on",
            ws_max_size=MAX_FRAME_BYTES,
            log_level="warning",
        ),
        records,
    )
    previous = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}

    def stop(_signum: int, _frame: Any) -> None:
        server.should_exit = True

    for signum in previous:
        signal.signal(signum, stop)
    try:
        server.run()
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        records.cleanup()


def setup(
    *,
    config_file: Path = DEFAULT_STATE_ROOT / "config.json",
    agent: Annotated[
        list[str], Parameter(help="Agent participant ID; repeat for multiple agents.")
    ] = (),
    page: Annotated[
        list[str], Parameter(help="Page participant ID; repeat for multiple pages.")
    ] = (),
    allow: Annotated[
        list[str], Parameter(help="Directed source:destination grant; repeat as needed.")
    ] = (),
) -> None:
    """Create private grants; with no identities, create page→agent as the default pair."""
    if not agent and not page and not allow:
        agent, page, allow = ["agent"], ["page"], ["page:agent"]
    participants = {}
    for kind, identities in (("agent", agent), ("page", page)):
        for identity in identities:
            if identity in participants:
                raise ValueError("Participant IDs must be distinct")
            participants[identity] = {"kind": kind, "token": secrets.token_urlsafe(32), "allow": []}
    for grant in allow:
        source, separator, destination = grant.partition(":")
        if not separator or source not in participants or destination not in participants:
            raise ValueError("Each --allow must name configured source:destination participants")
        participants[source]["allow"].append(destination)
    config = {"v": 1, "participants": participants}
    validate_config(config)
    try:
        private_write(config_file, config)
    except FileExistsError:
        raise ValueError(
            "Configuration already exists; review/edit its grants explicitly"
        ) from None
    print(f"private configuration: {config_file}")
    print("setup complete; no server, agent, browser or public directories were created")


def serve(
    *,
    port: int = 8787,
    config_file: Path = DEFAULT_STATE_ROOT / "config.json",
    endpoint_dir: Path = DEFAULT_STATE_ROOT / "endpoints",
    public_root: Annotated[
        Path | None, Parameter(help="Optional directory containing public-safe files only.")
    ] = None,
    origin: Annotated[
        list[str], Parameter(help="Additional direct-token browser Origin; not cookie auth.")
    ] = (),
    auth_dir: Annotated[
        Path | None, Parameter(help="Opt-in private browser session/control directory (0700).")
    ] = None,
    session_seconds: int = 604800,
    pairing_seconds: int = 300,
) -> None:
    """Serve authorized participants; static hosting is optional and independent of UI choice."""
    if not 1 <= port <= 65535:
        raise ValueError("--port must be between 1 and 65535")
    config = json.loads(
        config_file.read_text(),
        object_pairs_hook=strict_object_pairs,
        parse_constant=reject_json_constant,
    )
    grants = validate_config(config)
    public_url = f"http://127.0.0.1:{port}"
    shared = {
        "v": 2,
        "wsUrl": f"ws://127.0.0.1:{port}/ws",
        "publicUrl": public_url,
        "pid": os.getpid(),
        "startedAt": utc_now(),
    }
    records = {endpoint_dir / "server.json": shared}
    for identity, grant in grants.items():
        records[endpoint_dir / "participants" / f"{identity}.json"] = {
            **shared,
            "participant": identity,
            "kind": grant.kind,
            "token": grant.token,
        }
    # Check public/private boundaries before creating any auth data.
    backend = Router(grants, public_url=public_url)
    private_paths = (config_file, endpoint_dir, *((auth_dir,) if auth_dir else ()))
    application = RouterApp(backend, public_root=public_root, private_paths=private_paths,
                            origins=tuple(origin))
    if auth_dir:
        pages = {name for name, grant in grants.items() if grant.kind == "page"}
        store = AuthStore(auth_dir, pages, session_seconds=session_seconds,
                          code_seconds=pairing_seconds)
        try:
            application.auth = SessionAuth(store, public_url)
        except Exception:
            store.close()
            raise
    try:
        run_server(application, EndpointRecords(records), port)
    finally:
        if application.auth:
            application.auth.store.close()


def status(*, endpoint_file: Path = DEFAULT_STATE_ROOT / "endpoints" / "server.json") -> None:
    """Inspect public health without printing participant credentials."""
    if not endpoint_file.is_file():
        print(json.dumps({"status": "stopped", "endpoint": str(endpoint_file)}))
        return
    try:
        record = json.loads(endpoint_file.read_text())
        with urllib.request.urlopen(f"{record['publicUrl']}/health", timeout=2) as response:
            health = json.loads(response.read())
    except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError):
        print(json.dumps({"status": "unreachable", "endpoint": str(endpoint_file)}))
        return
    print(json.dumps({**health, "endpoint": str(endpoint_file)}))


def legacy_serve(
    *,
    port: int = 8787,
    runtime_root: Path | None = None,
    session_id: str = "default",
    endpoint_file: Path = Path(".agents/var/tools/agent-browser-bridge/endpoint.json"),
) -> None:
    """Opt-in v1 single-pair compatibility; never implicitly creates Adaptive UI roots."""
    if not 1 <= port <= 65535 or not SESSION_RE.fullmatch(session_id):
        raise ValueError("Invalid port or legacy static session name")
    broker = Broker(public_url=f"http://127.0.0.1:{port}", session_id=session_id)
    roots = (runtime_root / "lib", runtime_root / "sessions") if runtime_root else None
    application = RouterApp(broker, private_paths=(endpoint_file,), legacy_roots=roots)
    run_server(
        application,
        EndpointRecords({endpoint_file: broker.endpoint(port=port, pid=os.getpid())}),
        port,
    )


def operator_request(auth_dir: Path, packet: dict[str, Any]) -> None:
    """Private local operator request; never route secrets through public HTTP."""
    if not hasattr(socket, "AF_UNIX"):
        raise ValueError("Local browser auth control requires Unix sockets")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        client.connect(str(auth_dir.resolve() / "control.sock"))
        client.sendall((json.dumps(packet) + "\n").encode())
        body = b""
        while b"\n" not in body:
            chunk = client.recv(1024)
            if not chunk or len(body) + len(chunk) > 4096:
                raise ValueError("Invalid private operator response")
            body += chunk
    result = json.loads(body)
    if not result.pop("ok", False):
        raise ValueError(result.get("error", "Private operator request failed"))
    print(json.dumps(result))


def pair(*, auth_dir: Path, participant: str) -> None:
    """Generate a single-use private page code on the running service. Keep output private."""
    operator_request(auth_dir, {"action": "pair", "participant": participant})


def approve_request(*, auth_dir: Path, request: str, participant: str) -> None:
    """Approve a public locator only on explicit user instruction, for an existing page."""
    operator_request(auth_dir, {"action": "approve-request", "request": request,
                                "participant": participant})


def request_status(*, auth_dir: Path, request: str) -> None:
    """Inspect volatile request state privately; a locator is not approval authority."""
    operator_request(auth_dir, {"action": "request-status", "request": request})


def cancel_request(*, auth_dir: Path, request: str) -> None:
    """Cancel this exact pending/approved request, never a browser session."""
    operator_request(auth_dir, {"action": "cancel-request", "request": request})


def revoke(*, auth_dir: Path, participant: str | None = None,
           session_id: str | None = None) -> None:
    """Revoke a page's sessions or one private session ID, including active sockets."""
    if (participant is None) == (session_id is None):
        raise ValueError("Choose exactly one --participant or --session-id")
    operator_request(auth_dir, {"action": "revoke", **(
        {"participant": participant} if participant is not None else {"sessionId": session_id}
    )})


app = App(name="message-router", help="Route bounded JSON between authorized pages and agents.")
app.command(setup)
app.command(serve)
app.command(status)
app.command(pair)
app.command(approve_request, name="approve-request")
app.command(request_status, name="request-status")
app.command(cancel_request, name="cancel-request")
app.command(revoke)
app.command(legacy_serve, name="legacy-serve")


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}")
        raise SystemExit(2) from None
