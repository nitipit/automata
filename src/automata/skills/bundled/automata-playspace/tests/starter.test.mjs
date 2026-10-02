import assert from "node:assert/strict";
import test from "node:test";
import { starterHarness } from "./starter-harness.mjs";

/** Actual starter orchestration with narrow dependency/DOM fakes, not browser proof. */
test("Restore and Connect honor newest explicit intent before and after cache waits", async () => {
  const {get,controls:c,context,clientFactory,tick} = await starterHarness();
  try {
    c.holdStatus = true; get("connect-session").click(); await tick();
    assert.ok(c.resolveStatus);
    c.candidate = {version:2,mode:"sample",chat:{}};
    c.holdLoad = true; get("restore").click(); await tick();
    assert.ok(c.resolveLoad);
    c.resolveStatus(); await tick(); await tick(); // cancellation precedes delayed cache load
    assert.equal(c.connections.length,0);
    c.resolveLoad(); c.holdLoad = false; await tick(); await tick();
    assert.equal(get("connection").textContent,"Demo · local");
    c.holdStatus = true; c.resolveStatus = undefined;
    get("connect-session").click(); await tick();
    assert.ok(c.resolveStatus);
    await context.playspaceChat.connect({participant:"page",token:"synthetic"}, "other-agent", {createClient:clientFactory});
    c.resolveStatus(); await tick(); await tick();
    assert.equal(c.connections.length,1);
    assert.deepEqual(c.connections[0],{kind:"token",to:"other-agent"});

    c.holdLoad = true; c.resolveLoad = undefined;
    const older = context.playspaceChat.restore(); await tick();
    assert.ok(c.resolveLoad);
    await context.playspaceChat.connect({participant:"page",token:"synthetic"}, "newer-agent", {createClient:clientFactory});
    const before = c.restorations;
    c.resolveLoad(); c.holdLoad = false;
    assert.equal(await older,false);
    assert.equal(c.restorations,before);
    assert.equal(c.connections.at(-1).to,"newer-agent");
    assert.match(get("connection-detail").textContent,/LIVE.*authenticated/);

    for (const id of ["sample-mode", "live-mode"]) {
      c.holdLoad = true; c.resolveLoad = undefined;
      const stale = context.playspaceChat.restore(); await tick();
      assert.ok(c.resolveLoad);
      get(id).click();
      c.resolveLoad(); c.holdLoad = false;
      assert.equal(await stale,false);
      assert.equal(c.restorations,before);
    }
    c.holdLoad = true;
    const stale = context.playspaceChat.restore(); await tick();
    const resolveOld = c.resolveLoad;
    const newest = context.playspaceChat.restore(); await tick();
    const resolveNew = c.resolveLoad;
    resolveNew(); assert.equal(await newest,true);
    const latestCount = c.restorations;
    resolveOld(); c.holdLoad = false;
    assert.equal(await stale,false);
    assert.equal(c.restorations,latestCount);
  } finally {
    context.playspaceChat.dispose();
    assert.equal(get("connect-session").listeners.get("click").size,0);
    assert.equal(get("restore").listeners.get("click").size,0);
  }
});

test("first use is disconnected; paired UI hides code; opening and cancelling create no socket", async () => {
  const {get,controls:c,context,document,tick} = await starterHarness();
  try {
    assert.equal(c.connections.length,0);
    assert.equal(context.playspaceChat.snapshot().mode,"live");
    assert.equal(get("connection").textContent,"Disconnected");
    assert.equal(get("pairing-form").hidden,true);
    assert.equal(get("pairing-code").disabled,true);
    get("connection-settings").click(); await tick();
    assert.equal(get("connection-dialog").open,true);
    assert.equal(document.activeElement,get("target-participant"));
    assert.equal(get("connection-dialog").fire("cancel").defaultPrevented,true);
    assert.equal(get("connection-dialog").open,false);
    assert.equal(document.activeElement,get("connection-settings"));
    assert.equal(c.connections.length,0);
  } finally { context.playspaceChat.dispose(); }
});

