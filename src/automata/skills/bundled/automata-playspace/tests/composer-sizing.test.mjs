import test from "node:test";
import assert from "node:assert/strict";
import {load, installDOM, layout} from "./runtime.mjs";
installDOM();
const {Chat, registerPlayspace} = await load("playspace.js");
registerPlayspace();
function setup(mount = true) {
  const chat = new Chat(); chat.id = "sizing-chat";
  if (mount) chat.connectedCallback();
  else chat.snapshot();
  const textarea = chat.querySelector("textarea"), form = chat.querySelector("form");
  let reads = 0;
  Object.defineProperty(textarea, "scrollHeight", {get() {
    reads++;
    assert.equal(textarea.style.height, "auto", "reset height before measuring shrink");
    return 40 + 20 * (textarea.value.split("\n").length - 1);
  }});
  return {chat, textarea, form, reads:() => reads};
}

test("input typing/paste/delete measures after value changes without changing draft or keyboard semantics", () => {
  const {chat,textarea,reads} = setup();
  try {
    const outgoing = [];
    chat.addEventListener("agent-message", event => outgoing.push(event.detail));
    for (const value of ["one", "one\ntwo\nthree\nfour", "short", ""]) {
      textarea.value = value; textarea.emit("input");
      assert.equal(textarea.style.height, `${42 + 20 * (value.split("\n").length - 1)}px`);
      assert.equal(chat.snapshot().composer, value);
    }
    assert.equal(reads(), 4);
    assert.equal(textarea.rows, 1);
    assert.equal(textarea.listeners.has("keydown"), false);
    assert.equal(outgoing.length, 0);
  } finally { chat.dispose(); }
});

test("restore before mount measures again on mount, restores disconnected, and never replays", () => {
  const {chat,textarea,reads} = setup(false);
  const outgoing = [];
  chat.addEventListener("agent-message", event => outgoing.push(event.detail));
  try {
    textarea.isConnected = false;
    const snapshot = chat.snapshot(); snapshot.composer = "saved\nmultiline\ndraft"; snapshot.pending = true;
    assert.equal(chat.restore(snapshot), true);
    assert.equal(reads(), 0);
    textarea.isConnected = true; chat.connectedCallback();
    assert.equal(textarea.style.height, "82px");
    assert.equal(chat.snapshot().composer, snapshot.composer);
    assert.equal(chat.canSend(), false);
    assert.equal(outgoing.length, 0);
  } finally { chat.dispose(); }
});

test("markSent shrinks cleared draft; reject restores text; both preserve newly edited drafts", () => {
  for (const editLater of [false,true]) {
    const {chat,textarea,form} = setup();
    try {
      chat.setConnection(true); chat.setAgentBusy(false);
      textarea.value = "submitted\nlong\ndraft"; textarea.emit("input"); form.emit("submit");
      if (editLater) textarea.value = "new\nmessage";
      chat.markSent();
      assert.equal(textarea.value, editLater ? "new\nmessage" : "");
      assert.equal(textarea.style.height, editLater ? "62px" : "42px");
      chat.reject("not accepted");
      assert.equal(textarea.value, editLater ? "new\nmessage" : "submitted\nlong\ndraft");
      assert.equal(textarea.style.height, editLater ? "62px" : "82px");
    } finally { chat.dispose(); }
  }
});

test("native reset measures after default action; cancelled reset and queued work respect disposal", async () => {
  const {chat,textarea,form,reads} = setup();
  let changed = 0;
  chat.addEventListener("chat-change", () => changed++);
  textarea.value = "old\nlong\ndraft"; textarea.emit("input");
  form.emit("reset");
  textarea.value = ""; // simulate native default action, after reset listeners
  await Promise.resolve();
  assert.equal(textarea.style.height, "42px");
  assert.equal(changed, 2);
  const before = reads();
  form.dispatchEvent({type:"reset",defaultPrevented:true});
  await Promise.resolve();
  assert.equal(reads(), before);
  form.emit("reset"); chat.dispose();
  await Promise.resolve();
  assert.equal(reads(), before);
  assert.equal(changed, 2);
});

test("width/viewport resize remeasures, height-only observation does not loop, disposal releases resources", () => {
  const {chat,textarea,form,reads} = setup();
  const observer = layout.observers.at(-1);
  const beforeListeners = layout.listeners.get("resize").size;
  observer.fire(390); assert.equal(reads(), 1);
  observer.fire(390); assert.equal(reads(), 1);
  observer.fire(320); assert.equal(reads(), 2);
  for (const resize of layout.listeners.get("resize")) resize();
  assert.equal(reads(), 3);
  chat.connectedCallback(); // DOM movement must not duplicate resource bindings
  assert.equal(layout.listeners.get("resize").size, beforeListeners);
  assert.equal(layout.observers.at(-1), observer);
  const last = reads();
  chat.dispose();
  observer.fire(500); textarea.emit("input"); form.emit("reset");
  assert.equal(reads(), last);
  assert.equal(observer.disconnected, true);
  assert.equal(layout.listeners.get("resize").size, beforeListeners - 1);
});
