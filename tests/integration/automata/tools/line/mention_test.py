"""Public composer getter fixtures; no real profile, account, or LINE sends."""

import json
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("dictify")
sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
SOURCE = Path(__file__).parents[5] / "src/automata/tools/line"
sys.path.insert(0, str(SOURCE))
import line_send as line  # noqa: E402

HTML = """<div class="chatroom-module__chatroom__fixture" data-mid="group-a">
<button class="chatroomHeader-module__button_name__fixture">Fixture Group</button>
<textarea-ex></textarea-ex></div><script>
window.sent=0; window.clicks=0; window.duplicate=false; window.optionCountAtEnter=0;
window.wrongMention=false; window.tamperOnSuffix=false; window.inactiveOption=false;
window.missingOnInsert=false; window.lastActiveMember='All';
const host=document.querySelector('textarea-ex');
const shadow=host.attachShadow({mode:'open'});
shadow.innerHTML='<textarea></textarea>';
const editor=shadow.querySelector('textarea');
host.parts=[];
Object.defineProperty(host,'value',{configurable:true,get(){
  if(window.missingOnInsert&&this.parts.some(p=>p?.type==='mention'))return undefined;
  return this.parts;
}});
function insertMention(name,id) {
  window.lastActiveMember=name;
  const data=name==='All'?{A:'1'}:{M:id};
  host.parts=[{type:'mention',altText:'@'+name,extra:{data}},' '];
  editor.value='\\ue26e ';
  const marker=document.createElement('span'); marker.setAttribute('part','block mention');
  marker.textContent='native'; shadow.append(marker);
  document.querySelector('#picker')?.remove();
}
function menu(query) {
  document.querySelector('#picker')?.remove();
  const picker=document.createElement('div'); picker.id='picker';
  let members=[['All',''],['Test Member','member-123'],['Mallika','member-mallika']];
  if(window.duplicate)members.push(['Test Member','member-456']);
  const visible=query?members.filter(([name])=>
    name.toLowerCase().includes(query.toLowerCase())):members;
  const active=Math.max(0,visible.findIndex(([name])=>name===window.lastActiveMember));
  for(const [i,[name,id]] of visible.entries()) {
    const option=document.createElement('div');option.role='option';
    option.setAttribute('aria-selected',String(i===active&&!window.inactiveOption));
    const button=document.createElement('button');button.dataset.id=id;
    const label=document.createElement('span');label.textContent=name;
    button.append(label);option.append(button);picker.append(option);
    // Legacy clicking the named button inserts active All, not its own ID.
    button.onclick=()=>{window.clicks++;insertMention('All','');};
  }
  document.body.append(picker);
}
editor.addEventListener('input',()=>{
  if(!shadow.querySelector('[part~=mention]')) {
    host.parts=[editor.value];
    if(editor.value.startsWith('@'))menu(editor.value.slice(1));
  } else {
    host.parts[1]=editor.value.slice(1);
    if(window.tamperOnSuffix)host.parts[0].extra.data={A:'1'};
  }
});
editor.addEventListener('keydown',e=>{
  if(e.key!=='Enter')return;
  e.preventDefault();
  const selected=document.querySelector('[role=option][aria-selected=true] button');
  if(selected){
    window.optionCountAtEnter=document.querySelectorAll('[role=option]').length;
    insertMention(window.wrongMention?'All':selected.textContent,
                  selected.dataset.id);return;
  }
  window.sent++;editor.value='';host.parts=[];
  shadow.querySelectorAll('[part~=mention]').forEach(e=>e.remove());
});
</script>"""


@pytest.fixture(scope="module")
def browser():
    chrome = shutil.which("google-chrome")
    if not chrome:
        pytest.skip("Google Chrome required for local composer fixtures")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=chrome, headless=True)
        yield b
        b.close()


@pytest.fixture
def client(browser, tmp_path, monkeypatch):
    monkeypatch.setattr(line, "STATE", tmp_path)
    page = browser.new_page()
    page.set_content(HTML)
    page.set_default_timeout(500)
    yield line.Line(page)
    page.close()


def test_keyboard_individual_identity_suffix_and_one_shot(client):
    draft = client.mention("group-a", "Test Member", "สวัสดี\nHello 🙂", member_id="member-123")
    expected = {"kind": "individual", "name": "Test Member", "member_id": "member-123"}
    assert draft["mention_identity"] == expected
    assert (
        line.load_state()["expected_mention"] == line.load_state()["verified_mention"] == expected
    )
    assert line.load_state()["version"] == 1
    assert line.load_state()["kind"] == "composer"
    assert client.page.evaluate("sent") == 0, "Enter with active picker inserts, never dispatches"
    assert client.page.evaluate("clicks") == 0
    assert client.room.locator("textarea").input_value().endswith("สวัสดี\nHello 🙂")
    assert client.page.get_by_role("option").count() == 0
    assert client.send("group-a", draft["token"])["status"] == "dispatched"
    assert client.page.evaluate("sent") == 1
    with pytest.raises(RuntimeError):
        client.send("group-a", draft["token"])
    assert client.page.evaluate("sent") == 1


