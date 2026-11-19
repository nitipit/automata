from pathlib import Path

import pytest
from dictify import Model
from shelfdb.shelf import DB

from automata.tools.web.config import (
    CONFIG_KEY,
    CONFIG_SHELF,
    ConfigError,
    WebConfig,
    default_config_path,
    load_config,
    save_config,
)


def _put(path: Path, value: object) -> None:
    with DB(str(path)) as db, db.transaction(write=True) as tx:
        tx.shelf(CONFIG_SHELF).put(CONFIG_KEY, value)


def test_missing_implicit_config_does_not_create_store(tmp_path, monkeypatch):
    base = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(base))
    assert default_config_path() == base / "automata/web-ui/config.shelfdb"
    config = load_config()
    assert config.version == 1
    assert (config.browser_profile, config.provider, config.model, config.thinking) == (None,) * 4
    assert not base.exists()


@pytest.mark.parametrize("xdg", [None, "", "relative"])
def test_config_home_fallback(tmp_path, monkeypatch, xdg):
    monkeypatch.setenv("HOME", str(tmp_path))
    if xdg is None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    else:
        monkeypatch.setenv("XDG_CONFIG_HOME", xdg)
    assert default_config_path() == tmp_path / ".config/automata/web-ui/config.shelfdb"


def test_explicit_config_selects_instead_of_merging(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_config(default_config_path(), WebConfig(provider="default-provider", model="default"))
    alternate = tmp_path / "alternate.shelfdb"
    save_config(alternate, WebConfig(thinking="off"))

    assert load_config().provider == "default-provider"
    config = load_config(alternate)
    assert config.thinking == "off"
    assert config.provider is None and config.model is None
    missing = tmp_path / "missing.shelfdb"
    with pytest.raises(ConfigError, match="does not exist"):
        load_config(missing)
    assert not missing.exists()


def test_explicit_save_omits_unset_fields_and_load_leaves_data_unchanged(tmp_path):
    path = tmp_path / "prefs.shelfdb"
    config = WebConfig(browser_profile="~/dedicated profile", provider="fixture", model="model")
    save_config(path, config)
    with DB(str(path)) as db, db.transaction(write=False) as tx:
        assert tx.shelf(CONFIG_SHELF).key(CONFIG_KEY).item().value == {
            "version": 1,
            "browser_profile": "~/dedicated profile",
            "provider": "fixture",
            "model": "model",
        }
    data = path / "data.mdb"
    before = data.stat().st_mtime_ns, data.read_bytes(), set(path.iterdir())
    assert dict(load_config(path)) == dict(config)
    assert before == (data.stat().st_mtime_ns, data.read_bytes(), set(path.iterdir()))
    save_config(path, WebConfig(thinking="max"))
    assert dict(load_config(path)) == dict(WebConfig(thinking="max"))


@pytest.mark.parametrize(
    "record",
    [
        {"provider": "missing-version"},
        {"version": 2},
        {"version": True},
        {"version": "1"},
        {"version": 1, "port": 1234},
        {"version": 1, "browser_profile": "  "},
        {"version": 1, "provider": []},
        {"version": 1, "model": "\0"},
        {"version": 1, "model": None},
        {"version": 1, "thinking": "unsupported"},
        [1],
    ],
)
def test_invalid_existing_configuration_is_an_error(tmp_path, monkeypatch, record):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = default_config_path()
    path.mkdir(parents=True)
    _put(path, record)
    with pytest.raises(ConfigError, match="Invalid Web UI configuration"):
        load_config()


def test_missing_lock_file_is_not_recreated(tmp_path):
    path = tmp_path / "backup.shelfdb"
    save_config(path, WebConfig())
    lock_file = path / "lock.mdb"
    lock_file.unlink()
    with pytest.raises(ConfigError, match="Expected an existing ShelfDB"):
        load_config(path)
    assert not lock_file.exists()


def test_directory_instead_of_store_is_not_initialized(tmp_path):
    empty = tmp_path / "empty.shelfdb"
    empty.mkdir()
    with pytest.raises(ConfigError, match="Expected an existing ShelfDB"):
        load_config(empty)
    assert list(empty.iterdir()) == []


def test_public_model_validates_version_and_optional_values():
    with pytest.raises(Model.Error):
        WebConfig(version=2, provider=100)
    for level in ("off", "minimal", "low", "medium", "high", "xhigh", "max"):
        assert WebConfig(thinking=level).thinking == level
