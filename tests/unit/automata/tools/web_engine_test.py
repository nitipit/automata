import ast
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from automata.tools.web import bidi, browser, cli, engine, server
from automata.tools.web.config import WebConfig, save_config
from automata.tools.web.host import BrowserHost

_ORIGIN = "http://127.0.0.1:12600"
_SID = "native-id"
_TICKET = "private-fixture-launch-ticket"
_KEY = "private-fixture-jupyter-key"
_ADMITTED = {"session_id": _SID, "url": f"{_ORIGIN}/chat/sessions/{_SID}/launch/{_TICKET}"}
_PROBE = {"identity": "a" * 64, "origin": _ORIGIN}


@pytest.fixture
def flow(tmp_path, monkeypatch):
    path = tmp_path / "kernel.json"
    path.write_text(
        json.dumps(
            {
                **{
                    f"{k}_port": 12100 + i
                    for i, k in enumerate(("shell", "iopub", "hb", "control", "stdin"))
                },
                "transport": "tcp",
                "ip": "127.0.0.1",
                "key": _KEY,
                "signature_scheme": "hmac-sha256",
            }
        )
    )
    path.chmod(0o600)
    profile = tmp_path / "firefox"
    profile.mkdir()
    config = tmp_path / "prefs.shelfdb"
    save_config(config, WebConfig({"browser_profile": str(profile), "provider": "from-config"}))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(cli, "_config", SimpleNamespace(get=lambda: config))

    def forbidden(*_, **__):
        pytest.fail("engine mode must not launch or fall back to a managed host or plain Firefox")

    monkeypatch.setattr(server, "find_or_start", forbidden)
    monkeypatch.setattr(browser, "open_browser", forbidden)
    monkeypatch.setattr(browser.shutil, "which", lambda exe: "/usr/bin/firefox")
    calls = []
    state = SimpleNamespace(
        calls=calls,
        path=path,
        project=tmp_path,
        probe=_PROBE,
        admission=_ADMITTED,
        open_error=None,
        ready=True,
        connect_error=None,
        options=None,
    )

    class Client:
        def load_connection_info(self, info):
            assert info["key"] == _KEY and info["ip"] == "127.0.0.1"

        def start_channels(self, **kwargs):
            assert kwargs == dict(stdin=False, hb=False, control=False, iopub=False)

        async def execute(self, code, *, user_expressions, **kwargs):
            assert kwargs == {
                "silent": True,
                "store_history": False,
                "allow_stdin": False,
                "reply": True,
                "timeout": kwargs["timeout"],
            }
            expr = user_expressions["automata"]
            assert all(secret not in code + expr for secret in (_KEY, _TICKET))
            if code:
                calls.append("create")
                assert "await" in code and str(tmp_path) in code and _PROBE["identity"] in code
                state.options = ast.literal_eval(ast.parse(code).body[0].value.value.args[-1])
                response = state.admission
            elif "kernel_probe" in expr and "kernel_paired" not in expr:
                calls.append("probe")
                response = state.probe
            else:
                calls.append("pair")
                assert _SID in expr and _PROBE["identity"] in expr
                response = {"connected": True}
            if isinstance(response, Exception):
                raise response
            return {
                "content": {
                    "status": "ok",
                    "user_expressions": {
                        "automata": {
                            "status": "ok",
                            "data": {"text/plain": repr(response)},
                        }
                    },
                }
            }

        def stop_channels(self):
            calls.append("stop-kernel-client")

    class ControlledFirefox:
        def open_chat(self, admission, origin):
            calls.append("open")
            assert (admission.session_id, origin, admission.url) == (
                _SID,
                _ORIGIN,
                _ADMITTED["url"],
            )
            if state.open_error:
                raise state.open_error

        def chat_ready(self):
            return state.ready

        def close(self):
            calls.append("release-bidi")

    def connect(target):
        calls.append("connect-bidi")
        assert target.profile == profile
        if state.connect_error:
            raise state.connect_error
        return ControlledFirefox()

    monkeypatch.setitem(sys.modules, "jupyter_client", SimpleNamespace(AsyncKernelClient=Client))
    monkeypatch.setattr(bidi, "connect_firefox", connect)
    return state


