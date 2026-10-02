import assert from "node:assert/strict";
import test from "node:test";
import {starterHarness} from "./starter-harness.mjs";

function fakeClock() {
  let now = Date.now(), next = 0;
  const timers = new Map();
  return {
    Date: class extends Date { static now() { return now; } },
    setTimeout(fn, delay) { const id = ++next; timers.set(id, {fn, at:now + delay, delay}); return id; },
    clearTimeout(id) { timers.delete(id); },
    count: delay => [...timers.values()].filter(timer => delay === undefined || timer.delay === delay).length,
    async advance(ms) {
      const end = now + ms;
      while (true) {
        const due = [...timers].filter(([,timer]) => timer.at <= end).sort((a,b) => a[1].at-b[1].at)[0];
        if (!due) break;
        const [id,timer] = due; now = timer.at; timers.delete(id); timer.fn();
        await new Promise(resolve => setImmediate(resolve));
      }
      now = end;
      await new Promise(resolve => setImmediate(resolve));
    },
  };
}
const calls = (c, endpoint) => c.requests.filter(request => request.url.endsWith(endpoint)).length;
async function waiting() {
  const clock = fakeClock(), h = await starterHarness({authenticated:false, clock});
  h.get("connection-settings").click(); await h.tick();
  h.get("request-pairing").click(); await h.tick();
  return {...h, clock, record:[...h.controls.requestRecords.values()][0]};
}
function approve(h) { h.record.state = "approved"; h.record.participant = "approved-page"; }
function visibility(h, value) { h.document.visibilityState = value; h.document.fire("visibilitychange"); }

test("visible wait checks every two seconds, claims once, stops and never connects/replays/changes drafts", async () => {
  const h = await waiting(), {get,controls:c,clock,context} = h;
  try {
    const before = JSON.stringify(context.playspaceChat.snapshot());
    assert.match(get("pairing-request-state").textContent,/Waiting for agent approval/);
    assert.equal(clock.count(2000),1);
    await clock.advance(1999); assert.equal(calls(c,"/request-status"),0);
    await clock.advance(1); assert.equal(calls(c,"/request-status"),1);
    assert.equal(clock.count(2000),1);
    get("copy-pairing-message").click(); await h.tick();
    assert.equal(c.clipboard.length,1);
    approve(h); await clock.advance(2000);
    assert.equal(calls(c,"/request-redeem"),1);
    assert.equal(get("connect-session").hidden,false);
    assert.equal(get("pairing-state").textContent,"Browser approved");
    assert.equal(clock.count(),0);
    await clock.advance(300000);
    assert.equal(calls(c,"/request-redeem"),1);
    assert.equal(c.connections.length,0); assert.equal(c.sends ?? 0,0);
    assert.equal(JSON.stringify(context.playspaceChat.snapshot()),before);
    assert.equal(c.maxActiveRequests,1);
  } finally { context.playspaceChat.dispose(); }
});

test("initial, opening and manual status share the physical lock and postpone auto waiting", async () => {
  const clock = fakeClock(), h = await starterHarness({authenticated:false,clock,holdInitialStatus:true});
  const {get,controls:c,context} = h;
  try {
    get("connection-settings").click(); get("advanced-check-session").click();
    get("request-pairing").click();
    assert.equal(c.requests.length,1);
    c.resolveStatus(); await h.tick();
    get("request-pairing").click(); await h.tick();
    c.holdStatus = true; get("check-session-status").click();
    await clock.advance(2000);
    assert.equal(calls(c,"/request-status"),0); assert.equal(clock.count(2000),0);
    get("check-pairing-request").click(); get("advanced-check-session").click();
    assert.equal(c.activeRequests,1);
    c.resolveStatus(); await h.tick();
    await clock.advance(1999); assert.equal(calls(c,"/request-status"),0);
    await clock.advance(1); assert.equal(calls(c,"/request-status"),1);
    assert.equal(c.maxActiveRequests,1);
  } finally { context.playspaceChat.dispose(); }
});

test("manual approval replaces scheduled timer; automatic in-flight check rejects overlapping manual work", async () => {
  const h = await waiting(), {get,controls:c,clock,context} = h;
  try {
    await clock.advance(1000); get("check-pairing-request").click(); await h.tick();
    assert.equal(calls(c,"/request-status"),1);
    await clock.advance(1000); assert.equal(calls(c,"/request-status"),1);
    c.holdRequestStatus = true; await clock.advance(1000);
    assert.equal(c.activeRequests,1); assert.equal(clock.count(2000),0);
    for (const id of ["check-pairing-request","advanced-check-session","request-pairing","cancel-pairing-request","forget-pairing"])
      get(id).click();
    assert.equal(c.activeRequests,1); assert.equal(calls(c,"/request-status"),2);
    assert.equal(calls(c,"/request-cancel"),0);
    c.resolveRequestStatus(); await h.tick();
    assert.equal(clock.count(2000),1); assert.equal(c.maxActiveRequests,1);
  } finally { context.playspaceChat.dispose(); }
});

