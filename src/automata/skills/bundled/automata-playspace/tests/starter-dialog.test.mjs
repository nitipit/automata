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
      assert.equal(document.activeElement,get("pairing-state")); // opening status owns the shared busy lock
      if (focusElsewhere) get("cancel-connection").focus();
      c.authenticated=true; c.resolveStatus(); await tick();
      assert.equal(get("pairing-form").hidden,true);
      assert.equal(document.activeElement,get(focusElsewhere ? "cancel-connection" : "connect-session"));
      assert.equal(c.connections.length,0);
    } finally { context.playspaceChat.dispose(); }
  }
});

test("request pairing double-click reuses binding; explicit approval check claims without connecting", async () => {
  const {get,controls:c,context,requestStorage,tick} = await starterHarness({authenticated:false});
  try {
    get("connection-settings").click(); await tick();
    c.holdRequestCreate=true;
    get("request-pairing").click(); get("request-pairing").click(); await tick();
    assert.equal(c.requests.filter(value => value.url.endsWith("/request")).length,1);
    assert.equal(requestStorage.size,1);
    c.resolveRequestCreate(); await tick();
    const record=[...c.requestRecords.values()][0];
    assert.equal(get("pairing-request-locator").textContent,record.request);
    assert.ok(!get("pairing-request-state").textContent.includes(record.capability));
    get("request-pairing").click(); await tick();
    assert.equal(c.requestRecords.size,1);
    record.state="approved"; record.participant="approved-page";
    get("check-pairing-request").click(); await tick(); await tick();
    assert.equal(record.state,"redeemed");
    assert.equal(get("page-participant").textContent,"approved-page");
    assert.equal(c.connections.length,0);
    assert.equal(c.requests.filter(value => value.url.endsWith("/request-redeem")).length,1);
    get("connect-session").click(); await tick(); await tick();
    assert.equal(c.connections.length,1);
    assert.equal(c.connections[0].kind,"session");
  } finally { context.playspaceChat.dispose(); }
});

test("refresh resumes transient requester display without claim or connect; cancel is exact", async () => {
  const first=await starterHarness({authenticated:false});
  first.get("request-pairing").click(); await first.tick();
  const original=[...first.controls.requestRecords.values()][0];
  first.context.playspaceChat.dispose();
  const next=await starterHarness({authenticated:false,requestStorage:first.requestStorage});
  try {
    next.controls.requestRecords.set(original.request,original);
    assert.equal(next.get("pairing-request-locator").textContent,original.request);
    assert.equal(next.controls.connections.length,0);
    assert.ok(next.controls.requests.every(value => value.url.endsWith("/status")));
    next.get("cancel-pairing-request").click(); await next.tick();
    assert.equal(original.state,"cancelled");
    next.get("request-pairing").click(); await next.tick();
    assert.equal(next.controls.requestRecords.size,2);
    assert.notEqual(next.get("pairing-request-locator").textContent,original.request);
    assert.equal(next.controls.connections.length,0);
  } finally { next.context.playspaceChat.dispose(); }
});

test("closing dialog fences delayed approval check before claim; no polling after dismissal", async () => {
  const {get,controls:c,context,tick} = await starterHarness({authenticated:false});
  try {
    get("connection-settings").click(); await tick();
    get("request-pairing").click(); await tick();
    const record=[...c.requestRecords.values()][0];
    record.state="approved"; record.participant="page";
    c.holdRequestStatus=true;
    get("check-pairing-request").click(); await tick();
    assert.ok(c.resolveRequestStatus);
    get("close-connection").click();
    const count=c.requests.length;
    c.resolveRequestStatus(); await tick(); await tick();
    assert.equal(c.requests.length,count);
    assert.equal(record.state,"approved");
    assert.equal(c.connections.length,0);
  } finally { context.playspaceChat.dispose(); }
});

test("check approval preserves another paired cookie and reports lost-cookie repair", async () => {
  for (const existing of [true,false]) {
    const {get,controls:c,context,tick} = await starterHarness({authenticated:false});
    try {
      get("connection-settings").click(); await tick();
      get("request-pairing").click(); await tick();
      const record=[...c.requestRecords.values()][0];
      record.state=existing ? "approved" : "redeemed"; record.participant="page-A";
      c.authenticated=existing; c.participant="page-B";
      get("check-pairing-request").click(); await tick(); await tick();
      assert.equal(c.requests.filter(value => value.url.endsWith("/request-redeem")).length,0);
      assert.ok(get("pairing-state").textContent.includes(existing ? "Remove browser approval explicitly" : "orphaned"));
      if (existing) assert.equal(get("page-participant").textContent,"page-B");
      assert.equal(c.connections.length,0);
    } finally { context.playspaceChat.dispose(); }
  }
});
