"""Exercise real subprocess lock handoff and private socket I/O with a disposable host."""

import asyncio
import json
import os
import select
import shlex
import signal
import socket
import stat
import subprocess
import sys
import time
from contextlib import ExitStack, closing, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from automata.tools.web import server
from automata.tools.web.server import ServerError, endpoint_for, find_or_start

_SECRET = "disposable-fixture-admission"
_SCRIPT = Path(__file__).resolve()


class Refusal(Exception):
    code = "capacity"


class FixtureHost:
    def __init__(self, *, port):
        self.port = port
        self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sessions = []

    async def start(self, *, cwd, create_initial):
        assert not create_initial
        self.cwd = cwd
        await asyncio.sleep(0.1)  # There is a real lock-held, socket-not-yet-bound window.
        self.tcp.bind(("127.0.0.1", self.port))
        self.tcp.listen()
        self.runtime = SimpleNamespace(origin=f"http://127.0.0.1:{self.tcp.getsockname()[1]}")
        self.event("start", os.getpid())

    def event(self, event, *values):
        with (self.cwd / "events.jsonl").open("a") as journal:
            journal.write(json.dumps([event, *values]) + "\n")

    async def admit_session(self, *, provider, model, thinking):
        if model == "slow":
            self.event("dispatched")
            await asyncio.sleep(0.25)
        if model == "error":
            raise RuntimeError(_SECRET)
        if len(self.sessions) == 4:
            raise Refusal(_SECRET)
        ident = f"session-{os.getpid()}-{len(self.sessions)}"
        self.sessions.append(ident)
        self.event("create", ident, provider, model, thinking)
        return SimpleNamespace(
            session_id=ident,
            url=f"{self.runtime.origin}/chat/sessions/{ident}/#admission={_SECRET}",
        )

    async def wait_for_pair(self, session_id, *, timeout):
        assert timeout == 0
        return session_id in self.sessions and (self.cwd / f"connected-{session_id}").exists()

    async def close(self):
        if hasattr(self, "runtime"):
            self.event("close", os.getpid())
        self.tcp.close()


