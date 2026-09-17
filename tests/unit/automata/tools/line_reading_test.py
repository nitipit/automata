"""Local fixtures and failure injection; never sends real LINE messages."""

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("dictify")
TOOL_ROOT = Path(__file__).parents[4] / "src/automata/tools/line"
sys.path.insert(0, str(TOOL_ROOT))
import reading_api as api  # noqa: E402
import reading_state as storage  # noqa: E402


def message(identity="m1", stamp=100, text="hello"):
    return {
        "id": identity,
        "timestamp_ms": stamp,
        "text": text,
        "sender_id": "sender",
        "sender": "Person",
        "kind": "text",
        "timestamp": "fixture",
        "direction": "",
        "attachment_ids": [],
        "truncated": False,
    }


def result(messages, **coverage):
    selected, more = api.select_messages(messages, {}, 0, True, 100)
    return {
        "chat": {"id": "chat1", "name": "Fixture"},
        "messages": selected,
        "anchor_candidate": messages[-1]["id"] if messages else "",
        "coverage": dict(boundary_reached=True, more=more, history_gap=False, **coverage),
    }


class ReadingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = storage.ReadingStore(self.root, "journal")
        self.output = self.root / "LINE.md"
        self.output.write_text("Existing user content\n")

    def tearDown(self):
        self.temp.cleanup()

    def commit(self):
        chats = api.updated_chats({}, [result([message()])], 0)
        return self.store.commit(self.store.load(), self.output, "\nNew entry\n", chats)

    def test_success_and_namespace_isolation(self):
        state = self.commit()
        self.assertEqual(state["revision"], 1)
        self.assertEqual(state["chats"]["chat1"]["anchor_id"], "m1")
        self.assertIn("Existing user content", self.output.read_text())
        self.assertFalse(self.store.pending.exists())
        self.assertEqual(storage.ReadingStore(self.root, "other").load()["chats"], {})

    def test_failed_output_write_no_checkpoint(self):
        real = storage.atomic

        def fail(path, data):
            if Path(path) == self.output:
                raise OSError("write failed")
            real(path, data)

        with patch.object(storage, "atomic", side_effect=fail):
            with self.assertRaises(OSError):
                self.commit()
        self.assertEqual(self.store.load()["revision"], 0)
        self.assertEqual(self.output.read_text(), "Existing user content\n")
        self.assertTrue(self.store.recover())
        self.assertEqual(self.store.load()["revision"], 1)
        self.assertEqual(self.output.read_text().count("New entry"), 1)

    def test_crash_after_output_before_checkpoint(self):
        real = storage.atomic

        def fail(path, data):
            if Path(path) == self.store.path:
                raise OSError("crash after append")
            real(path, data)

        with patch.object(storage, "atomic", side_effect=fail):
            with self.assertRaises(OSError):
                self.commit()
        self.assertEqual(self.store.load()["revision"], 0)
        self.store.recover()
        self.assertEqual(self.output.read_text().count("New entry"), 1)
        self.assertFalse(self.store.recover())

    def test_crash_after_checkpoint_before_pending_removal(self):
        real = Path.unlink

        def fail(path, *args, **kwargs):
            if path == self.store.pending:
                raise OSError("crash")
            return real(path, *args, **kwargs)

        with patch.object(Path, "unlink", fail):
            with self.assertRaises(OSError):
                self.commit()
        self.assertEqual(self.store.load()["revision"], 1)
        self.store.recover()
        self.assertEqual(self.output.read_text().count("New entry"), 1)

    def test_pending_conflict_no_overwrite(self):
        real = storage.atomic

        def fail(path, data):
            if Path(path) == self.store.path:
                raise OSError("crash")
            real(path, data)

        with patch.object(storage, "atomic", side_effect=fail):
            with self.assertRaises(OSError):
                self.commit()
        self.output.write_text("Human changed file")
        with self.assertRaises(storage.ApiError) as error:
            self.store.recover()
        self.assertEqual(error.exception.code, "OUTPUT_CONFLICT")
        self.assertEqual(self.output.read_text(), "Human changed file")

    def test_output_binding_and_integrity(self):
        state = self.commit()
        with self.assertRaises(storage.ApiError):
            self.store.check_output(state, self.root / "different.md")
        self.output.write_text("truncated")
        with self.assertRaises(storage.ApiError):
            self.store.check_output(state, self.output)

    def test_manual_append_allowed(self):
        state = self.commit()
        with self.output.open("a") as f:
            f.write("User appended note")
        self.store.check_output(state, self.output)

    def test_invalid_state_fails_closed(self):
        state = self.commit()
        state["chats"]["chat1"]["seen"]["m1"]["timestamp_ms"] = "bad"
        self.store.path.write_text(json.dumps(state))
        with self.assertRaises(storage.ApiError):
            self.store.load()

    def test_invalid_consumer(self):
        with self.assertRaises(storage.ApiError):
            storage.ReadingStore(self.root, "../escape")

    def test_equal_timestamps_not_deduplicated(self):
        messages = [message("m1"), message("m2")]
        saved = api.updated_chats({}, [result(messages)], 0)["chat1"]
        selected, more = api.select_messages(messages, saved, 0, True, 100)
        self.assertEqual(selected, [])
        self.assertEqual(len(saved["seen"]), 2)
        self.assertFalse(more)

    def test_mobile_read_badge_not_an_input(self):
        saved = api.updated_chats({}, [result([message()])], 0)["chat1"]
        selected, _ = api.select_messages([message(), message("new", 101)], saved, 0, True, 100)
        self.assertEqual([m["id"] for m in selected], ["new"])

    def test_edit_same_id(self):
        saved = api.updated_chats({}, [result([message()])], 0)["chat1"]
        selected, _ = api.select_messages([message(text="edited")], saved, 0, True, 100)
        self.assertEqual(selected[0]["change"], "edited")

    def test_newest_pagination_equal_timestamps(self):
        messages = [message("a"), message("b"), message("c", 101)]
        first, more = api.select_messages(messages, {}, None, False, 2, newest_first=True)
        self.assertTrue(more)
        last = first[-1]
        second, _ = api.select_messages(
            messages, {}, None, False, 2, (last["timestamp_ms"], last["id"]), newest_first=True
        )
        self.assertEqual([m["id"] for m in first + second], ["c", "b", "a"])

    def test_no_anchor_advance_on_gap_or_backlog(self):
        old = api.updated_chats({}, [result([message()])], 0)
        for field in ("history_gap", "more"):
            update = result([message("m2", 101)])
            update["coverage"][field] = True
            new = api.updated_chats(old, [update], 0)
            self.assertEqual(new["chat1"]["anchor_id"], "m1")
            self.assertIn("m2", new["chat1"]["seen"])

    def test_no_bootstrap_anchor_when_boundary_unverified(self):
        update = result([message()])
        update["coverage"]["boundary_reached"] = False
        state = api.updated_chats({}, [update], 0)
        self.assertEqual(state["chat1"]["anchor_id"], "")

    def test_since_requires_timezone(self):
        with self.assertRaises(storage.ApiError):
            api.parse_since("2026-09-17T10:00:00")
        self.assertEqual(api.parse_since("1970-01-01T07:00:00+07:00"), 0)

    def test_schedule_gate(self):
        for hour, expected in [(7, False), (8, True), (19, True), (20, False)]:
            self.assertEqual(api.in_window("08:00-20:00", datetime(2026, 9, 17, hour)), expected)
