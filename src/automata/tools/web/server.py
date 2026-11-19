"""Find or start one managed Web UI listener per canonical checkout on Linux.

The control socket is private to the effective user. Neither a browser request
nor a legacy HTTP listener can acquire the launcher role. The caller owns browser
opening; only the server owns its listener and native Pi workers.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import fcntl
import hashlib
import math
import os
import signal
import socket
import stat
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from automata.tools.web.server_control import (
    Admission,
    Control,
    ServerError,
    admission_from,
    exchange,
    selection,
    socket_info,
    valid_id,
)

_SOCKET_NAME = "web-ui-server.sock"
_LOCK_NAME = "web-ui-server.lock"
_START_SECONDS = 15
_PING_SECONDS = 0.5
_POLL_SECONDS = 0.05
_SESSION_SECONDS = 55
_START_TRANSIENT = frozenset({"not_running", "busy", "request_timeout", "server_unavailable"})


@dataclass(frozen=True)
class ServerEndpoint:
    """Nonsecret information about the managed host's local control endpoint."""

    project: Path
    socket_path: Path
    _key: str = field(repr=False)
    port: int | None = None

    def new_session(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        thinking: str | None = None,
    ) -> Admission:
        """Request one fresh Pi session. Never retry a dispatched create automatically."""
        options = selection({"provider": provider, "model": model, "thinking": thinking})
        result = exchange(
            self.socket_path, self._key, "create", timeout=_SESSION_SECONDS, **options
        )
        return admission_from(result)

    def wait_connected(self, session_id: str, *, timeout: float = 15) -> bool:
        """Wait for the named session's paired writer, without creating or mutating it."""
        if (
            not valid_id(session_id)
            or type(timeout) not in (int, float)
            or not 0 <= timeout <= 300
            or not math.isfinite(timeout)
        ):
            raise ServerError("invalid_request")
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                result = exchange(
                    self.socket_path,
                    self._key,
                    "connected",
                    timeout=min(_PING_SECONDS, remaining),
                    session_id=session_id,
                )
            except ServerError as error:
                if error.code not in {"busy", "request_timeout"}:
                    raise
            else:
                if set(result) != {"connected"} or type(result["connected"]) is not bool:
                    raise ServerError("incompatible")
                if result["connected"]:
                    return True
            _pause(deadline)
        return False


def _private_dir(path, *, create=False):
    try:
        if create:
            path.mkdir(mode=0o700, exist_ok=True)
        info = path.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise ServerError("runtime_unavailable")
    except (OSError, ValueError):
        raise ServerError("runtime_unavailable") from None


def _runtime_root():
    if not hasattr(socket, "SO_PEERCRED"):
        raise ServerError("runtime_unavailable")
    root = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.geteuid()}")
    try:
        if not root.is_absolute() or root.resolve(strict=True) != root:
            raise ServerError("runtime_unavailable")
        _private_dir(root)
        for parent in root.parents:
            info = parent.lstat()
            if (
                not stat.S_ISDIR(info.st_mode)
                or info.st_uid not in {0, os.geteuid()}
                or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX)
            ):
                raise ServerError("runtime_unavailable")
    except (OSError, ValueError, RuntimeError):
        raise ServerError("runtime_unavailable") from None
    return root


def endpoint_for(project: Path) -> ServerEndpoint:
    """Resolve the caller-selected checkout path without making runtime artifacts.

    The CLI selects the Git worktree root (or launch directory outside Git).
    Symlink aliases share an identity, separately linked worktrees do not.
    """
    try:
        project = Path(project).resolve(strict=True)
        if not project.is_dir():
            raise ServerError("invalid_request")
    except (OSError, ValueError, RuntimeError, TypeError):
        raise ServerError("invalid_request") from None
    digest = hashlib.sha256(os.fsencode(project)).digest()
    key = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    path = _runtime_root() / "automata-web-ui" / key / _SOCKET_NAME
    if len(os.fsencode(path)) > 107:  # Linux sockaddr_un leaves one byte for NUL.
        raise ServerError("runtime_unavailable")
    return ServerEndpoint(project, path, key)


def _private_namespace(endpoint, *, create=False):
    directory = endpoint.socket_path.parent
    _private_dir(directory.parent, create=create)
    _private_dir(directory, create=create)
    return directory / _LOCK_NAME


def _verify_lock(fd, path):
    try:
        inode, named = os.fstat(fd), path.lstat()
    except OSError:
        raise ServerError("runtime_unavailable") from None
    if (
        not stat.S_ISREG(inode.st_mode)
        or inode.st_nlink != 1
        or stat.S_IMODE(inode.st_mode) != 0o600
        or inode.st_uid != os.geteuid()
        or not os.path.samestat(inode, named)
    ):
        raise ServerError("runtime_unavailable")


def _try_lock(path):
    # This inode is never replaced or unlinked. Closing the final copy of the
    # open file description releases the lock (an explicit LOCK_UN would also
    # release a newly spawned child's lock).
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            _verify_lock(fd, path)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                return None
            _verify_lock(fd, path)
            return fd
        except BaseException:
            os.close(fd)
            raise
    except OSError:
        raise ServerError("runtime_unavailable") from None