def test_dispatch_error_after_enter_is_uncertain_and_never_replayed(client, monkeypatch):
    draft = client.mention("group-a", "Test Member", "hello")
    locator_type = type(client.room.locator("textarea"))
    original = locator_type.press

    def fail_after_dispatch(locator, key, *args, **kwargs):
        original(locator, key, *args, **kwargs)
        raise RuntimeError("fixture interrupted after dispatch")

    monkeypatch.setattr(locator_type, "press", fail_after_dispatch)
    with pytest.raises(RuntimeError, match="interrupted"):
        client.send("group-a", draft["token"])
    assert line.load_state()["status"] == "uncertain"
    assert client.page.evaluate("sent") == 1
    with pytest.raises(RuntimeError, match="uncertain"):
        client.send("group-a", draft["token"])
    with pytest.raises(RuntimeError, match="uncertain"):
        client.mention_all("group-a", "never duplicate")
    assert client.page.evaluate("sent") == 1


def test_explicit_all_and_no_name_fallback(client):
    with pytest.raises(RuntimeError):
        client.mention("group-a", "All", "")
    assert client.room.locator("textarea").input_value() == ""
    draft = client.mention_all("group-a", "hello")
    assert draft["mention_identity"] == {"kind": "all", "name": "All", "member_id": None}
    assert client.page.evaluate("sent") == 0
    assert client.send("group-a", draft["token"])["status"] == "dispatched"


def test_all_query_overrides_remembered_individual_option_after_owned_clear(client):
    client.mention("group-a", "Test Member", "hello")
    assert client.page.evaluate("lastActiveMember") == "Test Member"
    # Simulate clearing the owned draft, retaining the picker's last active choice.
    client.page.evaluate("""() => {
        host.parts=[];editor.value='';
        shadow.querySelectorAll('[part~=mention]').forEach(e=>e.remove());
    }""")
    client.room.locator("textarea").fill("@")
    all_option = client.page.get_by_role("option").filter(
        has=client.page.get_by_text("All", exact=True)
    )
    assert all_option.get_attribute("aria-selected") == "false"
    client.room.locator("textarea").fill("")
    client.page.evaluate("document.querySelector('#picker')?.remove()")
    draft = client.mention_all("group-a", "All suffix 🙂")
    assert draft["mention_identity"] == {"kind": "all", "name": "All", "member_id": None}
    assert client.page.get_by_role("option").count() == 0
    assert client.page.evaluate("sent") == 0
    assert client.page.evaluate("clicks") == 0
    assert client.room.locator("textarea").input_value().endswith("All suffix 🙂")
    assert client.page.evaluate("optionCountAtEnter") == 2, "exact All need not be the only option"


def test_legacy_click_failure_is_represented_by_fixture(client):
    client.room.locator("textarea").fill("@")
    options = client.page.get_by_role("option")
    assert options.first.get_attribute("aria-selected") == "true"
    target = options.filter(has=client.page.get_by_text("Test Member", exact=True))
    assert target.locator("button").get_attribute("data-id") == "member-123"
    target.locator("button").click()
    assert client.page.locator("textarea-ex").evaluate("e=>e.value[0].extra.data") == {"A": "1"}
    assert client.page.evaluate("sent") == 0
    assert not (line.STATE / "draft.json").exists()


@pytest.mark.parametrize("flag", ["wrongMention", "tamperOnSuffix"])
def test_wrong_semantic_selection_or_suffix_stops_before_prepare(client, flag):
    client.page.evaluate("flag=>window[flag]=true", flag)
    with pytest.raises(RuntimeError, match="identity"):
        client.mention("group-a", "Test Member", "suffix")
    assert client.page.evaluate("sent") == 0
    assert not (line.STATE / "draft.json").exists()


def test_missing_semantic_metadata_after_insert_stops_before_prepare(client):
    client.page.evaluate("missingOnInsert=true")
    with pytest.raises(RuntimeError, match="Malformed public composer"):
        client.mention("group-a", "Test Member", "")
    assert client.room.locator("[part~=mention]").count() == 1
    assert client.page.evaluate("sent") == 0
    assert not (line.STATE / "draft.json").exists()


