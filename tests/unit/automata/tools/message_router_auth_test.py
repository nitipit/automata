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


def request_fixture(tmp_path):
    from automata_router.auth_requests import PairingRequests
    store = AuthStore(tmp_path / "auth", {"page", "other"})
    requests = PairingRequests(store)
    requests.presence = lambda _: False
    return store, requests


def test_request_binding_transitions_duplicates_and_exact_expiry(tmp_path, monkeypatch):
    import automata_router.auth_requests as module
    store, requests = request_fixture(tmp_path)
    try:
        capability = "a" * 64
        created = requests.create(capability)
        locator = created["request"]
        assert requests.create(capability) == created
        assert capability not in json.dumps(requests.records)
        assert digest(capability) in json.dumps(requests.records)
        assert "capability" not in created
        for method in (requests.status, requests.cancel, requests.redeem):
            with pytest.raises(ValueError):
                method(locator, "b" * 64)
            with pytest.raises(ValueError):
                method(locator, locator)
        with pytest.raises(ValueError):
            requests.redeem(locator, capability)
        for participant in ("agent", "missing"):
            with pytest.raises(ValueError):
                requests.approve(locator, participant)
        approved = requests.approve(locator, "page")
        assert requests.approve(locator, "page") == approved
        assert approved["expiresAt"] == created["expiresAt"]
        with pytest.raises(ValueError):
            requests.approve(locator, "other")
        token, session = requests.redeem(locator, capability)
        assert store.session(token) == session
        assert requests.lookup(locator)["state"] == "redeemed"
        for method, args in ((requests.redeem, (locator, capability)),
                             (requests.cancel, (locator, capability)),
                             (requests.approve, (locator, "page"))):
            with pytest.raises(ValueError):
                method(*args)
        assert len(store.state["sessions"]) == 1
        second = requests.create("c" * 64)
        requests.approve(second["request"], "other")
        assert requests.cancel(second["request"], "c" * 64)["state"] == "cancelled"
        assert requests.cancel(second["request"], "c" * 64)["state"] == "cancelled"
        with pytest.raises(ValueError):
            requests.approve(second["request"], "other")
        third = requests.create("d" * 64)
        monkeypatch.setattr(module.time, "time", lambda: third["expiresAt"])
        assert requests.lookup(third["request"])["state"] == "expired"
        with pytest.raises(ValueError):
            requests.approve(third["request"], "other")
        assert requests.lookup(second["request"])["state"] == "cancelled"
    finally:
        store.close()


def test_request_exclusivity_reservation_and_presence_fail_closed(tmp_path):
    store, requests = request_fixture(tmp_path)
    try:
        one = requests.create("a" * 64)["request"]
        two = requests.create("b" * 64)["request"]
        def broken(_):
            raise RuntimeError("unavailable")
        for callback in (None, broken, lambda _: None, lambda _: 0, lambda _: True):
            requests.presence = callback
            with pytest.raises(ValueError):
                requests.approve(one, "page")
            assert requests.lookup(one)["state"] == "pending"
        requests.presence = lambda _: False
        requests.approve(one, "page")
        with pytest.raises(ValueError):
            requests.approve(two, "page")
        for callback in (None, broken, lambda _: [], lambda _: True):
            requests.presence = callback
            with pytest.raises(ValueError):
                requests.redeem(one, "a" * 64)
            assert requests.lookup(one)["state"] == "approved"
            assert not store.state["sessions"]
        requests.presence = lambda _: False
        token, _ = store.exchange(store.pair_code("page")["code"])
        with pytest.raises(ValueError):
            requests.redeem(one, "a" * 64)
        assert store.session(token)  # no takeover, revoke or replacement
        with pytest.raises(ValueError):
            requests.approve(two, "page")
        store.revoke(token=token)
        requests.cancel(one, "a" * 64)
        requests.approve(two, "page")
        requests.redeem(two, "b" * 64)
        assert len(store.state["sessions"]) == 1
    finally:
        store.close()


