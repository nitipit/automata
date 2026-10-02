"""Opt-in local auth state and origin/lifecycle boundaries; no actual user state."""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[4] / "src/automata/tools/message-router"))
from automata_router.auth import SessionAuth  # noqa: E402
from automata_router.auth_store import AuthStore, digest  # noqa: E402
from automata_router.router import Router, validate_config  # noqa: E402
from automata_router.server import RouterApp  # noqa: E402


def test_private_hashed_single_use_bounded_state_and_restart(tmp_path):
    directory = tmp_path / "auth"
    store = AuthStore(directory, {"page"})
    try:
        code = store.pair_code("page")["code"]
        token, session = store.exchange(code)
        text = store.path.read_text()
        assert code not in text and token not in text
        assert digest(token) in text
        assert store.path.stat().st_mode & 0o777 == 0o600
        assert directory.stat().st_mode & 0o777 == 0o700
        with pytest.raises(ValueError):
            store.exchange(code)
        with pytest.raises(ValueError):
            store.pair_code("agent")
        another = store.pair_code("page")["code"]
        for _ in range(5):
            with pytest.raises(ValueError):
                store.exchange("wrong")
        with pytest.raises(ValueError):
            store.exchange(another)
        with pytest.raises(BlockingIOError):
            AuthStore(directory, {"page"})
    finally:
        store.close()
    recovered = AuthStore(directory, {"page"})
    try:
        assert recovered.session(token) == session
        assert recovered.revoke(session_id=session["id"]) == [session["id"]]
        assert recovered.session(token) is None
        expired = recovered.pair_code("page")["code"]
        recovered.state["codes"][digest(expired)]["expiresAt"] = time.time() - 1
        with pytest.raises(ValueError):
            recovered.exchange(expired)
    finally:
        recovered.close()


@pytest.mark.parametrize("text", ['{"v":1,"codes":{},"sessions":{},"v":1}',
    '{"v":1,"codes":{},"sessions":{"bad":{}}}', 'not-json',
    '{"v":1,"codes":{},"sessions":{},"extra":true}'])
def test_malformed_state_never_silently_resets(tmp_path, text):
    directory = tmp_path / "auth"
    directory.mkdir(mode=0o700)
    state = directory / "state.json"
    state.write_text(text)
    state.chmod(0o600)
    with pytest.raises(ValueError, match="malformed"):
        AuthStore(directory, {"page"})
    assert state.read_text() == text


def test_cookie_origin_host_and_revoke_idle_event(tmp_path):
    async def check():
        store = AuthStore(tmp_path / "auth", {"page"})
        auth = SessionAuth(store, "http://127.0.0.1:8787")
        try:
            token, session = store.exchange(store.pair_code("page")["code"])
            scope = {"headers": [(b"host", b"127.0.0.1:8787"),
                       (b"origin", b"http://127.0.0.1:8787"),
                       (b"cookie", f"automata_router_session={token}".encode())]}
            assert auth.session(scope) == session
            for header in ([(b"host", b"localhost:8787")],
                           [(b"host", b"127.0.0.1:8788"), (b"origin", b"http://127.0.0.1:8787")],
                           [(b"host", b"127.0.0.1:8787")],
                           [(b"host", b"127.0.0.1:8787"), (b"origin", b"http://evil.test")]):
                with pytest.raises(ValueError):
                    auth.session({"headers": header})
            assert "HttpOnly" in auth.cookie(token) and "SameSite=Strict" in auth.cookie(token)
            assert "Secure" not in auth.cookie(token) and "Domain=" not in auth.cookie(token)
            event, release = auth.watch(session)
            assert auth.revoke(participant="page") == 1
            await asyncio.wait_for(event.wait(), 1)
            release()
            assert not auth.watchers
            expiry, release = auth.watch({**session, "expiresAt": time.time() + .01})
            await asyncio.wait_for(expiry.wait(), 1)
            release()
            with pytest.raises(ValueError):
                auth.session(scope)
        finally:
            await auth.close()
    asyncio.run(check())