def _unlink_same(path, inode):
    """Unlink only the owned socket inode, not a replacement or another file."""
    current = socket_info(path)
    if current is None:
        return
    if not os.path.samestat(inode, current):
        raise ServerError("incompatible")
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        raise ServerError("incompatible") from None


def _clear_refused_socket(path):
    """Only under the lifetime lock: remove a private stale socket, not a live peer."""
    previous = socket_info(path)
    if previous is None:
        return
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
            peer.settimeout(_PING_SECONDS)
            peer.connect(os.fspath(path))
    except ConnectionRefusedError:
        _unlink_same(path, previous)
        return
    except FileNotFoundError:
        if socket_info(path) is None:
            return
    except OSError:
        pass
    raise ServerError("incompatible")


def _spawn(endpoint, port, fd):
    # Only a lock fd is inherited; no admission is put in argv, env or stdio.
    try:
        return subprocess.Popen(
            [sys.executable, "-m", __name__, str(fd), str(port), os.fspath(endpoint.project)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            pass_fds=(fd,),
        )
    except OSError:
        raise ServerError("startup_failed") from None


def _pause(deadline):
    time.sleep(min(_POLL_SECONDS, max(0, deadline - time.monotonic())))


def _probe(endpoint, port, deadline):
    try:
        result = exchange(
            endpoint.socket_path,
            endpoint._key,
            "ping",
            timeout=min(_PING_SECONDS, max(0, deadline - time.monotonic())),
        )
    except ServerError as error:
        if error.code in _START_TRANSIENT:
            return None
        raise
    actual = result.get("port")
    if set(result) != {"port"} or type(actual) is not int or not 1 <= actual <= 65535:
        raise ServerError("incompatible")
    if port and port != actual:
        raise ServerError("port_mismatch")
    return replace(endpoint, port=actual)


def find_or_start(project: Path, *, port: int = 0) -> ServerEndpoint:
    """Find the compatible endpoint or detach its server with a bounded readiness wait.

    Every prospective spawner opens the same lock inode. The winner hands off
    that *already locked* open file description in `pass_fds` and closes only
    its copy. The daemon keeps the lock through listener/worker shutdown. A
    loser can probe, but cannot unlink a socket or start a competing listener.
    """
    if type(port) is not int or not 0 <= port <= 65535:
        raise ServerError("invalid_request")
    endpoint = endpoint_for(project)
    lock = _private_namespace(endpoint, create=True)
    deadline = time.monotonic() + _START_SECONDS
    child = None
    while time.monotonic() < deadline:
        if child is None:
            fd = _try_lock(lock)
            if fd is not None:
                try:
                    _clear_refused_socket(endpoint.socket_path)
                    child = _spawn(endpoint, port, fd)
                finally:
                    os.close(fd)
        elif child.poll() is not None:
            raise ServerError("startup_failed")
        ready = _probe(endpoint, port, deadline)
        if ready is not None:
            return ready
        _pause(deadline)
    # Never signal a daemon here, even one we started: another launcher could
    # already have connected and own a writer. The server bounds its startup.
    raise ServerError("startup_timeout")


@contextlib.contextmanager
def _bound_control(path):
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    inode = None
    try:
        # Create the inode private from the first instant, including if the
        # daemon dies before listening. No await or worker launch under this mask.
        mask = os.umask(0o177)
        try:
            listener.bind(os.fspath(path))
        finally:
            os.umask(mask)
        inode = socket_info(path)
        if inode is None:
            raise ServerError("incompatible")
        listener.listen(32)
        listener.setblocking(False)
        yield listener
    finally:
        listener.close()
        if inode is not None:
            _unlink_same(path, inode)


async def _serve(endpoint, port, host_factory):
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stopped.set)
    host = host_factory(port=port)
    try:
        async with asyncio.timeout(10):
            await host.start(cwd=endpoint.project, create_initial=False)
        if stopped.is_set():
            return
        with _bound_control(endpoint.socket_path) as listener:
            control = Control(endpoint._key, host)
            try:
                await control.start(listener)
                await stopped.wait()
            finally:
                await control.close()
    finally:
        await host.close()


def _run_daemon(fd, port, project, host_factory=None):
    # Internal child entry point. Do not let a native worker inherit the lock.
    try:
        os.set_inheritable(fd, False)
        endpoint = endpoint_for(project)
        _verify_lock(fd, _private_namespace(endpoint))
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if host_factory is None:
            from automata.tools.web.host import BrowserHost

            host_factory = BrowserHost
        asyncio.run(_serve(endpoint, port, host_factory))
    finally:
        os.close(fd)


def _main():
    try:
        fd, port, project = sys.argv[1:]
        _run_daemon(int(fd), int(port), Path(project))
    except (Exception, KeyboardInterrupt):
        # Parent reports a fixed startup error; never dump a private traceback.
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
