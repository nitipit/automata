import assert from "node:assert/strict";
import test from "node:test";
import {load} from "./runtime.mjs";
const {createPairingRequest} = await load("../router/pairing-request.js");

function fixture(extra = {}) {
  let clock = 1000, value = JSON.stringify({capability:"a".repeat(64), request:"RP-AAAAAAAAAA",
    state:"approved", participant:"page", expiresAt:1300, ...extra});
  const calls = [], controls = {failWrite:false, loseResponse:false};
  const storage = {
    getItem:() => value,
    setItem:(_, next) => { if (controls.failWrite) throw new Error("storage denied"); value = next; },
    removeItem:() => { value = null; },
  };
  const options = {getStorage:() => storage, now:() => clock * 1000,
    location:{href:"http://127.0.0.1:8787/"}, auth:{
      async redeemRequest() {
        calls.push("redeem"); assert.equal(JSON.parse(value).claimAttempted,true);
        if (controls.loseResponse) throw new Error("lost response");
        return {authenticated:true,participant:"page"};
      },
      async requestStatus() { calls.push("check"); return {request:"RP-AAAAAAAAAA",state:"approved",participant:"page",expiresAt:1300}; },
      async requestPairing() { calls.push("create"); return {request:"RP-AAAAAAAAAA",state:"pending",expiresAt:1300}; },
    }};
  const requester = createPairingRequest(options);
  return {requester, options, calls, controls, stored:() => JSON.parse(value), expire:() => { clock = 1301; }};
}

test("legacy absent/false attempt markers restore unattempted; present marker must be strictly boolean", async () => {
  for (const extra of [{}, {claimAttempted:false}]) {
    const f = fixture(extra);
    assert.equal(f.requester.restore().claimAttempted,false);
    await f.requester.claim(); assert.deepEqual(f.calls,["redeem"]);
    assert.equal(f.requester.view().claimUncertain,false);
    assert.equal(f.stored().claimAttempted,true); assert.equal(f.stored().claimConfirmed,true);
  }
  for (const marker of [null,0,1,"true",{},[]]) {
    const f = fixture({claimAttempted:marker});
    assert.throws(() => f.requester.restore(),/Invalid transient/);
    assert.deepEqual(f.calls,[]);
  }
});

test("failed attempt persistence issues zero redeem calls", async () => {
  const f = fixture(); f.requester.restore(); f.controls.failWrite = true;
  await assert.rejects(f.requester.claim(),/storage denied/);
  assert.deepEqual(f.calls,[]); assert.equal(f.requester.view().claimAttempted,false);
});

test("ambiguous attempt is sticky through checks/reload/TTL and cannot be cleared or replaced", async () => {
  const f = fixture(); f.requester.restore(); f.controls.loseResponse = true;
  await assert.rejects(f.requester.claim(),/lost response/);
  await f.requester.check(); // even fresh approved server state does not remove the attempt
  assert.equal(f.requester.view().claimUncertain,true);
  await assert.rejects(f.requester.start(),/operator repair/);
  await assert.rejects(f.requester.claim(),/already attempted/);
  const restored = createPairingRequest(f.options);
  assert.equal(restored.restore().claimAttempted,true);
  f.expire();
  assert.equal(restored.view().state,"expired"); assert.equal(restored.view().claimUncertain,true);
  await assert.rejects(restored.start(),/operator repair/);
  assert.throws(() => restored.clearExpired(),/operator repair/);
  restored.confirmSession({authenticated:false});
  restored.confirmSession({authenticated:true,participant:"different-page"});
  assert.equal(restored.view().claimUncertain,true);
  assert.deepEqual(f.calls,["redeem","check"]);
  restored.confirmSession({authenticated:true,participant:"page"});
  assert.equal(restored.view().claimUncertain,false);
  assert.equal(restored.view().claimAttempted,true);
  assert.equal(restored.view().state,"redeemed");
  assert.throws(() => restored.clearExpired(),/explicit session revocation/);
  assert.throws(() => restored.clearExpired({revokedParticipant:"different-page"}),/explicit session revocation/);
  restored.clearExpired({revokedParticipant:"page"}); assert.equal(f.stored(),null);
});

test("accept cannot erase an already persisted attempt marker for the same binding", async () => {
  const f = fixture(); f.requester.restore();
  let settle;
  f.options.auth.requestStatus = () => new Promise(resolve => { settle = resolve; });
  const pending = f.requester.check();
  const second = createPairingRequest(f.options); second.restore();
  f.controls.loseResponse = true;
  await assert.rejects(second.claim(),/lost response/);
  settle({request:"RP-AAAAAAAAAA",state:"approved",participant:"page",expiresAt:1300});
  await pending;
  assert.equal(f.requester.view().claimUncertain,true);
  assert.equal(f.stored().claimAttempted,true);
  await assert.rejects(f.requester.claim(),/already attempted/);
});

test("a non-confirming redeem response stays unresolved rather than permitting fresh pairing", async () => {
  const f = fixture(); f.requester.restore();
  f.options.auth.redeemRequest = async () => ({authenticated:false});
  await assert.rejects(f.requester.claim(),/did not confirm/);
  assert.equal(f.requester.view().claimUncertain,true);
  f.expire(); await assert.rejects(f.requester.start(),/operator repair/);
});

test("confirmed and legacy redemptions retain repair identity after TTL until matching revocation", async () => {
  for (const legacy of [false,true]) {
    const f = fixture(legacy ? {state:"redeemed"} : {}); f.requester.restore();
    if (!legacy) await f.requester.claim();
    f.expire();
    const restored = createPairingRequest(f.options);
    assert.equal(restored.restore().state,"redeemed");
    assert.equal(restored.view().claimUncertain,false);
    await assert.rejects(restored.start(),/explicit session revocation/);
    assert.throws(() => restored.clearExpired(),/explicit session revocation/);
    assert.throws(() => restored.clearExpired({revokedParticipant:"another-page"}),/explicit session revocation/);
    restored.clearExpired({revokedParticipant:"page"});
    assert.equal(restored.view(),null); assert.equal(f.stored(),null);
    assert.deepEqual(f.calls,legacy ? [] : ["redeem"]);
  }
});

test("cleared binding fences an old delayed response", async () => {
  const f = fixture(); f.requester.restore();
  let settle;
  f.options.auth.requestStatus = () => new Promise(resolve => { settle = resolve; });
  const pending = f.requester.check();
  f.expire(); f.requester.clearExpired();
  settle({request:"RP-AAAAAAAAAA",state:"approved",participant:"page",expiresAt:1300});
  await pending;
  assert.equal(f.requester.view(),null); assert.equal(f.stored(),null);
});