def test_request_budgets_capacity_and_restart_are_bounded(tmp_path, monkeypatch):
    import automata_router.auth_requests as module
    store, requests = request_fixture(tmp_path)
    try:
        monkeypatch.setattr(module, "MAX_REQUESTS", 2)
        one = requests.create("a" * 64)
        requests.cancel(one["request"], "a" * 64)
        two = requests.create("b" * 64)
        with pytest.raises(module.RequestLimit):
            requests.create("c" * 64)
        assert requests.create("b" * 64) == two
        requests.status(two["request"], "b" * 64)
        with pytest.raises(module.RequestLimit):
            requests.status(two["request"], "b" * 64)
        requests.creation.tokens = 0
        with pytest.raises(module.RequestLimit):
            requests.create("d" * 64)
        requests.operations.tokens = 0
        with pytest.raises(module.RequestLimit):
            requests.operations.take()
        restarted = module.PairingRequests(store)
        with pytest.raises(ValueError):
            restarted.lookup(two["request"])
        assert not restarted.records
        assert json.loads(store.path.read_text()) == {"v": 1, "codes": {}, "sessions": {}}
    finally:
        store.close()


def test_request_cookie_guard_and_constructor_late_presence_wiring(tmp_path):
    from automata_router.auth_request_http import request_packet
    config = {"v": 1, "participants": {
        page: {"kind": "page", "token": char * 32, "allow": []}
        for page, char in (("page", "p"), ("other", "o"))}}
    backend = Router(validate_config(config), public_url="http://127.0.0.1:8787")
    store = AuthStore(tmp_path / "auth", {"page", "other"})
    auth = SessionAuth(store, backend.public_url)
    try:
        app = RouterApp(backend, auth=auth)
        assert auth.requests.presence("page") is False
        app.auth = SessionAuth(store, backend.public_url)  # actual CLI attachment path
        auth = app.auth
        backend.peers["page"] = object()
        assert auth.requests.presence("page") is True
        backend.peers.clear()
        locator = auth.requests.create("a" * 64)["request"]
        auth.requests.approve(locator, "page")
        old_token, old_session = store.exchange(store.pair_code("other")["code"])
        packet = {"request": locator, "capability": "a" * 64}
        headers = {"cookie": f"automata_router_session={old_token}"}
        with pytest.raises(ValueError, match="Forget"):
            request_packet(auth, "/session/request-redeem", packet, headers)
        assert len(store.state["sessions"]) == 1 and store.session(old_token) == old_session
        assert auth.requests.lookup(locator)["state"] == "approved"
        store.revoke(token=old_token)
        result, token = request_packet(auth, "/session/request-redeem", packet, {})
        assert result["authenticated"] and store.session(token)["participant"] == "page"
    finally:
        store.close()


def test_request_http_strict_inputs_and_persistence_failure(tmp_path, monkeypatch):
    async def check():
        store, requests = request_fixture(tmp_path)
        auth = SessionAuth(store, "http://127.0.0.1:8787")
        auth.requests = requests
        async def http(path, body, *, content_type=b"application/json", extras=()):
            replies = []
            scope = {"path": path, "method": "POST", "headers": [
                (b"host", b"127.0.0.1:8787"), (b"origin", b"http://127.0.0.1:8787"),
                (b"content-type", content_type), *extras]}
            async def receive():
                return {"type": "http.request", "body": body}
            async def send(packet):
                replies.append(packet)
            await auth.http(scope, receive, send, RouterApp.respond)
            return replies
        release = lambda: None
        try:
            for body in (b"[]", b'{"capability":"a","capability":"b"}',
                         b'{"capability":null}', b'{"capability":[]}', b"x" * 1025,
                         json.dumps({"capability": "a" * 64, "participant": "page"}).encode()):
                result = await http("/session/request", body)
                assert result[0]["status"] == 400
                assert not requests.records
            assert (await http("/session/request", b"{}", content_type=b"text/plain"))[0]["status"] == 415
            assert (await http("/session/request", b"{}", extras=[(b"origin", b"http://127.0.0.1:8787")]))[0]["status"] == 403
            locator = requests.create("a" * 64)["request"]
            requests.approve(locator, "page")
            token, existing = store.exchange(store.pair_code("other")["code"])
            revoked, release = auth.watch(existing)
            def fail():
                raise OSError("synthetic private persistence error")
            monkeypatch.setattr(store, "save", fail)
            response = await http("/session/request-redeem", json.dumps({
                "request": locator, "capability": "a" * 64}).encode())
            assert response[0]["status"] == 503
            assert b"set-cookie" not in dict(response[0]["headers"])
            assert b"synthetic" not in response[1]["body"]
            assert auth.failed and revoked.is_set()
            assert (await http("/session/request", b"{}"))[0]["status"] == 403
        finally:
            release()
            await auth.close()
    asyncio.run(check())
