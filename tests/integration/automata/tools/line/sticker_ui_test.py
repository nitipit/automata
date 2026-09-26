"""Local headless popup fixtures only; never connect to an account or real LINE."""

import importlib
import importlib.util
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
SOURCE = Path(__file__).parents[5] / "src/automata/tools/line"
BASE = "https://fixture.invalid/index.html"
POPUP = "https://fixture.invalid/popup.html"
CDN = "https://stickershop.line-scdn.net"
ASSET = CDN + "/stickershop/v1/sticker/263/android/sticker.png"
NONCE = "1141b5a0-8d49-4706-854d-19515dafea1b"
MAIN_HTML = f"""<div class="chatroom-module__chatroom__fixture" data-mid="chat-one">
<button class="chatroomHeader-module__button_name__fixture">Fixture Recipient</button>
<textarea></textarea><button aria-label="Select sticker"
 onclick="window.open('{POPUP}')">Stickers</button><div id="messages"></div></div>
<script>
window.sent=0;
window.emitSticker=()=>{{
 window.sent++;
 const m=document.createElement('div');m.dataset.messageSelectId='new-'+window.sent;
 m.dataset.direction='reverse';
 m.innerHTML='<img data-product-id="4" src="{ASSET}?{NONCE}">';
 document.getElementById('messages').append(m);
}};
</script>"""
POPUP_HTML = f"""<button role="tab" aria-label="sticker package" aria-selected="true">
<img src="{CDN}/stickershop/v1/product/4/android/tab_on.png" alt="Fixture package"></button>
<div data-sticker-key="4/263" class="sticker" onclick="window.opener.emitSticker()">
<img src="{ASSET}?{NONCE}" data-product-id="4" data-is-owned="true"
 data-is-effect-sticker="false" style="width:30px;height:30px"></div>"""


@pytest.fixture(scope="module")
def browser():
    chrome = shutil.which("google-chrome")
    if not chrome:
        pytest.skip("Google Chrome required for local browser fixtures")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chrome, headless=True)
        yield browser
        browser.close()


@pytest.fixture
def setup(browser, monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(SOURCE))
    ui = importlib.import_module("sticker_ui")
    api = importlib.import_module("sticker_api")
    monkeypatch.setattr(ui, "INDEX", BASE)
    monkeypatch.setattr(ui, "POPUP", POPUP)
    spec = importlib.util.spec_from_file_location(
        "line_sticker_ui_fixture", SOURCE / "line_send.py"
    )
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    monkeypatch.setattr(tool, "STATE", tmp_path)
    context = browser.new_context()

    def route(request):
        url = request.request.url
        if url.startswith(BASE):
            request.fulfill(content_type="text/html", body=MAIN_HTML)
        elif url.startswith(POPUP):
            request.fulfill(content_type="text/html", body=POPUP_HTML)
        else:
            request.fulfill(status=204)  # No external asset/network requests.

    context.route("**/*", route)
    page = context.new_page()
    page.goto(BASE + "#/chats/chat-one")
    line = tool.Line(page)
    yield SimpleNamespace(
        ui=ui,
        api=api,
        line=line,
        page=page,
        context=context,
        tool=tool,
        service=api.StickerOperations(line, tmp_path, ui.open_picker),
    )
    context.close()


def test_real_popup_fixture_catalog_and_metadata_preparation_never_dispatch(setup):
    result = setup.service.inspect("chat-one", "4", limit=1)
    assert result["catalog"]["packages"][0]["package_id"] == "4"
    selected = result["catalog"]["stickers"][0]
    assert selected["sticker_id"] == "263" and selected["preview_url"] == ASSET
    assert result["cleanup"]["closed"]
    token = setup.service.prepare("chat-one", "4", "263")["token"]
    assert token.startswith("sticker:")
    assert setup.page.evaluate("sent") == 0
    assert setup.context.pages == [setup.page]


def test_existing_send_routes_sticker_token_once_with_new_evidence(setup):
    token = setup.service.prepare("chat-one", "4", "263")["token"]
    result = setup.line.send("chat-one", token)
    assert result["status"] == "dispatched"
    assert result["evidence"]["message_id"] == "new-1"
    assert result["cleanup"]["closed"]
    with pytest.raises(setup.api.StickerError):
        setup.line.send("chat-one", token)
    assert setup.page.evaluate("sent") == 1
    assert setup.context.pages == [setup.page]