for (const transition of ["close","hide","target","dispose"]) {
  test(`${transition} fences delayed approved status before claim and owns timer cleanup`, async () => {
    const h = await waiting(), {get,controls:c,clock,context} = h;
    try {
      approve(h); c.holdRequestStatus = true; await clock.advance(2000);
      if (transition === "close") get("close-connection").click();
      if (transition === "hide") visibility(h,"hidden");
      if (transition === "target") { get("target-participant").value = "other-agent"; get("target-participant").fire("input"); }
      if (transition === "dispose") context.playspaceChat.dispose();
      assert.equal(clock.count(2000),0);
      c.resolveRequestStatus(); await h.tick();
      await clock.advance(10000);
      assert.equal(calls(c,"/request-redeem"),0); assert.equal(clock.count(),0);
      if (transition === "close") get("connection-settings").click();
      if (transition === "hide") visibility(h,"visible");
      if (transition === "target") { get("close-connection").click(); get("connection-settings").click(); }
      if (transition !== "dispose") {
        await h.tick(); await clock.advance(1999); assert.equal(calls(c,"/request-redeem"),0);
        await clock.advance(1); assert.equal(calls(c,"/request-redeem"),1);
      } else assert.equal(h.document.listeners.get("visibilitychange").size,0);
    } finally { context.playspaceChat.dispose(); }
  });
}

for (const mode of ["close","hide"]) {
  for (const fail of [false,true]) {
    test(`${mode}/resume before settlement keeps lock and fresh delay; stale error=${fail}`, async () => {
      const h = await waiting(), {get,controls:c,clock,context} = h;
      try {
        approve(h); c.holdRequestStatus = true; await clock.advance(2000);
        if (mode === "close") { get("close-connection").click(); get("connection-settings").click(); }
        else { visibility(h,"hidden"); visibility(h,"visible"); }
        assert.equal(clock.count(2000),0); assert.equal(c.activeRequests,1);
        get("pairing-code").value = "new-user-input";
        if (fail) c.failNext = "RequestStatus";
        c.resolveRequestStatus(); await h.tick();
        assert.equal(get("pairing-code").value,"new-user-input");
        assert.equal(calls(c,"/request-redeem"),0);
        assert.equal(clock.count(2000),fail ? 0 : 1);
        await clock.advance(1999); assert.equal(calls(c,"/request-redeem"),0);
        await clock.advance(1); assert.equal(calls(c,"/request-redeem"),fail ? 0 : 1);
        if (fail) {
          get("close-connection").click(); get("connection-settings").click(); await h.tick();
          await clock.advance(10000); assert.equal(calls(c,"/request-status"),1);
          assert.match(get("pairing-request-state").textContent,/No automatic retry/);
          get("check-session-status").click(); await h.tick();
          await clock.advance(2000); assert.equal(calls(c,"/request-redeem"),1);
        }
        assert.equal(c.maxActiveRequests,1);
      } finally { context.playspaceChat.dispose(); }
    });
  }
}

test("cancel stops waiting; new request does not inherit old approval or timer", async () => {
  const h = await waiting(), {get,controls:c,clock,context} = h;
  try {
    get("cancel-pairing-request").click(); await h.tick();
    assert.equal(clock.count(),0);
    approve(h); await clock.advance(4000); assert.equal(calls(c,"/request-redeem"),0);
    get("request-pairing").click(); await h.tick();
    assert.notEqual(get("pairing-request-locator").textContent,h.record.request);
    await clock.advance(2000); assert.equal(calls(c,"/request-redeem"),0);
    assert.equal(clock.count(2000),1);
  } finally { context.playspaceChat.dispose(); }
});

test("fixed TTL and errors terminate scheduling without retries", async () => {
  for (const error of [false,true]) {
    const h = await waiting(), {get,controls:c,clock,context} = h;
    try {
      if (error) c.failNext = "RequestStatus";
      await clock.advance(error ? 2000 : 300000);
      assert.equal(clock.count(),0);
      assert.match(get("pairing-request-state").textContent,error ? /No automatic retry/ : /expired/);
      const count = c.requests.length;
      await clock.advance(100000); assert.equal(c.requests.length,count);
      assert.equal(calls(c,"/request-redeem"),0);
    } finally { context.playspaceChat.dispose(); }
  }
});

for (const cookie of [false,true]) {
  test(`ambiguous claim survives reload and expiry; cookie recovery=${cookie} never redeems twice`, async () => {
    const first = await waiting(); approve(first);
    first.controls.loseRedeemResponse = true; first.controls.loseCookie = !cookie;
    await first.clock.advance(2000);
    assert.equal(calls(first.controls,"/request-redeem"),1);
    assert.equal(first.clock.count(),0);
    first.context.playspaceChat.dispose();
    const h = await starterHarness({authenticated:cookie, requestStorage:first.requestStorage,clock:first.clock});
    const {get,controls:c,context} = h;
    try {
      c.participant = "approved-page";
      get("connection-settings").click(); await h.tick();
      await first.clock.advance(310000);
      if (!cookie) {
        assert.match(get("pairing-request-state").textContent,/uncertain.*expiry/);
        assert.equal(get("request-pairing").hidden,true);
        get("request-pairing").click(); await h.tick(); // even accidental/programmatic activation cannot create
        assert.equal(calls(c,"/request"),0);
        get("check-session-status").click(); await h.tick();
        assert.equal(get("request-pairing").hidden,true);
      } else {
        assert.equal(get("connect-session").hidden,false);
        assert.equal(JSON.parse([...h.requestStorage.values()][0]).claimConfirmed,true);
      }
      assert.equal(calls(c,"/request-redeem"),0);
      assert.equal(c.connections.length,0);
    } finally { context.playspaceChat.dispose(); }
  });
}