test("Cancel fences auth wait and opening handshake, but keeps an established connection", async () => {
  const {get,controls:c,context,tick} = await starterHarness();
  try {
    get("connection-settings").click(); await tick();
    c.holdStatus=true; get("connect-session").click(); await tick();
    get("cancel-connection").click(); c.resolveStatus(); await tick(); await tick();
    assert.equal(c.connections.length,0);
    get("connection-settings").click(); await tick();
    c.holdConnect=true; get("connect-session").click(); await tick();
    assert.equal(get("connection").textContent,"Connecting…");
    get("close-connection").click();
    assert.equal(c.clients.at(-1).closed,true);
    c.resolveConnect(); await tick(); await tick();
    assert.equal(get("connection").textContent,"Disconnected");
    get("connection-settings").click(); await tick();
    get("connect-session").click(); await tick(); await tick();
    assert.equal(get("connection").textContent,"Connected");
    get("connection-dialog").fire("cancel");
    assert.equal(c.clients.at(-1).closed,false);
    assert.equal(get("connection").textContent,"Connected");
    // A queued native close from an older dialog cannot cancel a reopened action.
    get("connection-settings").click(); await tick();
    c.holdStatus=true; get("connect-session").click(); await tick();
    get("connection-dialog").fire("close");
    c.resolveStatus(); await tick(); await tick();
    assert.equal(get("connection").textContent,"Connected");
  } finally { context.playspaceChat.dispose(); }
});

test("cancelled Pair cannot chain Connect or clear a newer code/action", async () => {
  const {get,controls:c,context,tick} = await starterHarness();
  try {
    c.authenticated=false;
    get("connection-settings").click(); await tick();
    assert.equal(get("pairing-form").hidden,false);
    c.holdPair=true; get("pairing-code").value="old-private-code";
    get("pairing-form").fire("submit"); await tick();
    assert.equal(get("pairing-code").value,"");
    const resolveOld=c.resolvePair;
    get("cancel-connection").click();
    get("connection-settings").click(); await tick();
    get("pairing-code").value="new-private-code";
    c.holdPair=true; get("pairing-form").fire("submit"); await tick();
    const resolveNew=c.resolvePair;
    resolveOld(); await tick(); await tick();
    assert.equal(get("pair-browser").disabled,true);
    get("cancel-connection").click();
    get("pairing-code").value="unsent-new-code";
    c.authenticated=true; resolveNew(); await tick(); await tick();
    assert.equal(get("pairing-code").value,"unsent-new-code");
    assert.equal(c.connections.length,0);
  } finally { context.playspaceChat.dispose(); }
});

test("target edits fence old Connect and retire an established binding; only Connect saves target", async () => {
  const {get,controls:c,context,storage,tick} = await starterHarness();
  try {
    assert.equal(storage.size,0);
    c.holdStatus=true; get("connect-session").click(); await tick();
    get("target-participant").value="new-agent"; get("target-participant").fire("input");
    c.resolveStatus(); await tick(); await tick();
    assert.equal(c.connections.length,0);
    assert.equal([...storage.values()][0],"pc1-agent");
    get("connect-session").click(); await tick(); await tick();
    assert.equal(c.connections.at(-1).to,"new-agent");
    assert.equal([...storage.values()][0],"new-agent");
    get("target-participant").value="third-agent"; get("target-participant").fire("input");
    assert.equal(c.clients.at(-1).closed,true);
    assert.equal(get("connection").textContent,"Disconnected");
    assert.equal([...storage.values()][0],"new-agent");
    get("sample-form").click();
    assert.equal(context.playspaceChat.snapshot().mode,"sample");
    assert.equal(get("connection").textContent,"Demo · local");
    assert.equal(c.messages.at(-1)[1],"sample-form");
  } finally { context.playspaceChat.dispose(); }
});
