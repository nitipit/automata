import assert from "node:assert/strict";
import test from "node:test";
import {starterHarness} from "./starter-harness.mjs";

const count = (h, endpoint) => h.controls.requests.filter(r => r.url.endsWith(endpoint)).length;
async function claimed() {
  const key = "automata-router-request-v1:http://127.0.0.1:8775/";
  const requestStorage = new Map([[key,JSON.stringify({capability:"a".repeat(64),
    request:"RP-AAAAAAAAAA",state:"redeemed",participant:"page",expiresAt:Date.now()/1000-10,
    claimAttempted:true,claimConfirmed:true})]]);
  const h = await starterHarness({requestStorage});
  h.get("connection-settings").click(); await h.tick();
  return h;
}

test("fresh status, not displayed identity, determines whether explicit logout may retire a claim", async () => {
  for (const current of ["page","other-page",null]) {
    const h = await claimed();
    try {
      assert.equal(h.get("page-participant").textContent,"page");
      h.controls.authenticated = current !== null;
      h.controls.participant = current;
      const before = count(h,"/status");
      h.get("forget-pairing").click(); await h.tick();
      assert.equal(count(h,"/status"),before+1);
      assert.equal(count(h,"/logout"),1);
      assert.equal(h.requestStorage.size,current === "page" ? 0 : 1);
      assert.equal(h.get("request-pairing").hidden,current !== "page");
      assert.equal(h.controls.maxActiveRequests,1);
      assert.equal(h.controls.connections.length,0);
    } finally { h.context.playspaceChat.dispose(); }
  }
});

for (const fence of ["close","hide","target","dispose"]) {
  test(`fresh pre-logout status is fenced by ${fence}; no logout or retirement follows`, async () => {
    const h = await claimed();
    try {
      h.controls.holdStatus = true;
      h.get("forget-pairing").click(); await h.tick();
      assert.equal(h.controls.activeRequests,1);
      if (fence === "close") h.get("close-connection").click();
      if (fence === "hide") { h.document.visibilityState = "hidden"; h.document.fire("visibilitychange"); }
      if (fence === "target") { h.get("target-participant").value = "new-agent"; h.get("target-participant").fire("input"); }
      if (fence === "dispose") h.context.playspaceChat.dispose();
      h.controls.resolveStatus(); await h.tick();
      assert.equal(count(h,"/logout"),0); assert.equal(h.requestStorage.size,1);
      assert.equal(h.controls.maxActiveRequests,1);
    } finally { h.context.playspaceChat.dispose(); }
  });
}

test("failed fresh status never logs out; already-issued logout may commit after close but cannot retire stale UI binding", async () => {
  for (const failStatus of [true,false]) {
    const h = await claimed();
    try {
      if (failStatus) h.controls.failNext = "Status";
      else h.controls.holdForget = true;
      h.get("forget-pairing").click(); await h.tick();
      if (!failStatus) {
        h.get("close-connection").click();
        h.controls.resolveForget(); await h.tick();
        assert.equal(h.controls.authenticated,false);
      }
      assert.equal(count(h,"/logout"),failStatus ? 0 : 1);
      assert.equal(h.requestStorage.size,1);
      assert.equal(h.controls.maxActiveRequests,1);
    } finally { h.context.playspaceChat.dispose(); }
  }
});
