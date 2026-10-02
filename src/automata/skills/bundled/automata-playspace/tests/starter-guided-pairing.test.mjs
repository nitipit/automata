import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs/promises";
import path from "node:path";
import {starterHarness} from "./starter-harness.mjs";
const actions = ["request-pairing", "copy-pairing-message", "check-pairing-request", "cancel-pairing-request",
  "connect-session", "choose-agent", "done-connection", "check-session-status", "live-mode", "forget-pairing"];
function primary(get, expected) {
  assert.deepEqual(actions.filter(id => !get(id).hidden && get(id).className === "primary"), [expected]);
}
async function requestState(state) {
  const first = await starterHarness({authenticated:false});
  first.get("request-pairing").click(); await first.tick();
  const record = [...first.controls.requestRecords.values()][0];
  const [key, raw] = [...first.requestStorage][0];
  const value = {...JSON.parse(raw), state, participant:"approved-page"};
  if (state === "expired") value.expiresAt = Date.now()/1000 - 1;
  first.requestStorage.set(key, JSON.stringify(value));
  first.context.playspaceChat.dispose();
  const next = await starterHarness({authenticated:false,requestStorage:first.requestStorage});
  next.controls.requestRecords.set(record.request, {...record, ...value});
  return next;
}

test("guided waiting path copies only public message, explicit check claims, Connect and Done stay separate", async () => {
  const {get,controls:c,context,document,tick} = await starterHarness({authenticated:false});
  try {
    get("connection-settings").click(); await tick();
    primary(get,"request-pairing");
    c.holdRequestCreate = true;
    get("request-pairing").focus(); get("request-pairing").click();
    assert.equal(document.activeElement,get("pairing-state"));
    c.resolveRequestCreate(); await tick();
    primary(get,"copy-pairing-message");
    assert.equal(document.activeElement,get("copy-pairing-message"));
    const record = [...c.requestRecords.values()][0], count = c.requests.length;
    get("copy-pairing-message").click(); await tick();
    assert.deepEqual(c.clipboard,[`Please approve pairing ${record.request}`]);
    assert.equal(get("pairing-message").textContent,c.clipboard[0]);
    assert.equal(c.requests.length,count);
    assert.ok(!c.clipboard[0].includes(record.capability));
    c.clipboardFail = true; get("copy-pairing-message").click(); await tick();
    assert.match(get("copy-pairing-state").textContent,/Select and copy/);
    record.state = "approved"; record.participant = "approved-page";
    get("check-pairing-request").focus(); get("check-pairing-request").click(); await tick(); await tick();
    primary(get,"connect-session");
    assert.equal(document.activeElement,get("connect-session"));
    assert.equal(c.connections.length,0);
    assert.equal(get("connect-session").textContent,"Connect to pc1-agent");
    get("connect-session").click(); await tick(); await tick();
    primary(get,"done-connection");
    assert.equal(document.activeElement,get("done-connection"));
    get("done-connection").click();
    assert.equal(get("connection-dialog").open,false);
    assert.equal(c.clients.at(-1).closed,false);
    assert.equal(document.activeElement,get("connection-settings"));
  } finally { context.playspaceChat.dispose(); }
});

test("restored approved-unclaimed request offers Check, not Copy, and restoration never claims", async () => {
  const {get,controls:c,context,tick} = await requestState("approved");
  try {
    primary(get,"check-pairing-request");
    assert.equal(get("copy-pairing-message").hidden,true);
    assert.match(get("pairing-request-state").textContent,/Approved by agent/);
    assert.ok(c.requests.every(request => request.url.endsWith("/status")));
    assert.equal(c.connections.length,0);
    get("check-pairing-request").click(); await tick(); await tick();
    primary(get,"connect-session");
    assert.equal(c.connections.length,0);
  } finally { context.playspaceChat.dispose(); }
});

test("expired/cancelled requests offer new pairing; redeemed-without-cookie offers safe status/operator recovery", async () => {
  for (const state of ["expired","cancelled","redeemed"]) {
    const {get,controls:c,context,tick} = await requestState(state);
    try {
      primary(get,state === "redeemed" ? "check-session-status" : "request-pairing");
      if (state === "redeemed") {
        assert.match(get("pairing-request-state").textContent,/orphaned.*do not retry/);
        get("check-session-status").click(); await tick();
        primary(get,"check-session-status");
        assert.ok(c.requests.every(request => request.url.endsWith("/status")));
      }
      assert.equal(c.connections.length,0);
    } finally { context.playspaceChat.dispose(); }
  }
});

test("uncertain create and malformed storage never suggest a confident new request", async () => {
  for (const malformed of [false,true]) {
    const requestStorage = new Map();
    if (malformed) requestStorage.set("automata-router-request-v1:http://127.0.0.1:8775/", "{bad");
    const {get,controls:c,context,tick} = await starterHarness({authenticated:false,requestStorage});
    try {
      if (!malformed) { c.failNext = "RequestCreate"; get("request-pairing").click(); await tick(); }
      primary(get,"check-session-status");
      assert.equal(get("request-pairing").hidden,true);
      assert.equal(get("pairing-form").hidden,false);
      get("check-session-status").click(); await tick();
      primary(get,"check-session-status");
      assert.equal(c.connections.length,0);
    } finally { context.playspaceChat.dispose(); }
  }
});