def test_duplicate_name_and_wrong_expected_id_stop(client):
    client.page.evaluate("duplicate=true")
    with pytest.raises(RuntimeError, match="ambiguous"):
        client.mention("group-a", "Test Member", "")
    assert client.page.evaluate("sent") == 0
    client.room.locator("textarea").fill("")
    with pytest.raises(RuntimeError, match="Member ID"):
        client.mention("group-a", "Test Member", "", member_id="wrong-id")
    assert not (line.STATE / "draft.json").exists()


@pytest.mark.parametrize(
    "parts",
    [
        None,
        {},
        [None],
        [{"type": "mention"}],
        [],
        [
            {"type": "mention", "altText": "@All", "extra": {"data": {"A": "1"}}},
            {"type": "mention", "altText": "@Test Member", "extra": {"data": {"M": "member-123"}}},
        ],
        [{"type": "mention", "altText": "@Test Member", "extra": {"data": {"M": "", "A": "1"}}}],
        [{"type": "mention", "altText": "@All", "extra": {"data": {"A": 1}}}],
        [{"type": "mention", "altText": "@Test Member", "extra": {"data": {"M": "bad id"}}}],
    ],
)
def test_missing_mixed_malformed_composer_metadata_blocks_confirm(client, parts):
    draft = client.mention("group-a", "Test Member", "hello")
    client.page.locator("textarea-ex").evaluate("(e,v)=>e.parts=v", parts)
    with pytest.raises(RuntimeError):
        client.send("group-a", draft["token"])
    assert client.page.evaluate("sent") == 0
    assert line.load_state()["status"] == "prepared"


def test_id_tamper_without_visible_text_change_blocks_confirm(client):
    draft = client.mention("group-a", "Test Member", "hello")
    raw = client.room.locator("textarea").input_value()
    client.page.locator("textarea-ex").evaluate("e=>e.parts[0].extra.data.M='member-456'")
    assert client.room.locator("textarea").input_value() == raw
    with pytest.raises(RuntimeError, match="identity changed"):
        client.send("group-a", draft["token"])
    assert client.page.evaluate("sent") == 0


def test_inactive_option_stops_before_enter_or_prepare(client):
    client.page.evaluate("inactiveOption=true")
    from playwright.sync_api import expect

    # Bound only the fixture assertion wait; production keeps its normal timeout.
    expect.set_options(timeout=100)
    try:
        with pytest.raises(AssertionError, match="aria-selected"):
            client.mention("group-a", "Test Member", "")
    finally:
        expect.set_options(timeout=5000)
    assert client.page.evaluate("sent") == 0
    assert client.room.locator("[part~=mention]").count() == 0
    assert not (line.STATE / "draft.json").exists()


def test_expected_id_can_pin_one_duplicate_name_when_active(client):
    client.page.evaluate("duplicate=true")
    draft = client.mention("group-a", "Test Member", "", member_id="member-123")
    assert draft["mention_identity"]["member_id"] == "member-123"
    assert client.page.evaluate("sent") == 0


def test_reopened_picker_blocks_confirm_without_consuming_receipt(client):
    draft = client.mention("group-a", "Test Member", "hello")
    client.page.evaluate("menu('')")
    with pytest.raises(RuntimeError, match="Active picker"):
        client.send("group-a", draft["token"])
    assert line.load_state()["status"] == "prepared"
    assert client.page.evaluate("sent") == 0


def test_removed_marker_blocks_confirm(client):
    draft = client.mention("group-a", "Test Member", "hello")
    client.room.locator("[part~=mention]").evaluate("e=>e.remove()")
    with pytest.raises(RuntimeError, match="marker and semantic"):
        client.send("group-a", draft["token"])
    assert client.page.evaluate("sent") == 0


def test_missing_public_getter_blocks_confirm(client):
    draft = client.mention("group-a", "Test Member", "")
    client.page.locator("textarea-ex").evaluate("e=>delete e.value")
    with pytest.raises(RuntimeError, match="Malformed public composer"):
        client.send("group-a", draft["token"])
    assert client.page.evaluate("sent") == 0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda state: state.update(version=2),
        lambda state: state.pop("expected_mention"),
        lambda state: state.update(verified_mention=None),
        lambda state: state.update(
            expected_mention={"kind": "all", "name": "All", "member_id": None}
        ),
        lambda state: state.update(status="invalid"),
        lambda state: state.update(digest="bad"),
        lambda state: state.update(extra="unknown"),
    ],
)
def test_malformed_versioned_state_stops_without_dispatch(client, mutate):
    draft = client.mention("group-a", "Test Member", "")
    state = line.load_state()
    mutate(state)
    (line.STATE / "draft.json").write_text(json.dumps(state))
    with pytest.raises(RuntimeError, match="receipt"):
        client.send("group-a", draft["token"])
    assert client.page.evaluate("sent") == 0