def test_public_overlap_and_symlink_excluded(tmp_path):
    config = {"v": 1, "participants": {"page": {"kind": "page", "token": "p" * 32, "allow": []}}}
    backend = Router(validate_config(config), public_url="http://127.0.0.1:8787")
    public = tmp_path / "public"
    public.mkdir()
    store = AuthStore(tmp_path / "auth", {"page"})
    auth = SessionAuth(store, backend.public_url)
    try:
        (public / "private").symlink_to(store.path)
        app = RouterApp(backend, public_root=public, auth=auth)
        assert app.public_path("/private") is None
        with pytest.raises(ValueError, match="overlap"):
            RouterApp(backend, public_root=tmp_path, auth=auth)
    finally:
        store.close()


def test_control_collision_not_deleted(tmp_path):
    async def check():
        store = AuthStore(tmp_path / "auth", {"page"})
        auth = SessionAuth(store, "http://127.0.0.1:8787")
        auth.control_path.write_text("not a socket")
        try:
            with pytest.raises(ValueError, match="collision"):
                await auth.start()
            assert auth.control_path.read_text() == "not a socket"
        finally:
            await auth.close()
    asyncio.run(check())


def test_auth_capacity_pruning_and_duplicate_session_state(tmp_path, monkeypatch):
    import automata_router.auth_store as module
    monkeypatch.setattr(module, "MAX_CODES", 1)
    monkeypatch.setattr(module, "MAX_SESSIONS", 1)
    store = AuthStore(tmp_path / "auth", {"page"})
    try:
        code = store.pair_code("page")["code"]
        with pytest.raises(ValueError, match="capacity"):
            store.pair_code("page")
        token, _ = store.exchange(code)
        another = store.pair_code("page")["code"]
        with pytest.raises(ValueError, match="capacity"):
            store.exchange(another)
        store.state["sessions"][digest(token)]["expiresAt"] = time.time() - 1
        replacement, _ = store.exchange(another)
        assert store.session(replacement)
        assert len(store.state["sessions"]) == 1
        # Malformed persisted duplicate IDs must not combine revocation domains.
        monkeypatch.setattr(module, "MAX_SESSIONS", 128)
        store.state["sessions"]["f" * 64] = {**store.session(replacement)}
        store.save()
    finally:
        store.close()
    with pytest.raises(ValueError, match="malformed"):
        AuthStore(tmp_path / "auth", {"page"})
    assert len(json.loads((tmp_path / "auth/state.json").read_text())["sessions"]) == 2


def test_persistence_failure_closes_auth_domain_and_signals_idle_socket(tmp_path, monkeypatch):
    async def check():
        store = AuthStore(tmp_path / "auth", {"page"})
        auth = SessionAuth(store, "http://127.0.0.1:8787")
        token, session = store.exchange(store.pair_code("page")["code"])
        event, release = auth.watch(session)
        def fail():
            raise OSError("synthetic disk failure; never forwarded")
        monkeypatch.setattr(store, "save", fail)
        scope = {"path": "/session/logout", "method": "POST", "headers": [
            (b"host", b"127.0.0.1:8787"), (b"origin", b"http://127.0.0.1:8787"),
            (b"content-type", b"application/json"),
            (b"cookie", f"automata_router_session={token}".encode())]}
        replies = []
        async def receive():
            return {"type": "http.request", "body": b"{}"}
        async def send(packet):
            replies.append(packet)
        try:
            await auth.http(scope, receive, send, RouterApp.respond)
            assert replies[0]["status"] == 503
            assert b"synthetic" not in replies[1]["body"]
            await asyncio.wait_for(event.wait(), 1)
            with pytest.raises(ValueError):
                auth.authorize_origin(scope, mandatory=True)
        finally:
            release()
            await auth.close()
    asyncio.run(check())


def test_ordinary_import_without_unix_locks_and_explicit_opt_in_error(tmp_path):
    source = Path(__file__).parents[4] / "src/automata/tools/message-router"
    result = subprocess.run([sys.executable, "-c", '''
import builtins, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
original = builtins.__import__
def without_fcntl(name, *args, **kwargs):
    if name == "fcntl":
        raise ImportError("synthetic non-Unix platform")
    return original(name, *args, **kwargs)
builtins.__import__ = without_fcntl
import automata_router.server
from automata_router.auth_store import AuthStore
try:
    AuthStore(Path(sys.argv[2]), {"page"})
except ValueError as error:
    assert "requires Unix" in str(error)
else:
    raise AssertionError("Unsupported opt-in auth must fail visibly")
assert not Path(sys.argv[2]).exists()
''', str(source), str(tmp_path / "auth")], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