def _failed(flow, capsys, **flags):
    with pytest.raises(SystemExit) as failure:
        cli.new(engine=flow.path, cwd=flow.project, as_json=True, **flags)
    assert failure.value.code == 1
    output = capsys.readouterr()
    assert _KEY not in output.out + output.err and _TICKET not in output.out + output.err
    return json.loads(output.out)


def test_create_on_selected_engine_and_confirm_exact_tab_and_pair(flow, capsys):
    cli.new(engine=flow.path, cwd=flow.project, model="from-flag", as_json=True)
    assert json.loads(capsys.readouterr().out) == {
        "session_id": _SID,
        "creation": "created",
        "browser_connected": True,
    }
    assert flow.calls == [
        "probe",
        "connect-bidi",
        "create",
        "open",
        "pair",
        "release-bidi",
        "stop-kernel-client",
    ]
    assert flow.options == {"provider": "from-config", "model": "from-flag", "thinking": None}


def test_browser_failure_after_create_retains_session_id_without_retry(flow, capsys):
    flow.open_error = browser.BrowserError(f"private browser error {_TICKET}")
    assert _failed(flow, capsys) == {
        "session_id": _SID,
        "creation": "created",
        "browser_connected": False,
        "error": "browser_open_failed",
    }
    assert flow.calls == [
        "probe",
        "connect-bidi",
        "create",
        "open",
        "release-bidi",
        "stop-kernel-client",
    ]


def test_dispatched_create_timeout_is_unknown_and_not_retried(flow, capsys):
    flow.admission = TimeoutError(f"private reply {_TICKET}")
    assert _failed(flow, capsys) == {
        "session_id": None,
        "creation": "unknown",
        "browser_connected": False,
        "error": "engine_create_timeout",
    }
    assert flow.calls == ["probe", "connect-bidi", "create", "release-bidi", "stop-kernel-client"]


def test_request_for_different_checkout_never_touches_browser_or_creates(flow, capsys):
    flow.probe = {"error": "engine_project_mismatch"}
    assert _failed(flow, capsys)["error"] == "engine_project_mismatch"
    assert flow.calls == ["probe", "stop-kernel-client"]


def test_missing_bidi_control_does_not_create(flow, capsys):
    flow.connect_error = bidi.BiDiError("firefox_bidi_unavailable")
    assert _failed(flow, capsys)["creation"] == "not_created"
    assert flow.calls == ["probe", "connect-bidi", "stop-kernel-client"]


def test_unsafe_connection_file_does_not_contact_kernel(flow, capsys):
    flow.path.chmod(0o644)
    assert _failed(flow, capsys)["error"] == "invalid_connection_file"
    assert not flow.calls


def test_unconfirmed_browser_target_does_not_count_as_connected(flow, capsys, monkeypatch):
    monkeypatch.setattr(engine, "_PAIR_SECONDS", 0.01)
    flow.ready = False
    assert _failed(flow, capsys) == {
        "session_id": _SID,
        "creation": "created",
        "browser_connected": False,
        "error": "browser_connection_unconfirmed",
    }
    assert flow.calls.count("create") == 1 and "pair" not in flow.calls


def test_admission_on_other_host_keeps_id_but_does_not_navigate(flow, capsys):
    flow.admission = {**_ADMITTED, "url": _ADMITTED["url"].replace(":12600/", ":13000/")}
    assert _failed(flow, capsys)["session_id"] == _SID
    assert flow.calls.count("create") == 1 and "open" not in flow.calls


def test_kernel_rechecks_host_identity_before_effects(tmp_path):
    def host():
        instance = object.__new__(BrowserHost)
        instance._project = tmp_path
        instance._started, instance._closed = True, False
        instance.runtime = SimpleNamespace(origin=_ORIGIN, token="fake", _running=True)
        instance._runtime = SimpleNamespace(memory_bridge=True)
        instance.admit_session = AsyncMock()
        return instance

    approved, substituted = host(), host()
    project = str(tmp_path)
    identity = engine.kernel_probe(approved, project)["identity"]
    assert asyncio.run(engine.kernel_create(substituted, project, identity, {})) == {
        "error": "engine_host_changed",
    }
    substituted.admit_session.assert_not_called()
    assert engine.kernel_probe(approved, str(tmp_path.parent)) == {
        "error": "engine_project_mismatch",
    }
    substituted._runtime = SimpleNamespace()
    assert asyncio.run(engine.kernel_create(substituted, project, identity, {})) == {
        "error": "engine_host_incompatible",
    }
    substituted.admit_session.assert_not_called()
    approved.admit_session.return_value = SimpleNamespace(session_id=_SID, url=_ADMITTED["url"])
    assert asyncio.run(engine.kernel_create(approved, project, identity, {"thinking": "low"})) == (
        _ADMITTED
    )
    approved.admit_session.assert_awaited_once_with(provider=None, model=None, thinking="low")


