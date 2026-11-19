import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from automata.tools.web import browser


def _firefox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    binary = tmp_path / "firefox"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))
    return binary


def test_default_profile_preflight_does_not_create_it(tmp_path, monkeypatch):
    base = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(base))
    expected = base / "automata/browser-profiles/firefox/automata"
    assert browser.default_firefox_profile() == expected
    _firefox(tmp_path, monkeypatch)
    with pytest.raises(browser.BrowserError, match="existing, accessible directory"):
        browser.preflight_browser()
    assert not base.exists()


def test_default_profile_falls_back_under_home(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    expected = tmp_path / ".config/automata/browser-profiles/firefox/automata"
    assert browser.default_firefox_profile() == expected


def test_preflight_resolves_selected_profile_without_mutation(tmp_path, monkeypatch):
    binary = _firefox(tmp_path, monkeypatch)
    profile = tmp_path / "exact profile"
    profile.mkdir()
    alias = tmp_path / "profile alias"
    alias.symlink_to(profile, target_is_directory=True)
    target = browser.preflight_browser(alias)
    assert target == browser.FirefoxTarget(binary, profile)
    assert list(profile.iterdir()) == []


def test_preflight_requires_executable(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(browser.BrowserError, match="Firefox executable not found"):
        browser.preflight_browser(tmp_path)


def test_open_uses_exact_path_once_and_sanitizes_firefox_restart_environment(tmp_path, monkeypatch):
    binary = _firefox(tmp_path, monkeypatch)
    profile = tmp_path / "automata profile"
    profile.mkdir()
    target = browser.preflight_browser(profile)
    overrides = ("XRE_PROFILE_PATH", "XRE_PROFILE_LOCAL_PATH", "MOZ_NO_REMOTE", "MOZ_NEW_INSTANCE")
    for name in overrides:
        monkeypatch.setenv(name, "do-not-inherit")
    monkeypatch.setenv("WAYLAND_DISPLAY", "fixture-display")
    popen = Mock()
    popen.return_value.wait.side_effect = subprocess.TimeoutExpired("fixture", 0.5)
    monkeypatch.setattr(browser.subprocess, "Popen", popen)
    url = "http://127.0.0.1:49000/launch/fixture-ticket"

    browser.open_browser(target, url)

    args, kwargs = popen.call_args
    assert args == ([str(binary), "--profile", str(profile), "--new-tab", url],)
    assert kwargs["env"]["WAYLAND_DISPLAY"] == "fixture-display"
    assert set(overrides).isdisjoint(kwargs["env"])
    assert kwargs["start_new_session"] and kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
    popen.assert_called_once()
    popen.return_value.kill.assert_not_called()
    popen.return_value.terminate.assert_not_called()


def test_open_checks_that_profile_still_exists(tmp_path, monkeypatch):
    _firefox(tmp_path, monkeypatch)
    profile = tmp_path / "old profile"
    profile.mkdir()
    target = browser.preflight_browser(profile)
    profile.rmdir()
    popen = Mock()
    monkeypatch.setattr(browser.subprocess, "Popen", popen)

    with pytest.raises(browser.BrowserError, match="existing, accessible directory"):
        browser.open_browser(target, "http://127.0.0.1:49000/sessions/example/")
    assert not profile.exists()
    popen.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "--profile=fixture-secret",
        "https://example.org/fixture-secret",
        "http://127.0.0.1:23@example.org/fixture-secret",
        "http://127.0.0.1:0/fixture-secret",
        "http://127.0.0.1:90000/fixture-secret",
        "http://127.0.0.1:42/fixture-secret\n",
        "http://127.0.0.1:42/sessions/example/#fixture-secret",
    ],
)
def test_open_rejects_noncanonical_navigation_without_logging(tmp_path, monkeypatch, url):
    binary = _firefox(tmp_path, monkeypatch)
    popen = Mock()
    monkeypatch.setattr(browser.subprocess, "Popen", popen)
    with pytest.raises(browser.BrowserError) as raised:
        browser.open_browser(browser.FirefoxTarget(binary, tmp_path), url)
    assert "fixture-secret" not in str(raised.value)
    popen.assert_not_called()


@pytest.mark.parametrize("failed_spawn", [False, True])
def test_launch_failure_is_redacted_and_never_retried(tmp_path, monkeypatch, failed_spawn):
    binary = _firefox(tmp_path, monkeypatch)
    url = "http://127.0.0.1:49000/launch/fixture-secret"
    popen = Mock(side_effect=OSError(url) if failed_spawn else None)
    popen.return_value.wait.return_value = 3
    monkeypatch.setattr(browser.subprocess, "Popen", popen)
    with pytest.raises(browser.BrowserError) as raised:
        browser.open_browser(browser.FirefoxTarget(binary, tmp_path), url)
    assert "fixture-secret" not in str(raised.value)
    popen.assert_called_once()
