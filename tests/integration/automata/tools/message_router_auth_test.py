"""Source CLI, private operator socket and real HTTP/WebSocket session boundaries."""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ENTRY = Path(__file__).parents[4] / "src/automata/tools/message-router/message_router.py"


class Service:
    def __init__(self, root):
        self.root = root
        uv = shutil.which("uv")
        if not uv:
            pytest.skip("uv required")
        self.cli = [uv, "run", "--offline", "--no-project", "--script", str(ENTRY)]
        self.private = root / "private"
        self.config, self.endpoints = self.private / "config.json", self.private / "endpoints"
        self.auth = self.private / "auth"
        self.public = root / "public"
        self.public.mkdir()
        (self.public / "index.html").write_text("<p>public-safe</p>")
        self.run("setup", "--config-file", str(self.config), "--page", "page", "--agent", "agent")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.base = f"http://127.0.0.1:{self.port}"
        self.process = None
        self.connections = []
        self.log = (root / "server.log").open("w+")

    def run(self, *arguments):
        result = subprocess.run([*self.cli, *arguments], cwd=self.root,
                                capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    def start(self, seconds=604800):
        self.process = subprocess.Popen([*self.cli, "serve", "--config-file", str(self.config),
            "--endpoint-dir", str(self.endpoints), "--auth-dir", str(self.auth),
            "--port", str(self.port), "--public-root", str(self.public),
            "--session-seconds", str(seconds)], stdout=self.log, stderr=self.log)
        deadline = time.monotonic() + 10
        while not (self.endpoints / "server.json").exists():
            if self.process.poll() is not None or time.monotonic() > deadline:
                self.log.seek(0)
                pytest.fail(self.log.read())
            time.sleep(.02)
        assert (self.auth / "control.sock").stat().st_mode & 0o777 == 0o600

    def stop(self):
        for connection in self.connections:
            connection.close()
        self.connections.clear()
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)
        self.process = None
        assert not (self.auth / "control.sock").exists()
        assert not (self.endpoints / "server.json").exists()

    def http(self, path, value=None, *, cookie=None, origin=True, host=None):
        headers = {}
        if value is not None:
            headers["Content-Type"] = "application/json"
        if origin:
            headers["Origin"] = self.base if origin is True else origin
        if host:
            headers["Host"] = host
        if cookie:
            headers["Cookie"] = cookie
        request = urllib.request.Request(self.base + path, headers=headers,
            data=None if value is None else json.dumps(value).encode())
        try:
            response = urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    def pair(self):
        output = self.run("pair", "--auth-dir", str(self.auth), "--participant", "page")
        code = json.loads(output)["code"]
        status, body, headers = self.http("/session/pair", {"code": code})
        assert status == 200, body
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        assert "HttpOnly" in headers["Set-Cookie"] and "SameSite=Strict" in headers["Set-Cookie"]
        assert "Secure" not in headers["Set-Cookie"]
        return code, cookie

    def ws(self, *, cookie=None, origin=True, path="/session/ws", hello=None):
        websocket = pytest.importorskip("websocket")
        options = {"timeout": 4}
        if cookie:
            options["cookie"] = cookie
        if origin:
            options["origin"] = self.base if origin is True else origin
        else:
            options["suppress_origin"] = True
        connection = websocket.create_connection(
            self.base.replace("http:", "ws:") + path, **options)
        self.connections.append(connection)
        connection.send(json.dumps(hello or {"v": 2, "type": "hello"}))
        return connection, json.loads(connection.recv())


@pytest.fixture
def service(tmp_path):
    instance = Service(tmp_path)
    try:
        yield instance
    finally:
        instance.stop()
        instance.log.close()


def packet(connection, value):
    connection.send(json.dumps({"v": 2, **value}))
    return json.loads(connection.recv())


