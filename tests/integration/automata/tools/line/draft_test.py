"""Local Chromium fixtures only: never connects to LINE or sends real messages."""

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
pytest.importorskip("dictify")
TOOL_PATH = Path(__file__).parents[5] / "src/automata/tools/line/line_send.py"
sys.path.insert(0, str(TOOL_PATH.parent))
spec = importlib.util.spec_from_file_location("line_tool", TOOL_PATH)
line = importlib.util.module_from_spec(spec)
spec.loader.exec_module(line)

HTML = """<div class="chatroom-module__chatroom__fixture" data-mid="group-a">
<button class="chatroomHeader-module__button_name__fixture">Fixture Group<br>(15)</button>
<textarea></textarea><div id="previews"></div></div>
<script>
const editor = document.querySelector('textarea');
window.sent = 0;
editor.addEventListener('keydown', e => {
 if(e.key === 'Enter') { e.preventDefault(); window.sent++;
 editor.value = ''; document.querySelector('#previews').innerHTML = ''; }
});
editor.addEventListener('paste', e => {
 e.preventDefault(); const file = e.clipboardData.files[0];
 const d = document.createElement('div');
 d.className = 'pastedImageList-module__image_list_item__fixture'; d.title = file.name;
 const img = document.createElement('img'); img.src=URL.createObjectURL(file);
 d.append(img); document.querySelector('#previews').append(d);
});
</script>"""


class LineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = sync_playwright().start()
        chrome = shutil.which("google-chrome")
        if not chrome:
            cls.p.stop()
            raise unittest.SkipTest("Google Chrome is required for browser fixtures")
        cls.browser = cls.p.chromium.launch(executable_path=chrome, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.p.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        line.STATE = Path(self.temp.name)
        self.page = self.browser.new_page()
        self.page.set_content(HTML)
        self.client = line.Line(self.page)

    def tearDown(self):
        self.page.close()
        self.temp.cleanup()

    def test_thai_multiline_and_send_once(self):
        draft = self.client.draft("group-a", "ทดสอบ\nHello 🙂", "Fixture Group")
        self.assertEqual(self.page.locator("textarea").input_value(), "ทดสอบ\nHello 🙂")
        self.assertEqual(self.page.evaluate("sent"), 0)
        self.assertEqual(
            self.client.send("group-a", draft["token"], "Fixture Group")["status"],
            "dispatched",
        )
        with self.assertRaises(RuntimeError):
            self.client.send("group-a", draft["token"], "Fixture Group")
        self.assertEqual(self.page.evaluate("sent"), 1)

    def test_existing_draft_and_wrong_chat(self):
        self.client.draft("group-a", "keep", "Fixture Group")
        with self.assertRaises(RuntimeError):
            self.client.draft("group-a", "replace", "Fixture Group")
        with self.assertRaises(RuntimeError):
            self.client.draft("group-b", "wrong", "Fixture Group")
        self.assertEqual(self.page.locator("textarea").input_value(), "keep")

    def test_changed_draft_rejected(self):
        draft = self.client.draft("group-a", "original", "Fixture Group")
        self.page.locator("textarea").fill("changed")
        with self.assertRaises(RuntimeError):
            self.client.send("group-a", draft["token"], "Fixture Group")
        self.assertEqual(self.page.evaluate("sent"), 0)

    def test_same_name_different_id_rejected(self):
        draft = self.client.draft("group-a", "original", "Fixture Group")
        self.page.locator(".chatroom-module__chatroom__fixture").evaluate(
            "(e)=>e.setAttribute('data-mid', 'group-b')"
        )
        with self.assertRaises(RuntimeError):
            self.client.send("group-a", draft["token"], "Fixture Group")
        self.assertEqual(self.page.evaluate("sent"), 0)

    def test_route_change_rejected(self):
        draft = self.client.draft("group-a", "original", "Fixture Group")
        self.page.evaluate("history.pushState({}, '', '#/chats/group-a/changed')")
        with self.assertRaises(RuntimeError):
            self.client.send("group-a", draft["token"], "Fixture Group")
        self.assertEqual(self.page.evaluate("sent"), 0)

    def test_legacy_token_without_identity_rejected(self):
        line.STATE.mkdir(parents=True, exist_ok=True)
        line.save_state({"token": "legacy", "digest": "unused", "status": "prepared"})
        with self.assertRaises(RuntimeError):
            self.client.send("group-a", "legacy", "Fixture Group")
        self.assertEqual(self.page.evaluate("sent"), 0)

    def test_dispatch_error_consumes_token(self):
        draft = self.client.draft("group-a", "original", "Fixture Group")
        state = line.load_state()
        state["status"] = "uncertain"
        line.save_state(state)
        with self.assertRaises(RuntimeError):
            self.client.send("group-a", draft["token"], "Fixture Group")
        self.assertEqual(self.page.evaluate("sent"), 0)

    def test_image_preparation(self):
        file = Path(self.temp.name) / "photo.png"
        file.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        result = self.client.attach("group-a", file, "Fixture Group")
        self.assertEqual(result["images"], 1)
        self.assertEqual(self.page.evaluate("sent"), 0)

    def install_picker(self, duplicate=False):
        self.page.evaluate(
            """duplicate => {
          document.querySelector('textarea').addEventListener('input', e => {
            if(e.target.value !== '@') return;
            const menu=document.createElement('div'); menu.id='picker';
            for(let i=0;i<(duplicate?2:1);i++) {
              const option=document.createElement('div'); option.role='option';
              option.innerHTML='<button data-id="member-123"><span>Test Member</span></button>';
              option.querySelector('button').onclick=()=>{
                e.target.value='\\ue26e ';
                const marker=document.createElement('span');
                marker.setAttribute('part','block mention');
                marker.textContent='native';
                document.querySelector('.chatroom-module__chatroom__fixture').append(marker);
                menu.remove();
              };
              menu.append(option);
            }
            document.body.append(menu);
          });
        }""",
            duplicate,
        )

    def test_native_mention_and_suffix(self):
        self.install_picker()
        result = self.client.mention("group-a", "Test Member", "สวัสดี\nHello 🙂", "Fixture Group")
        self.assertEqual(result["mention"], "Test Member")
        self.assertEqual(self.page.locator('[part~="mention"]').count(), 1)
        self.assertTrue(self.page.locator("textarea").input_value().endswith("สวัสดี\nHello 🙂"))
        self.assertEqual(self.page.evaluate("sent"), 0)
        # Same visible text with a removed mention must fail the draft fingerprint.
        self.page.locator('[part~="mention"]').evaluate("(e)=>e.remove()")
        with self.assertRaises(RuntimeError):
            self.client.send("group-a", result["token"], "Fixture Group")

    def test_ambiguous_mention_rejected(self):
        self.install_picker(duplicate=True)
        with self.assertRaises(RuntimeError):
            self.client.mention("group-a", "Test Member", "", "Fixture Group")
        self.assertEqual(self.page.evaluate("sent"), 0)

    def test_all_mention_rejected(self):
        with self.assertRaises(RuntimeError):
            self.client.mention("group-a", "All", "", "Fixture Group")
        self.assertEqual(self.page.locator("textarea").input_value(), "")

    def test_uncertain_receipt_blocks_fresh_preparation_even_when_empty(self):
        line.save_state({"token": "uncertain", "status": "uncertain"})
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            self.client.draft("group-a", "do not duplicate")
        self.assertEqual(self.page.locator("textarea").input_value(), "")
        self.assertEqual(self.page.evaluate("sent"), 0)