def test_bidi_navigates_only_to_clean_url_and_scopes_handoff(monkeypatch):
    from automata.tools.web.server_control import admission_from

    tab = bidi.FirefoxBiDi(socket=None)
    requests = []
    target = f"{_ORIGIN}/chat/sessions/{_SID}/"
    secret = "private-fixture-admission"

    def call(method, **params):
        requests.append((method, params))
        return {
            "browsingContext.create": {"context": "created-tab"},
            "script.addPreloadScript": {"script": "handoff"},
            "script.evaluate": {"type": "success", "result": {"value": target}},
        }.get(method, {})

    monkeypatch.setattr(bidi, "_redeem", lambda *args: secret)
    monkeypatch.setattr(tab, "call", call)
    tab.open_chat(admission_from(_ADMITTED), _ORIGIN)
    assert requests[1][1]["contexts"] == ["created-tab"]
    assert secret in requests[1][1]["functionDeclaration"]
    assert requests[2] == (
        "browsingContext.navigate",
        {
            "context": "created-tab",
            "url": target,
            "wait": "interactive",
        },
    )
    assert requests[3][1]["target"] == {"context": "created-tab"}
    assert requests[-1] == ("script.removePreloadScript", {"script": "handoff"})
    assert _TICKET not in repr(requests)


def test_locked_profile_with_untrusted_listener_is_not_restarted(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        pytest.fail("must not start Firefox or connect to an unverified listener")

    monkeypatch.setattr(bidi, "_locked", lambda _: True)
    monkeypatch.setattr(bidi, "_cold_start", fail)
    monkeypatch.setattr(bidi, "_port", lambda _: 42601)
    monkeypatch.setattr(bidi.shutil, "which", lambda _: "/usr/bin/ss")
    monkeypatch.setattr(
        bidi.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(
            stdout='LISTEN 0 5 0.0.0.0:42601 0.0.0.0:* users:(("firefox",pid=100,fd=14))\n',
        ),
    )
    monkeypatch.setitem(sys.modules, "websocket", SimpleNamespace(create_connection=fail))
    with pytest.raises(bidi.BiDiError, match="firefox_bidi_unavailable"):
        bidi.connect_firefox(browser.FirefoxTarget(Path("/usr/bin/firefox"), tmp_path))


@pytest.mark.parametrize("session_created", [False, True])
def test_bidi_never_uses_wrong_profile_or_takes_over_foreign_session(
    monkeypatch, tmp_path, session_created
):
    target = browser.FirefoxTarget(Path("/usr/bin/firefox"), tmp_path)
    commands = []

    def connect(url, **_):
        assert url == "ws://127.0.0.1:43101/session"
        return SimpleNamespace(close=lambda **kw: commands.append("close"))

    def call(self, method, **_):
        commands.append(method)
        if method == "session.new":
            if not session_created:
                raise browser.BrowserError("another controller owns the active session")
            return {
                "capabilities": {
                    "browserName": "firefox",
                    "moz:processID": 101,
                    "moz:profile": "/other/profile",
                }
            }

    monkeypatch.setattr(bidi.shutil, "which", lambda _: "/usr/bin/ss")
    monkeypatch.setattr(bidi, "_locked", lambda _: True)
    monkeypatch.setattr(bidi, "_endpoint", lambda *args: (43101, 101, b"102"))
    monkeypatch.setattr(bidi.FirefoxBiDi, "call", call)
    monkeypatch.setitem(sys.modules, "websocket", SimpleNamespace(create_connection=connect))
    with pytest.raises(bidi.BiDiError, match="firefox_bidi_unavailable"):
        bidi.connect_firefox(target)
    # End only a session this CLI actually established. Never open any tab on either failure.
    assert commands == (
        ["session.new", "session.end", "close"]
        if session_created
        else [
            "session.new",
            "close",
        ]
    )
