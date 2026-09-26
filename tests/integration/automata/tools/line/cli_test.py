"""Schema-driven CLI contracts; no live account or message dispatch."""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).parents[5] / "src/automata/tools/line"
sys.path.insert(0, str(SOURCE))
schemas = importlib.import_module("line_schemas")
cli = importlib.import_module("line_cli")


@pytest.mark.parametrize(
    "fields",
    [
        {"before": "1:a", "after": "2:b"},
        {"limit": 0},
        {"limit": 1001},
        {"before": "wrong"},
        {"after": "0:a"},
        {"max_scrolls": -1},
        {"since": "2026-09-27", "until": "2026-09-26"},
        {"since": "2026-09-27T12:00:00"},
    ],
)
def test_read_schema_rejects_invalid_inputs(fields):
    with pytest.raises((ValueError, schemas.Model.Error)):
        schemas.Read(chat_id="chat-a", **fields)


def test_dates_use_explicit_offset_or_configured_timezone(monkeypatch):
    monkeypatch.setenv("AUTOMATA_LINE_TIMEZONE", "Asia/Bangkok")
    assert schemas.date_ms("2026-09-27") == schemas.date_ms("2026-09-26T17:00:00Z")
    assert schemas.date_ms("2026-09-27T00:00:00+07:00") == schemas.date_ms("2026-09-27")
    monkeypatch.delenv("AUTOMATA_LINE_TIMEZONE")
    assert schemas.date_ms("2026-09-27") == schemas.date_ms("2026-09-27T00:00:00Z")


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"text": ""},
        {"text": "x", "sticker_id": "y", "sticker_package": "z"},
        {"sticker_id": "x"},
        {"confirm": "token", "draft": True},
        {"confirm": "token", "text": "x"},
        {"confirm": ""},
        {"mention": "All"},
        {"mention": " "},
        {"image": Path("/no/such/image.png")},
    ],
)
def test_send_schema_rejects_ambiguous_or_invalid_content(fields):
    with pytest.raises((ValueError, schemas.Model.Error)):
        schemas.Send(chat_id="chat-a", **fields)


def test_image_schema_reads_only_signature(tmp_path, monkeypatch):
    image = tmp_path / "fixture.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fixture")

    def forbidden_full_read(self):
        raise AssertionError("Validation must not read the entire image")

    monkeypatch.setattr(Path, "read_bytes", forbidden_full_read)
    assert schemas.Send(chat_id="chat-a", image=image, draft=True).image == image


def test_shared_draft_and_direct_send_path():
    calls = []
    line = SimpleNamespace(
        draft=lambda chat, text: calls.append(("prepare", chat, text)) or {"token": "bound"},
        send=lambda chat, token: calls.append(("send", chat, token)) or {"status": "dispatched"},
    )
    assert cli.dispatch_send(line, schemas.Send(chat_id="a", text="Hi", draft=True)) == {
        "token": "bound"
    }
    assert calls == [("prepare", "a", "Hi")]
    calls.clear()
    assert cli.dispatch_send(line, schemas.Send(chat_id="a", text="Hi"))["status"] == "dispatched"
    assert calls == [("prepare", "a", "Hi"), ("send", "a", "bound")]
    calls.clear()
    cli.dispatch_send(line, schemas.Send(chat_id="a", confirm="bound"))
    assert calls == [("send", "a", "bound")]


def test_cli_invalid_content_fails_before_browser_or_state(tmp_path):
    process = subprocess.run(
        [
            sys.executable,
            str(SOURCE / "line_cli.py"),
            "send",
            "--chat-id",
            "a",
            "--text",
            "hi",
            "--sticker-id",
            "s",
        ],
        cwd=tmp_path,
        env=dict(os.environ, AUTOMATA_LINE_PROFILE=str(tmp_path / "unused")),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert process.returncode == 2
    assert json.loads(process.stderr)["code"] == "INVALID_ARGUMENT"
    assert not (tmp_path / ".agents").exists()


def test_read_filter_equal_time_and_date_bounds():
    from reading_api import select_messages

    messages = [
        {"id": x, "timestamp_ms": t, "text": x} for t, x in [(1, "a"), (2, "b"), (2, "c"), (3, "d")]
    ]
    selected, more = select_messages(messages, {}, 2, False, 10, after=(2, "b"), until_ms=3)
    assert [m["id"] for m in selected] == ["c"] and not more
    selected, more = select_messages(
        messages, {}, None, False, 2, before=(3, "d"), newest_first=True
    )
    assert [m["id"] for m in selected] == ["c", "b"] and more
