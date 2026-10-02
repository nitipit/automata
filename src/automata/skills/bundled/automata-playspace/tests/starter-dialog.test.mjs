import assert from "node:assert/strict";
import test from "node:test";
import { starterHarness } from "./starter-harness.mjs";

test("owned queued close cannot cancel or refocus newer provisioning without reopening", async () => {
  const {get,controls:c,context,document,tick} = await starterHarness();
  try {
    get("connection-settings").click(); await tick();
    get("close-connection").click();
    c.holdImport=true;
    const newest=context.playspaceChat.connect({participant:"page",token:"synthetic"},"newest-agent");
    await tick(); assert.ok(c.resolveImport);
    get("save").focus();
    get("connection-dialog").fire("close");
    assert.equal(document.activeElement,get("save"));
    c.resolveImport();
    assert.equal(await newest,true);
    assert.equal(c.connections.at(-1).to,"newest-agent");
  } finally { context.playspaceChat.dispose(); }
});

test("mixed owned/external transitions retire current handshake, not newer intent at queued notifications", async () => {
  const {get,controls:c,context,document,tick} = await starterHarness();
  try {
    get("connection-settings").click(); await tick();
    get("close-connection").click(); // owned close notification still queued
    get("connection-settings").click(); await tick();
    c.holdConnect=true; get("connect-session").click(); await tick();
    const openingClient=c.clients.at(-1);
    get("connection-dialog").close(); // external synchronous beforetoggle
    assert.equal(openingClient.closed,true);
    c.holdImport=true;
    const newest=context.playspaceChat.connect({participant:"page",token:"synthetic"},"after-external-close");
    get("save").focus();
    await tick(); assert.ok(c.resolveImport);
    assert.equal(document.activeElement,get("save")); // stale external focus microtask fenced
    get("connection-dialog").fire("close"); // old owned notification
    get("connection-dialog").fire("close"); // old external notification
    c.resolveConnect(); await tick();
    assert.equal(document.activeElement,get("save"));
    c.resolveImport();
    assert.equal(await newest,true);
    assert.equal(c.connections.at(-1).to,"after-external-close");
  } finally { context.playspaceChat.dispose(); }
});

test("unhandled external native close cancels current auth wait and returns focus", async () => {
  const {get,controls:c,context,document,tick} = await starterHarness();
  try {
    get("connection-settings").click(); await tick();
    c.holdStatus=true; get("connect-session").click(); await tick();
    get("connection-dialog").close();
    await tick();
    assert.equal(document.activeElement,get("connection-settings"));
    c.resolveStatus(); await tick(); await tick();
    assert.equal(c.connections.length,0);
    get("connection-dialog").fire("close");
    assert.equal(get("connection").textContent,"Disconnected");
  } finally { context.playspaceChat.dispose(); }
});

test("current modal Cancel fences delayed Restore while preserving established connection policy", async () => {
  const {get,controls:c,context,tick} = await starterHarness();
  try {
    get("connection-settings").click(); await tick();
    c.candidate={version:2,mode:"sample",chat:{}}; c.holdLoad=true;
    const restore=context.playspaceChat.restore(); await tick();
    assert.ok(c.resolveLoad);
    get("cancel-connection").click();
    c.resolveLoad();
    assert.equal(await restore,false);
    assert.equal(c.restorations,0);
    assert.equal(get("connection").textContent,"Disconnected");
    // Notification from handled Cancel cannot invalidate a NEW Restore.
    c.holdLoad=true;
    const newest=context.playspaceChat.restore(); await tick();
    get("connection-dialog").fire("close");
    c.resolveLoad();
    assert.equal(await newest,true);
    assert.equal(c.restorations,1);
  } finally { context.playspaceChat.dispose(); }
});

test("explicit Connect fences older cache Restore before delayed auth status completes", async () => {
  const {get,controls:c,context,tick} = await starterHarness();
  try {
    c.candidate={version:2,mode:"sample",chat:{}}; c.holdLoad=true;
    const stale=context.playspaceChat.restore(); await tick();
    c.holdStatus=true; get("connect-session").click(); await tick();
    assert.ok(c.resolveStatus);
    c.resolveLoad();
    assert.equal(await stale,false);
    assert.equal(c.restorations,0);
    c.resolveStatus(); await tick(); await tick();
    assert.equal(c.connections.at(-1).to,"pc1-agent");
    assert.equal(get("connection").textContent,"Connected");
  } finally { context.playspaceChat.dispose(); }
});

test("paired status redirects focus before hiding code, without stealing focus elsewhere", async () => {
  for (const focusElsewhere of [false,true]) {
    const {get,controls:c,context,document,tick} = await starterHarness();
    try {
      c.authenticated=false;
      get("connection-settings").click(); await tick();
      get("close-connection").click();
      c.holdStatus=true;
      get("connection-settings").click(); await tick();
      assert.equal(document.activeElement,get("pairing-code"));
      if (focusElsewhere) get("cancel-connection").focus();
      c.authenticated=true; c.resolveStatus(); await tick();
      assert.equal(get("pairing-form").hidden,true);
      assert.equal(document.activeElement,get(focusElsewhere ? "cancel-connection" : "target-participant"));
      assert.equal(c.connections.length,0);
    } finally { context.playspaceChat.dispose(); }
  }
});