def test_pair_restart_duplicate_grants_full_payload_and_logout(service):
    s = service
    s.start()
    code, cookie = s.pair()
    assert s.http("/session/pair", {"code": code})[0] == 400
    assert s.http("/session/pair", {"code": "bad", "participant": "agent"})[0] == 400
    assert s.http("/session/status", cookie=cookie)[0] == 200
    page, hello = s.ws(cookie=cookie)
    assert hello == {"v": 2, "type": "hello_ack", "participant": "page", "kind": "page",
                     "network": "default"}
    duplicate, denied = s.ws(cookie=cookie)
    assert denied["type"] == "error"
    duplicate.close()
    assert packet(page, {"type": "status", "requestId": "still"})["status"] == "connected"
    assert packet(page, {"type": "route", "requestId": "offline", "to": "agent",
                         "payload": {"text": "not replayed"}})["error"] == "offline"
    record = json.loads((s.endpoints / "participants/agent.json").read_text())
    agent, hello = s.ws(path="/ws", hello={"v": 2, "type": "hello", "participant": "agent",
                         "token": record["token"], "sessionId": "test-session"})
    assert hello["kind"] == "agent"
    payload = {"nested": [None, False, 0, "", {"extra": {"answer": 42}}]}
    receipt = packet(page, {"type": "route", "requestId": "new-explicit", "to": "agent",
                           "payload": payload, "metadata": {"custom": [1, 2]}})
    incoming = json.loads(agent.recv())
    assert receipt["status"] == "forwarded" and incoming["payload"] == payload
    assert incoming["metadata"] == {"custom": [1, 2]}
    assert incoming["id"] == receipt["routeId"]
    assert packet(agent, {"type": "respond", "requestId": "reply", "routeId": incoming["id"],
                          "payload": payload})["status"] == "forwarded"
    response = json.loads(page.recv())
    assert response["payload"] == payload and response["requestId"] == "new-explicit"
    assert packet(page, {"type": "route", "requestId": "forbidden", "to": "page",
                         "payload": None})["error"] == "forbidden"
    # A lost capability is never recovered by a valid persistent browser session.
    pending = packet(page, {"type": "route", "requestId": "lost", "to": "agent", "payload": None})
    assert json.loads(agent.recv())["id"] == pending["routeId"]
    s.stop()
    s.start()
    page, hello = s.ws(cookie=cookie)
    assert hello["participant"] == "page"
    status = packet(page, {"type": "status", "requestId": "restart-status"})
    assert status["pending"] == 0
    assert status["destinations"] == [{"id": "agent", "kind": "agent", "network": "default",
                                       "connected": False}]
    assert s.http("/session/logout", {}, cookie=cookie)[0] == 200
    assert page.recv() == ""  # idle socket closed; no post-revocation JSON frame
    assert json.loads(s.http("/session/status", cookie=cookie)[1])["authenticated"] is False
    websocket = pytest.importorskip("websocket")
    with pytest.raises(websocket.WebSocketBadStatusException):
        s.ws(cookie=cookie)
    text = (s.auth / "state.json").read_text()
    assert code not in text and cookie.split("=", 1)[1] not in text
    (s.public / "private-link").symlink_to(s.auth / "state.json")
    assert s.http("/private-link")[0] == 404
    assert s.http("/state.json")[0] == 404


def test_wrong_origin_host_hello_and_operator_revoke(service):
    s = service
    s.start()
    code = json.loads(s.run("pair", "--auth-dir", str(s.auth), "--participant", "page"))["code"]
    for options in ({"origin": False}, {"origin": "http://evil.test"},
                    {"host": "localhost:" + str(s.port)}, {"host": "127.0.0.1:1"}):
        assert s.http("/session/pair", {"code": code}, **options)[0] == 403
    status, body, headers = s.http("/session/pair", {"code": code})
    assert status == 200, body
    cookie = headers["Set-Cookie"].split(";", 1)[0]
    websocket = pytest.importorskip("websocket")
    for origin in (False, "http://evil.test"):
        with pytest.raises(websocket.WebSocketBadStatusException):
            s.ws(cookie=cookie, origin=origin)
    spoof, result = s.ws(cookie=cookie, hello={"v": 2, "type": "hello", "participant": "agent"})
    assert result["type"] == "error"
    spoof.close()
    page, hello = s.ws(cookie=cookie)
    assert hello["type"] == "hello_ack"
    result = json.loads(s.run("revoke", "--auth-dir", str(s.auth), "--participant", "page"))
    assert result["revoked"] == 1
    assert page.recv() == ""


def test_session_expiry_closes_idle_socket(service):
    s = service
    s.start(seconds=2)
    _, cookie = s.pair()
    page, hello = s.ws(cookie=cookie)
    assert hello["type"] == "hello_ack"
    assert page.recv() == ""
    assert json.loads(s.http("/session/status", cookie=cookie)[1])["authenticated"] is False