test("closed/hidden state is checked before claim even ahead of its lifecycle event", async () => {
  for (const hidden of [false,true]) {
    const h = await waiting(), {get,controls:c,clock,context} = h;
    try {
      approve(h); c.holdRequestStatus = true; await clock.advance(2000);
      if (hidden) h.document.visibilityState = "hidden";
      else get("connection-dialog").open = false;
      c.resolveRequestStatus(); await h.tick();
      assert.equal(calls(c,"/request-redeem"),0); assert.equal(clock.count(),0);
    } finally { context.playspaceChat.dispose(); }
  }
});

test("restored known approval waits for visible dialog; storage failure stops without redeem", async () => {
  const first = await waiting();
  const [key,raw] = [...first.requestStorage][0];
  first.requestStorage.set(key,JSON.stringify({...JSON.parse(raw),state:"approved",participant:"approved-page"}));
  first.context.playspaceChat.dispose();
  const h = await starterHarness({authenticated:false,requestStorage:first.requestStorage,clock:first.clock});
  try {
    h.controls.requestRecords.set(first.record.request,{...first.record,state:"approved",participant:"approved-page"});
    await first.clock.advance(10000); assert.equal(calls(h.controls,"/request-status"),0);
    h.get("connection-settings").click(); await h.tick();
    h.controls.storageWriteFail = true;
    await first.clock.advance(2000);
    assert.equal(calls(h.controls,"/request-redeem"),0); assert.equal(first.clock.count(),0);
    assert.match(h.get("pairing-request-state").textContent,/No automatic retry/);
  } finally { h.context.playspaceChat.dispose(); }
});

test("confirmed redemption plus cookie loss and TTL requires repair, not fresh pairing", async () => {
  const h = await waiting(), {get,controls:c,clock,context} = h;
  try {
    approve(h); await clock.advance(2000);
    assert.equal(calls(c,"/request-redeem"),1);
    c.authenticated = false; await clock.advance(300000);
    get("advanced-check-session").click(); await h.tick();
    assert.equal(get("request-pairing").hidden,true);
    assert.match(get("pairing-request-state").textContent,/orphaned/);
    assert.equal(calls(c,"/logout"),0);
    get("request-pairing").click(); await h.tick();
    assert.equal(calls(c,"/request"),1); // accidental click cannot replace the tombstone
    get("close-connection").click(); get("connection-settings").click(); await h.tick();
    assert.equal(get("request-pairing").hidden,true);
    assert.equal(clock.count(),0);
    // Cookie recovery does not itself retire the claim; matched explicit logout does.
    c.authenticated = true; get("advanced-check-session").click(); await h.tick();
    assert.equal(h.requestStorage.size,1);
    get("forget-pairing").click(); await h.tick();
    assert.equal(calls(c,"/logout"),1); assert.equal(h.requestStorage.size,0);
    assert.equal(get("request-pairing").hidden,false);
    get("request-pairing").click(); await h.tick();
    assert.equal(calls(c,"/request"),2);
    assert.equal(c.connections.length,0);
  } finally { context.playspaceChat.dispose(); }
});

test("successful logout of another page cannot retire the prior redeemed binding", async () => {
  const h = await waiting(), {get,controls:c,clock,context} = h;
  try {
    approve(h); await clock.advance(2000); await clock.advance(300000);
    c.participant = "another-page";
    get("advanced-check-session").click(); await h.tick();
    get("forget-pairing").click(); await h.tick();
    assert.equal(calls(c,"/logout"),1); assert.equal(c.authenticated,false);
    assert.equal(h.requestStorage.size,1);
    assert.equal(get("request-pairing").hidden,true);
    assert.match(get("pairing-request-state").textContent,/orphaned/);
    assert.equal(get("pairing-state").textContent,"Browser not approved / approval expired");
  } finally { context.playspaceChat.dispose(); }
});

test("issued claim may commit after close but cannot connect; reopen recovers cookie via status", async () => {
  const h = await waiting(), {get,controls:c,clock,context} = h;
  try {
    approve(h); c.holdRequestRedeem = true; await clock.advance(2000);
    get("close-connection").click();
    c.resolveRequestRedeem(); await h.tick();
    assert.equal(c.authenticated,true); assert.equal(clock.count(),0);
    assert.equal(c.connections.length,0);
    get("connection-settings").click(); await h.tick();
    assert.equal(get("connect-session").hidden,false);
    assert.equal(calls(c,"/request-redeem"),1);
  } finally { context.playspaceChat.dispose(); }
});
