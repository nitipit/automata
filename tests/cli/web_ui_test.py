"""CLI contract tests: preferences, one creation, and credential-free output."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from automata.cli import app
from automata.tools.web import browser, config, server
from automata.tools.web.cli import checkout_root


def test_checkout_from_subdirectory():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    assert checkout_root(root / "tests") == root


@pytest.mark.parametrize("outcome", ["connected", "unconfirmed", "open_failed", "bad_config"])
def test_create_once(tmp_path, monkeypatch, capsys, outcome):
    store = tmp_path / "prefs"
    config.save_config(store, config.WebConfig({"model": "saved"}))
    endpoint = Mock()
    private = "sensitive-test-link"
    endpoint.new_session.return_value = SimpleNamespace(url=private, session_id="test-native")
    endpoint.wait_connected.return_value = outcome == "connected"
    select = Mock(return_value=endpoint)
    monkeypatch.setattr(server, "find_or_start", select)
    monkeypatch.setattr(browser, "preflight_browser", Mock())
    opener = Mock(side_effect=browser.BrowserError(private) if outcome == "open_failed" else None)
    monkeypatch.setattr(browser, "open_browser", opener)
    args = [
        "web-ui",
        "--config",
        str(store),
        "chat",
        "new",
        "--cwd",
        str(tmp_path),
        "--model",
        "override",
        "--json",
    ]
    if outcome == "bad_config":
        args += ["--thinking", "invalid"]
    if outcome == "connected":
        app(args, result_action="return_value")
    else:
        with pytest.raises(SystemExit) as exc:
            app(args, result_action="return_value")
        assert exc.value.code == 1
    captured = capsys.readouterr()
    assert private not in captured.out + captured.err
    result = json.loads(captured.out)
    assert result["browser_connected"] == (outcome == "connected")
    assert config.load_config(store).model == "saved"
    if outcome == "bad_config":
        select.assert_not_called()
        assert result["session_id"] is None
        return
    assert result["session_id"] == "test-native"
    endpoint.new_session.assert_called_once_with(model="override", provider=None, thinking=None)
    opener.assert_called_once()