test("read-only status failure recovers after explicit successful check without creating a request", async () => {
  const {get,controls:c,context,tick} = await starterHarness({authenticated:false});
  try {
    c.failNext = "Status"; get("advanced-check-session").click(); await tick();
    primary(get,"check-session-status");
    get("check-session-status").click(); await tick();
    primary(get,"request-pairing");
    assert.ok(c.requests.every(request => request.url.endsWith("/status")));
    assert.equal(c.connections.length,0);
  } finally { context.playspaceChat.dispose(); }
});

test("uncertain create binding remains safe after reload, with no automatic retry", async () => {
  const first = await starterHarness({authenticated:false});
  first.controls.failNext = "RequestCreate";
  first.get("request-pairing").click(); await first.tick();
  first.context.playspaceChat.dispose();
  const {get,controls:c,context} = await starterHarness({authenticated:false,requestStorage:first.requestStorage});
  try {
    primary(get,"check-session-status");
    assert.match(get("pairing-request-state").textContent,/outcome is uncertain/);
    assert.ok(c.requests.every(request => request.url.endsWith("/status")));
  } finally { context.playspaceChat.dispose(); }
});

test("invalid approved target opens Advanced and focuses field; unrelated focus is retained during busy/completion", async () => {
  const {get,controls:c,context,document,tick} = await starterHarness();
  try {
    get("connection-settings").click(); await tick();
    get("target-participant").value = ""; get("target-participant").fire("input");
    primary(get,"choose-agent");
    get("choose-agent").click();
    assert.equal(get("connection-advanced").open,true);
    assert.equal(document.activeElement,get("target-participant"));
    get("target-participant").value = "agent-two"; get("target-participant").fire("input");
    assert.equal(document.activeElement,get("target-participant"));
    primary(get,"connect-session");
    get("close-connection").focus(); c.holdStatus = true; get("connect-session").click();
    assert.equal(document.activeElement,get("close-connection"));
    c.resolveStatus(); await tick(); await tick();
    assert.equal(document.activeElement,get("close-connection"));
    primary(get,"done-connection");
  } finally { context.playspaceChat.dispose(); }
});

test("Close retains request; Cancel pairing request cancels only request; removal revokes approval not drafts", async () => {
  const {get,controls:c,context,tick,requestStorage} = await starterHarness({authenticated:false});
  try {
    get("connection-settings").click(); await tick();
    get("request-pairing").click(); await tick();
    const record = [...c.requestRecords.values()][0];
    get("cancel-connection").click();
    assert.equal(record.state,"pending");
    assert.equal(requestStorage.size,1);
    get("connection-settings").click(); await tick();
    get("cancel-pairing-request").click(); await tick();
    assert.equal(record.state,"cancelled");
    primary(get,"request-pairing");
    get("request-pairing").click(); await tick();
    const next = [...c.requestRecords.values()].at(-1);
    next.state = "approved"; next.participant = "page";
    get("check-pairing-request").click(); await tick(); await tick();
    get("connect-session").click(); await tick(); await tick();
    const before = JSON.stringify(context.playspaceChat.snapshot());
    get("forget-pairing").click(); await tick();
    assert.equal(c.authenticated,false);
    assert.equal(c.clients.at(-1).closed,true);
    assert.equal(JSON.stringify(context.playspaceChat.snapshot()),before);
    assert.equal(requestStorage.size,0); // only terminal request retired after confirmed revocation
    primary(get,"request-pairing");
  } finally { context.playspaceChat.dispose(); }
});

test("HTML exposes compact readonly Page ID before Advanced and a focusable busy destination; CSS caps composer", async () => {
  const stage = path.dirname(process.env.PLAYSPACE_LIB);
  const html = await fs.readFile(path.join(stage,"index.html"),"utf8");
  assert.ok(html.indexOf('id="page-participant"') < html.indexOf('id="connection-advanced"'));
  assert.match(html, /id="pairing-state"[^>]*tabindex="-1"/);
  assert.match(html, /Remove browser approval/);
  assert.match(html, /Revokes approval and disconnects this browser\. Keeps your drafts/);
  const style = await fs.readFile(path.join(stage,"style.css"),"utf8");
  const chatStyle = await fs.readFile(path.join(process.env.PLAYSPACE_LIB,"chat.css.js"),"utf8");
  assert.match(style, /min-height: min\(3\.1rem, 30vh\); max-height: 30vh/);
  assert.match(chatStyle, /min-height: min\(5rem, 30vh\); max-height: 30vh/);
  assert.match(chatStyle, /resize: none; overflow-y: auto/);
});
