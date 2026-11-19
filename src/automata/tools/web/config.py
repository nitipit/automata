"""Versioned local preferences for Web UI launch."""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

import lmdb
from dictify import Field, Model
from shelfdb.shelf import DB
from shelfdb.shelf.db import Transaction

from .model_controls import THINKING_LEVELS

CONFIG_SHELF = "web_ui"
CONFIG_KEY = "config"
_VERSION = 1
_DB_LOCK = Lock()


class ConfigError(ValueError):
    """The selected Web UI configuration is missing or invalid."""


def _optional_text(value: object) -> bool:
    return value is None or (isinstance(value, str) and bool(value.strip()) and "\0" not in value)


class WebConfig(Model):
    """V1 preferences; None leaves selection to the next default layer."""

    version = Field(default=_VERSION).verify(lambda v: type(v) is int and v == _VERSION)
    browser_profile = Field(default=None).verify(_optional_text)
    provider = Field(default=None).verify(_optional_text)
    model = Field(default=None).verify(_optional_text)
    thinking = Field(default=None).verify(
        lambda v: v is None or (isinstance(v, str) and v in THINKING_LEVELS)
    )


def _config_home() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", ""))
    return base if base.is_absolute() else Path.home() / ".config"


def default_config_path() -> Path:
    """Return the XDG path without creating it."""
    return _config_home() / "automata" / "web-ui" / "config.shelfdb"


def _read_record(path: Path) -> object:
    if not (path / "data.mdb").is_file() or not (path / "lock.mdb").is_file():
        raise ConfigError(f"Expected an existing ShelfDB at {path}")
    # ShelfDB's DB constructor opens for writing. Reuse its transaction and
    # decoding on a read-only LMDB handle instead; retain LMDB reader locking.
    with _DB_LOCK, lmdb.open(str(path), readonly=True, create=False, max_dbs=128) as env:
        with Transaction(env, env.begin()) as tx:
            return tx.shelf(CONFIG_SHELF).key(CONFIG_KEY).item().value


def load_config(path: Path | None = None) -> WebConfig:
    """Read one selected store; only an absent implicit default is optional."""
    selected = default_config_path() if path is None else path.expanduser()
    try:
        selected.lstat()
    except FileNotFoundError:
        if path is None:
            return WebConfig()
        raise ConfigError(f"Web UI configuration does not exist: {selected}") from None
    except OSError:
        raise ConfigError(f"Cannot access Web UI configuration at {selected}") from None

    try:
        record = _read_record(selected)
        if not isinstance(record, dict) or "version" not in record:
            raise ValueError("Expected a versioned record")
        if any(value is None for value in record.values()):
            raise ValueError("Unset preferences must be omitted")
        return WebConfig(record)
    except ConfigError:
        raise
    except (lmdb.Error, Model.Error, OSError, TypeError, ValueError):
        raise ConfigError(f"Invalid Web UI configuration at {selected}") from None


def save_config(path: Path, config: WebConfig) -> None:
    """Explicitly store a validated V1 record at path."""
    selected = path.expanduser()
    try:
        validated = WebConfig(dict(config))
        record = {field: value for field, value in validated.items() if value is not None}
        with _DB_LOCK:
            selected.mkdir(parents=True, exist_ok=True, mode=0o700)
            with DB(str(selected)) as db, db.transaction(write=True) as tx:
                tx.shelf(CONFIG_SHELF).put(CONFIG_KEY, record)
    except (lmdb.Error, Model.Error, OSError, RuntimeError, TypeError, ValueError):
        raise ConfigError(f"Cannot save Web UI configuration at {selected}") from None