def test_failed_public_bind_never_starts_private_control(service):
    s = service
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", s.port))
        occupied.listen()
        result = subprocess.run([*s.cli, "serve", "--config-file", str(s.config),
            "--endpoint-dir", str(s.endpoints), "--auth-dir", str(s.auth),
            "--port", str(s.port)], cwd=s.root, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert not (s.auth / "control.sock").exists()
    assert not (s.endpoints / "server.json").exists()
    # Failed bind released the store owner; same explicit start can now succeed.
    s.start()
    s.stop()


def test_malformed_persisted_auth_fails_visible_without_reset(service):
    s = service
    s.auth.mkdir(parents=True, mode=0o700)
    state = s.auth / "state.json"
    state.write_text('{"v":1,"codes":{},"sessions":{"bad":{}}}')
    state.chmod(0o600)
    original = state.read_bytes()
    result = subprocess.run([*s.cli, "serve", "--config-file", str(s.config),
        "--endpoint-dir", str(s.endpoints), "--auth-dir", str(s.auth),
        "--port", str(s.port)], cwd=s.root, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0 and "malformed" in result.stdout
    assert state.read_bytes() == original
    assert not (s.auth / "control.sock").exists()
    assert not (s.endpoints / "server.json").exists()


def test_request_happy_path_cookie_guard_and_restart(service):
    s = service
    # Synthetic fixture config only: exercise a second existing configured page.
    config = json.loads(s.config.read_text())
    config["nodes"]["other"] = {"kind": "page", "token": "o" * 32}
    s.config.write_text(json.dumps(config))
    s.start()
    capability = "a" * 64
    code = json.loads(s.run("pair", "--auth-dir", str(s.auth), "--participant", "other"))["code"]
    status, body, headers = s.http("/session/request", {"capability": capability})
    assert status == 200 and "Set-Cookie" not in headers
    created = json.loads(body)
    packet = {"request": created["request"], "capability": capability}
    assert json.loads(s.http("/session/request", {"capability": capability})[1]) == created
    websocket = pytest.importorskip("websocket")
    with pytest.raises(websocket.WebSocketBadStatusException):
        s.ws(cookie=f"automata_router_session={capability}")
    for path in ("request-status", "request-cancel", "request-redeem"):
        assert s.http("/session/" + path, {**packet, "capability": "b" * 64})[0] == 400
        assert s.http("/session/" + path, {"request": created["request"]})[0] == 400
    assert s.http("/session/request-redeem", packet)[0] == 400
    # Wrong request credentials never consume existing fallback guess budgets.
    status, _, paired_headers = s.http("/session/pair", {"code": code})
    assert status == 200
    other_cookie = paired_headers["Set-Cookie"].split(";", 1)[0]
    approved = json.loads(s.run("approve-request", "--auth-dir", str(s.auth),
                              "--request", created["request"], "--participant", "page"))
    assert approved["state"] == "approved" and approved["expiresAt"] == created["expiresAt"]
    assert json.loads(s.run("approve-request", "--auth-dir", str(s.auth),
                          "--request", created["request"], "--participant", "page")) == approved
    status, _, denied_headers = s.http("/session/request-redeem", packet, cookie=other_cookie)
    assert status == 400 and "Set-Cookie" not in denied_headers
    assert json.loads(s.http("/session/status", cookie=other_cookie)[1])["participant"] == "other"
    sessions = json.loads((s.auth / "state.json").read_text())["sessions"]
    assert len(sessions) == 1 and next(iter(sessions.values()))["participant"] == "other"
    assert json.loads(s.run("request-status", "--auth-dir", str(s.auth),
                          "--request", created["request"]))["state"] == "approved"
    assert s.http("/session/logout", {}, cookie=other_cookie)[0] == 200
    status, body, headers = s.http("/session/request-redeem", packet)
    assert status == 200 and json.loads(body)["participant"] == "page"
    cookie = headers["Set-Cookie"].split(";", 1)[0]
    status, _, headers = s.http("/session/request-redeem", packet)
    assert status == 400 and "Set-Cookie" not in headers  # lost cookie cannot be reissued
    page, hello = s.ws(cookie=cookie)
    assert hello["participant"] == "page"
    assert packet_status(page)["status"] == "connected"
    fresh = json.loads(s.http("/session/request", {"capability": "c" * 64})[1])
    s.stop()
    s.start()
    assert json.loads(s.http("/session/status", cookie=cookie)[1])["authenticated"] is True
    assert s.http("/session/request-status", {"request": fresh["request"], "capability": "c" * 64})[0] == 400
    assert capability not in (s.auth / "state.json").read_text()


def packet_status(connection):
    return packet(connection, {"type": "status", "requestId": "request-paired-status"})


def test_request_origin_cancel_and_actual_cli_peer_presence(service):
    s = service
    s.start()
    for options in ({"origin": False}, {"origin": "http://evil.test"},
                    {"host": "localhost:" + str(s.port)}):
        for path in ("request", "request-status", "request-cancel", "request-redeem"):
            assert s.http("/session/" + path, {"capability": "a" * 64}, **options)[0] == 403
    assert s.http("/session/request?capability=bad", {"capability": "a" * 64})[0] == 404
    created = json.loads(s.http("/session/request", {"capability": "a" * 64})[1])
    locator = created["request"]
    record = json.loads((s.endpoints / "participants/page.json").read_text())
    peer, hello = s.ws(path="/ws", hello={"v": 2, "type": "hello", "participant": "page", "token": record["token"]})
    assert hello["participant"] == "page"
    command = [*s.cli, "approve-request", "--auth-dir", str(s.auth),
               "--request", locator, "--participant", "page"]
    result = subprocess.run(command, cwd=s.root, capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert packet_status(peer)["status"] == "connected"  # no active-peer takeover
    assert json.loads(s.run("request-status", "--auth-dir", str(s.auth), "--request", locator))["state"] == "pending"
    packet_value = {"request": locator, "capability": "a" * 64}
    assert json.loads(s.http("/session/request-cancel", packet_value)[1])["state"] == "cancelled"
    assert json.loads(s.http("/session/request-cancel", packet_value)[1])["state"] == "cancelled"
    result = subprocess.run(command, cwd=s.root, capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    fresh = json.loads(s.http("/session/request", {"capability": "b" * 64})[1])
    assert fresh["request"] != locator
    assert s.http("/session/request-cancel", packet_value)[0] == 200
    assert json.loads(s.run("request-status", "--auth-dir", str(s.auth),
                          "--request", fresh["request"]))["state"] == "pending"