def test_normal_text_send_is_unchanged_with_uncertain_sticker_receipt(setup):
    setup.service.prepare("chat-one", "4", "263")
    state = setup.service.load()
    state["status"] = "uncertain"
    setup.service.save(state)
    setup.page.locator("textarea").evaluate("""e=>e.addEventListener('keydown', ev=>{
      if(ev.key==='Enter'){ev.preventDefault();e.value='';window.sent++;}
    })""")
    text = setup.line.draft("chat-one", "ordinary text")
    assert setup.line.send("chat-one", text["token"])["status"] == "dispatched"
    assert setup.service.load()["status"] == "uncertain"
    assert setup.page.evaluate("sent") == 1


def test_preexisting_popup_is_refused_and_never_closed(setup):
    with setup.context.expect_page() as waiting:
        setup.page.get_by_role("button", name="Select sticker").click()
    existing = waiting.value
    existing.wait_for_load_state("domcontentloaded")
    with pytest.raises(setup.api.StickerError) as error:
        setup.service.prepare("chat-one", "4", "263")
    assert error.value.code == "STICKER_PICKER_AMBIGUOUS"
    assert not existing.is_closed() and setup.page.evaluate("sent") == 0


def test_popup_opener_must_match_even_if_recipient_route_matches(setup):
    foreign = setup.context.new_page()
    foreign.goto(POPUP)
    picker = setup.ui.Picker(setup.line, "chat-one", foreign)
    with pytest.raises(setup.api.StickerError, match="binding changed"):
        picker.guard()
    assert not foreign.is_closed()


def test_route_change_prevents_tile_click_and_closes_owned_popup(setup):
    picker = setup.ui.open_picker(setup.line, "chat-one")
    selected = picker.find("4", "263")
    setup.page.evaluate("history.pushState({},'', '#/chats/chat-one/changed')")
    with pytest.raises(setup.api.StickerError):
        picker.click_once(selected)
    picker.close()
    assert setup.page.evaluate("sent") == 0


def test_ambiguous_tile_and_effect_sticker_are_rejected(setup):
    picker = setup.ui.open_picker(setup.line, "chat-one")
    tile = picker.popup.locator('[data-sticker-key="4/263"]')
    tile.locator("img").evaluate("e=>e.dataset.isEffectSticker='true'")
    with pytest.raises(setup.api.StickerError):
        picker.find("4", "263")
    tile.locator("img").evaluate("e=>e.dataset.isEffectSticker='false'")
    tile.evaluate("e=>e.after(e.cloneNode(true))")
    with pytest.raises(setup.api.StickerError):
        picker.find("4", "263")
    picker.close()
    assert setup.page.evaluate("sent") == 0


def test_uuid_cache_buster_changes_preserve_same_identity(setup):
    picker = setup.ui.open_picker(setup.line, "chat-one")
    first = picker.find("4", "263")
    picker.popup.locator('[data-sticker-key="4/263"] img').evaluate(
        "(e,url)=>e.src=url", ASSET + "?794a8249-1d82-4ce8-a540-563e613cbced"
    )
    assert picker.find("4", "263") == first
    picker.close()


@pytest.mark.parametrize(
    "suffix", ["?version=2", "?cache=" + NONCE, "?" + NONCE + "&a=1", "#fragment"]
)
def test_other_url_semantics_are_rejected_never_stripped(setup, suffix):
    with pytest.raises(setup.api.StickerError):
        setup.ui.asset_identity(ASSET + suffix)


@pytest.mark.parametrize(
    "url",
    [
        "http://stickershop.line-scdn.net/stickershop/v1/sticker/263/android/sticker.png",
        "https://other.invalid/stickershop/v1/sticker/263/android/sticker.png",
        "https://user@stickershop.line-scdn.net/stickershop/v1/sticker/263/android/sticker.png",
        CDN + "/stickershop/v1/sticker/263/android/effect.png",
    ],
)
def test_unknown_asset_shapes_fail_closed(setup, url):
    with pytest.raises(setup.api.StickerError):
        setup.ui.asset_identity(url)


def test_old_outgoing_row_and_nonuuid_query_do_not_establish_new_dispatch(setup, monkeypatch):
    picker = setup.ui.open_picker(setup.line, "chat-one")
    selected = picker.find("4", "263")
    setup.page.evaluate("emitSticker()")  # Fixture-only old message, not a real send.
    baseline = picker.outgoing_ids()
    original = setup.page.wait_for_function

    def short_wait(expression, **kwargs):
        return original(expression, **dict(kwargs, timeout=150))

    monkeypatch.setattr(setup.page, "wait_for_function", short_wait)
    with pytest.raises(Exception, match="Timeout"):
        picker.wait_outgoing(selected, baseline)
    setup.page.evaluate("emitSticker()")
    setup.page.locator('[data-message-select-id="new-2"] img').evaluate(
        "(e,url)=>e.src=url", ASSET + "?semantic-change=yes"
    )
    with pytest.raises(Exception, match="Timeout"):
        picker.wait_outgoing(selected, baseline)
    picker.close()