def _spawn_fixture(endpoint, port, fd):
    return subprocess.Popen(
        [sys.executable, str(_SCRIPT), "daemon", str(fd), str(port), str(endpoint.project)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
        pass_fds=(fd,),
    )


def _reap(child, *, crash=False):
    if child.poll() is None:
        child.send_signal(signal.SIGKILL if crash else signal.SIGTERM)
    try:
        _, stderr = child.communicate(timeout=4)
    except subprocess.TimeoutExpired:
        child.kill()
        child.communicate(timeout=4)
        raise
    if stderr is not None:
        assert _SECRET.encode() not in stderr
    return child.returncode


def _launch(project, barrier):
    """Independent launcher process; hold its exact daemon Popen for cleanup."""
    children = []

    def spawn(*args):
        child = _spawn_fixture(*args)
        children.append(child)
        return child

    original = server._spawn
    server._spawn = spawn
    crash = False
    try:
        deadline = time.monotonic() + 10
        while not barrier.exists():
            if time.monotonic() >= deadline:
                raise TimeoutError
            time.sleep(0.01)
        endpoint = find_or_start(project)
        print(json.dumps([endpoint.port, [child.pid for child in children]]), flush=True)
        crash = sys.stdin.readline().strip() == "crash"
    finally:
        server._spawn = original
        for child in children:
            _reap(child, crash=crash)


@pytest.fixture
def project(tmp_path, monkeypatch):
    # A short owned location is needed for Linux sockaddr_un's 107-byte limit.
    with TemporaryDirectory(prefix="aw-") as runtime:
        monkeypatch.setenv("XDG_RUNTIME_DIR", runtime)
        yield tmp_path


@pytest.fixture
def fixture_children(monkeypatch, project):
    children = []

    def spawn(*args):
        child = _spawn_fixture(*args)
        children.append(child)
        return child

    monkeypatch.setattr(server, "_spawn", spawn)
    try:
        yield children
    finally:
        for child in children:
            _reap(child)


def _events(project):
    path = project / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


@contextmanager
def _reason(code):
    with pytest.raises(ServerError) as error:
        yield error
    assert error.value.code == code


def test_concurrent_launcher_processes_reuse_one_listener_and_recover_a_crash(project):
    launchers = []
    barrier = project / "go"
    endpoint = endpoint_for(project)
    try:
        for _ in range(8):
            launchers.append(
                subprocess.Popen(
                    [sys.executable, str(_SCRIPT), "launcher", str(project), str(barrier)],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            )
        barrier.touch()
        answers = []
        for launcher in launchers:
            assert select.select([launcher.stdout], [], [], 9)[0], "launcher did not become ready"
            answers.append(json.loads(launcher.stdout.readline()))
        ports = {port for port, _ in answers}
        owners = [(index, pids) for index, (_, pids) in enumerate(answers) if pids]
        assert len(ports) == len(owners) == 1
        index, pids = owners[0]
        assert len(pids) == 1
        assert _events(project) == [["start", pids[0]]]
        assert find_or_start(project).port in ports
        assert stat.S_IMODE(endpoint.socket_path.lstat().st_mode) == 0o600
        assert stat.S_IMODE(endpoint.socket_path.parent.lstat().st_mode) == 0o700
        lock = endpoint.socket_path.with_suffix(".lock")
        lock_inode = lock.stat().st_ino
        assert stat.S_IMODE(lock.stat().st_mode) == 0o600
        # A SIGKILL cannot unlink its socket, but also cannot keep the lock alive.
        _, stderr = launchers[index].communicate("crash\n", timeout=6)
        assert launchers[index].returncode == 0, stderr
        assert endpoint.socket_path.exists()
        with _reason("not_running"):
            endpoint.new_session()
    finally:
        for launcher in launchers:
            if launcher.poll() is None:
                # Closing stdin also asks the launcher to reap any daemon it owns.
                _, stderr = launcher.communicate("stop\n", timeout=20)
                assert launcher.returncode == 0, stderr

    # An independent launcher removes the stale inode under the same stable lock.
    with subprocess.Popen(
        [sys.executable, str(_SCRIPT), "launcher", str(project), str(barrier)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as restarted:
        stdout, stderr = restarted.communicate("stop\n", timeout=20)
        assert restarted.returncode == 0, stderr
    _, [new_pid] = json.loads(stdout)
    assert _events(project) == [["start", pids[0]], ["start", new_pid], ["close", new_pid]]
    assert not endpoint.socket_path.exists()
    assert lock.stat().st_ino == lock_inode


def test_checkout_aliases_share_the_endpoint_but_other_directories_do_not(project):
    first, other, alias = (project / name for name in ("first", "other", "alias"))
    first.mkdir()
    other.mkdir()
    alias.symlink_to(first, target_is_directory=True)
    assert endpoint_for(first) == endpoint_for(alias)
    assert endpoint_for(first).socket_path != endpoint_for(other).socket_path
    assert not endpoint_for(first).socket_path.parent.exists()
    with _reason("invalid_request"):
        endpoint_for(project / "missing")


def test_local_create_has_per_invocation_selections_and_status_only_reads(
    project, fixture_children
):
    endpoint = find_or_start(project)
    with _reason("native_unavailable") as error:
        endpoint.new_session(model="error")
    assert _SECRET not in str(error.value)
    with _reason("invalid_request"):
        endpoint.new_session(provider="--no-session")
    first = endpoint.new_session(provider="fixture", model="a/b", thinking="high")
    assert _SECRET in first.url and _SECRET not in repr(first)
    assert not endpoint.wait_connected(first.session_id, timeout=0.08)
    (project / f"connected-{first.session_id}").touch()
    assert endpoint.wait_connected(first.session_id, timeout=1)
    with _reason("port_mismatch"):
        find_or_start(project, port=2 if endpoint.port == 1 else 1)
    assert find_or_start(project, port=endpoint.port) == endpoint
    additional = [endpoint.new_session() for _ in range(3)]
    assert len({first.session_id, *(item.session_id for item in additional)}) == 4
    with _reason("capacity") as error:
        endpoint.new_session()
    assert _SECRET not in str(error.value)
    assert endpoint.wait_connected(first.session_id, timeout=1)
    assert _events(project) == [
        ["start", fixture_children[0].pid],
        ["create", first.session_id, "fixture", "a/b", "high"],
        *[["create", item.session_id, None, None, None] for item in additional],
    ]


def test_uncertain_create_timeout_does_not_replay(project, fixture_children, monkeypatch):
    endpoint = find_or_start(project)
    monkeypatch.setattr(server, "_SESSION_SECONDS", 0.1)
    with _reason("request_timeout"):
        endpoint.new_session(model="slow")
    deadline = time.monotonic() + 2
    while len(_events(project)) < 3 and time.monotonic() < deadline:
        time.sleep(0.02)
    assert [event[0] for event in _events(project)] == ["start", "dispatched", "create"]
    assert len(fixture_children) == 1


def _raw(endpoint, payload):
    with closing(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)) as client:
        client.settimeout(4)
        client.connect(str(endpoint.socket_path))
        client.sendall(payload)
        return json.loads(client.makefile("rb").readline(4097))


def test_socket_rejects_public_requests_and_unrecognized_or_oversized_frames(
    project, fixture_children
):
    endpoint = find_or_start(project)
    key = endpoint._key

    def record(**fields):
        return (
            json.dumps({"version": 1, "project": key, "op": "create", **fields}) + "\n"
        ).encode()

    def check(data, code):
        assert _raw(endpoint, data) == {"version": 1, "project": key, "error": code}

    check(b"POST /sessions HTTP/1.1\r\n\r\n", "invalid_request")
    check(b"X" * 4097 + b"\n", "invalid_request")
    check(b'{"op":"create","op":"ping"}\n', "invalid_request")
    check(record(pi=_SECRET), "invalid_request")
    check(record(version=True), "incompatible")
    check(record(version=2), "incompatible")
    check(record(project="different"), "incompatible")
    assert _raw(endpoint, record(op="ping"))["result"] == {"port": endpoint.port}
    assert len(_events(project)) == 1


def test_connection_limit_refuses_new_requests_until_idle_clients_close(project, fixture_children):
    endpoint = find_or_start(project)
    ping = json.dumps({"version": 1, "project": endpoint._key, "op": "ping"}).encode() + b"\n"
    with ExitStack() as idle:
        for _ in range(32):
            peer = idle.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
            peer.settimeout(2)
            peer.connect(str(endpoint.socket_path))
        assert _raw(endpoint, ping)["error"] == "busy"
    assert find_or_start(project) == endpoint
    assert len(fixture_children) == 1 and len(_events(project)) == 1


def test_absent_listener_with_owned_lock_times_out_without_a_second_spawn(
    project, fixture_children, monkeypatch
):
    monkeypatch.setattr(server, "_START_SECONDS", 0.13)
    endpoint = endpoint_for(project)
    lock = server._private_namespace(endpoint, create=True)
    fd = server._try_lock(lock)
    assert fd is not None
    try:
        before = time.monotonic()
        with _reason("startup_timeout"):
            find_or_start(project)
        assert time.monotonic() - before < 1
    finally:
        os.close(fd)
    assert fixture_children == []


def test_unmanaged_unix_socket_is_not_adopted_or_removed(project, fixture_children):
    endpoint = endpoint_for(project)
    server._private_namespace(endpoint, create=True)
    with closing(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)) as unmanaged:
        unmanaged.bind(str(endpoint.socket_path))
        endpoint.socket_path.chmod(0o600)
        unmanaged.listen()
        inode = endpoint.socket_path.stat()
        with _reason("incompatible"):
            find_or_start(project)
        assert os.path.samestat(inode, endpoint.socket_path.stat())
    assert fixture_children == []


def test_busy_legacy_tcp_listener_is_not_reused_or_stopped(project, fixture_children):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as legacy:
        legacy.bind(("127.0.0.1", 0))
        legacy.listen()
        legacy.settimeout(1)
        with _reason("startup_failed"):
            find_or_start(project, port=legacy.getsockname()[1])
        with socket.create_connection(legacy.getsockname(), timeout=1), closing(legacy.accept()[0]):
            pass
        assert not endpoint_for(project).socket_path.exists()
    assert len(fixture_children) == 1


def test_refuses_unsafe_runtime_namespace_files_and_symlinks(project, fixture_children):
    endpoint = endpoint_for(project)
    namespace = endpoint.socket_path.parent.parent
    namespace.symlink_to(project, target_is_directory=True)
    with _reason("runtime_unavailable"):
        find_or_start(project)
    assert namespace.is_symlink()
    namespace.unlink()
    lock = server._private_namespace(endpoint, create=True)
    victim = project / "keep"
    victim.write_text("keep")
    lock.symlink_to(victim)
    with _reason("runtime_unavailable"):
        find_or_start(project)
    assert lock.is_symlink()
    lock.unlink()
    endpoint.socket_path.symlink_to(victim)
    with _reason("incompatible"):
        find_or_start(project)
    assert endpoint.socket_path.is_symlink()
    assert victim.read_text() == "keep"
    assert fixture_children == []


def _fake_pi():
    """Native JSONL fixture only; never read personal Pi state or call a provider."""
    ident = f"fixture-{os.getpid()}"
    ledger = Path("rpc-workers.jsonl")

    def mark(event):
        with ledger.open("a") as out:
            out.write(json.dumps([event, ident]) + "\n")

    mark("start")
    try:
        for line in sys.stdin:
            request = json.loads(line)
            kind = request["type"]
            if kind == "get_state":
                data = {
                    "sessionId": ident,
                    "sessionFile": str(Path(f"{ident}.jsonl").resolve()),
                    "isStreaming": False,
                    "isCompacting": False,
                    "pendingMessageCount": 0,
                }
            elif kind == "get_messages":
                data = {"messages": []}
            elif kind in {"abort", "clear_queue"}:
                data = {}
            else:
                raise AssertionError("Unexpected fixture RPC command")
            print(
                json.dumps(
                    {"id": request["id"], "type": "response", "success": True, "data": data}
                ),
                flush=True,
            )
    finally:
        mark("close")


def test_real_managed_host_pairs_a_writer_and_never_evicts_it(project, monkeypatch):
    pytest.importorskip("automata_web_runtime")
    httpx = pytest.importorskip("httpx")
    ws = pytest.importorskip("websockets.asyncio.client")
    from automata.tools.web.host import BrowserHost

    if not hasattr(BrowserHost, "admit_session"):
        pytest.skip("Exercise after integrating the BrowserHost adapter")

    # Start the production daemon entry point and actual HTTP listener. Only the
    # native executable is replaced, with a PATH entry private to this test.
    bin_dir = project / "bin"
    bin_dir.mkdir()
    pi = bin_dir / "pi"
    pi.write_text(
        f"#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(_SCRIPT))} fake-pi\n"
    )
    pi.chmod(0o700)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(project / "agent"))
    monkeypatch.delenv("PI_SESSION_FILE", raising=False)
    owned = []
    spawn = server._spawn

    def track(*args):
        child = spawn(*args)
        owned.append(child)
        return child

    monkeypatch.setattr(server, "_spawn", track)
    try:
        endpoint = find_or_start(project)
        assert not (project / "rpc-workers.jsonl").exists()  # Listener-only startup.
        first = endpoint.new_session()
        assert not endpoint.wait_connected(first.session_id, timeout=0.12)

        async def pair():
            parts = urlsplit(first.url)
            connection = parts.path.rstrip("/") + "/chat/connection"
            origin = f"{parts.scheme}://{parts.netloc}"
            private = {"Authorization": "Bearer " + parts.fragment.removeprefix("admission=")}
            async with httpx.AsyncClient(
                base_url=origin, headers={"Origin": origin, "User-Agent": "Automata/1.0"}, timeout=2
            ) as client:
                assert (await client.post(connection)).status_code == 403
                ticket = (await client.post(connection, headers=private)).json()["ticket"]
                base = "ws://" + parts.netloc
                options = {"origin": origin, "open_timeout": 2, "user_agent_header": "Automata/1.0"}
                async with (
                    ws.connect(f"{base}/ws?token={ticket}", **options),
                    ws.connect(f"{base}{parts.path}chat?token={ticket}", **options) as chat,
                ):
                    await asyncio.wait_for(chat.recv(), 2)
                    assert await asyncio.to_thread(endpoint.wait_connected, first.session_id)
                    others = await asyncio.gather(
                        *(asyncio.to_thread(endpoint.new_session) for _ in range(3))
                    )
                    assert len({first.session_id, *(item.session_id for item in others)}) == 4
                    with _reason("capacity"):
                        await asyncio.to_thread(endpoint.new_session)
                    assert await asyncio.to_thread(endpoint.wait_connected, first.session_id)
                    response = await client.post(connection, headers=private)
                    assert (
                        response.status_code == 409 and response.json()["code"] == "writer_active"
                    )

        asyncio.run(pair())
    finally:
        for child in owned:
            assert _reap(child) == 0
    assert not endpoint.socket_path.exists()
    rows = [json.loads(line) for line in (project / "rpc-workers.jsonl").read_text().splitlines()]
    started = {ident for event, ident in rows if event == "start"}
    closed = {ident for event, ident in rows if event == "close"}
    assert len(started) == 4 and closed == started


if __name__ == "__main__":
    mode, *args = sys.argv[1:]
    if mode == "daemon":
        fd, port, project = args
        try:
            server._run_daemon(int(fd), int(port), Path(project), host_factory=FixtureHost)
        except OSError:
            sys.exit(1)
    elif mode == "launcher":
        _launch(*(Path(arg) for arg in args))
    elif mode == "fake-pi":
        _fake_pi()
    else:
        sys.exit(2)
