"""Local fixtures and failure injection; never sends real LINE messages."""

import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("dictify")
TOOL_ROOT = Path(__file__).parents[5] / "src/automata/tools/line"
sys.path.insert(0, str(TOOL_ROOT))
import reading_api as api  # noqa: E402
import reading_state as storage  # noqa: E402

pytest.importorskip("playwright")


class BrowserReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright

        cls.playwright = sync_playwright().start()
        chrome = shutil.which("google-chrome")
        if not chrome:
            cls.playwright.stop()
            raise unittest.SkipTest("Google Chrome is required for browser fixtures")
        cls.browser = cls.playwright.chromium.launch(executable_path=chrome, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        import line_send as line_tool

        self.page = self.browser.new_page()
        self.page.set_content("""<input placeholder="Search chat list">
        <div class="chatroom-module__chatroom__fixture" data-mid="chat1">
        <button class="chatroomHeader-module__button_name__fixture">Fixture</button>
        <textarea></textarea><div class="message_list"
        style="height:100px;overflow:auto;display:flex;flex-direction:column-reverse">
        <div class="messageDate-module__date_wrap__fixture"
        data-message-select-id="100-" data-timestamp="100">Today</div>
        <div data-message-select-id="100-m1" data-timestamp="100" data-mid="sender">
        <span class="username-module__username__fixture">A<img alt="🙂"></span>
        <div class="message-module__content_inner__fixture">
        <div class="textMessageContent-module__text__fixture">Hi <img alt="🙂"></div></div></div>
        <div data-message-select-id="100-m2" data-timestamp="100" data-mid="sender"
        data-message-content="Photos">
        <div class="message-module__content_inner__fixture">
        <div class="imageMessageContent-fixture" data-message-id="m2"></div></div></div>
        </div></div>""")
        self.reader = api.Reader(line_tool.Line(self.page), "about:blank", line_tool.HEADER)

    def tearDown(self):
        self.page.close()

    def test_date_separator_excluded_and_equal_timestamps_retained(self):
        messages = self.reader.extract("chat1")
        self.assertEqual([m["id"] for m in messages], ["100-m1", "100-m2"])
        self.assertEqual(messages[0]["text"], "Hi 🙂")
        self.assertEqual(messages[0]["sender"], "A🙂")
        self.assertEqual(messages[1]["kind"], "image")

    def test_missing_message_id_timestamp_fails_closed(self):
        self.page.locator('[data-message-select-id="100-m1"]').evaluate(
            '(e)=>e.removeAttribute("data-timestamp")'
        )
        with self.assertRaises(storage.ApiError) as error:
            self.reader.extract("chat1")
        self.assertEqual(error.exception.code, "MESSAGE_ID_MISSING")

    def test_draft_blocks_read_without_overwrite(self):
        self.page.locator("textarea").fill("human draft")
        with self.assertRaises(storage.ApiError) as error:
            self.reader.extract("chat1")
        self.assertEqual(error.exception.code, "DRAFT_PRESENT")
        self.assertEqual(self.page.locator("textarea").input_value(), "human draft")

    def test_missing_anchor_reports_gap(self):
        with patch.object(self.reader, "open_id", return_value="Fixture"):
            result = self.reader.read(
                "chat1", {"anchor_id": "missing", "seen": {}}, 0, max_scrolls=0
            )
        self.assertTrue(result["coverage"]["history_gap"])
        self.assertFalse(result["coverage"]["boundary_reached"])

    def test_existing_anchor_reached(self):
        with patch.object(self.reader, "open_id", return_value="Fixture"):
            result = self.reader.read(
                "chat1", {"anchor_id": "100-m1", "seen": {}}, 0, max_scrolls=0
            )
        self.assertTrue(result["coverage"]["checkpoint_found"])
        self.assertFalse(result["coverage"]["history_gap"])

    def test_wrong_chat_identity_blocks(self):
        with self.assertRaises(storage.ApiError):
            self.reader.extract("different")

    def test_after_cursor_returns_newer_without_duplicate(self):
        with patch.object(self.reader, "open_id", return_value="Fixture"):
            result = self.reader.read(
                "chat1", {}, None, unseen=False, max_scrolls=0, after=(100, "100-m1")
            )
        self.assertEqual([m["id"] for m in result["messages"]], ["100-m2"])
        self.assertTrue(result["coverage"]["cursor_found"])

    def test_missing_cursor_returns_no_misleading_continuation(self):
        for direction in ("after", "before"):
            with patch.object(self.reader, "open_id", return_value="Fixture"):
                result = self.reader.read(
                    "chat1", {}, None, unseen=False, max_scrolls=0, **{direction: (99, "missing")}
                )
            self.assertEqual(result["messages"], [])
            self.assertEqual(result["coverage"]["code"], "HISTORY_GAP")

    def test_new_arrival_appears_on_next_after_read(self):
        self.page.locator(".message_list").evaluate("""e => {
            const m=document.createElement('div');
            m.dataset.messageSelectId='101-m3'; m.dataset.timestamp='101';
            m.innerHTML='<div class="textMessageContent-module__text__fixture">new</div>';
            e.prepend(m);
        }""")
        with patch.object(self.reader, "open_id", return_value="Fixture"):
            result = self.reader.read(
                "chat1", {}, None, unseen=False, max_scrolls=0, after=(100, "100-m2")
            )
        self.assertEqual([m["id"] for m in result["messages"]], ["101-m3"])

    def test_stalled_loading_is_unknown_not_complete_history(self):
        with patch.object(self.reader, "open_id", return_value="Fixture"):
            result = self.reader.read("chat1", {}, None, max_scrolls=4)
        coverage = result["coverage"]
        self.assertEqual(coverage["reason"], "no_more_loaded_messages")
        self.assertEqual(coverage["older_history_availability"], "unknown")
        self.assertTrue(coverage["older_history_unverified"])
        self.assertFalse(coverage["result_overflow"])
        self.assertEqual(coverage["freshness"], "unknown")
        self.assertEqual(coverage["newest_loaded_timestamp_ms"], 100)
        self.assertTrue(coverage["observed_at"])

    def test_visible_chat_list_newer_evidence_and_result_overflow_are_separate(self):
        self.page.evaluate("""() => {
            const row=document.createElement('div');row.dataset.mid='chat1';
            row.className='chatlistItem-module__chatlist_item__fixture';
            row.innerHTML='<time datetime="1970-01-01T00:00:02Z"></time>';
            document.body.append(row);
        }""")
        with patch.object(self.reader, "open_id", return_value="Fixture"):
            result = self.reader.read("chat1", {}, None, limit=1, max_scrolls=0)
        coverage = result["coverage"]
        self.assertEqual(coverage["freshness"], "newer_chat_list_evidence")
        self.assertEqual(coverage["chat_list_latest_timestamp_ms"], 2000)
        self.assertTrue(coverage["result_overflow"])
        self.assertEqual(coverage["reason"], "scroll_limit")
        self.assertEqual(coverage["older_history_availability"], "unknown")
        self.assertFalse(coverage["requested_window"]["returned_all_loaded_matches"])

    def test_state_unchanged_by_read(self):
        entry = {"anchor_id": "100-m1", "seen": {}}
        with patch.object(self.reader, "open_id", return_value="Fixture"):
            self.reader.read("chat1", entry, 0, max_scrolls=0)
        self.assertEqual(entry, {"anchor_id": "100-m1", "seen": {}})
