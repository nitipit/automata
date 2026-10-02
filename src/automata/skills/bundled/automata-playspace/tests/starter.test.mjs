import test from "node:test";
import assert from "node:assert/strict";
import { starterHarness, deferred, response, settle } from "./starter-harness.mjs";

test("actual starter restores local drafts, pairs separately, and applies only Pi terminal replies", async () => {
  const h = await starterHarness();
  assert.equal(h.clients.length, 0); assert.equal(h.control.authCalls, 0);
  h.send("local draft"); assert.match(h.message, /Disconnected/);
  assert.equal(await h.page.save(), true);
  assert.equal(h.saves[0].layout[0].state.draft, "local draft");
  assert.deepEqual(Object.keys(h.saves[0]).sort(), ["definitions", "layout", "version"]);
  assert.equal(await h.page.pair("private-one-use-code"), true);
  assert.equal(h.clients.length, 0);
  assert.equal(h.elements.code.value, "");
  assert.equal(JSON.stringify(h.saves).includes("private-one-use-code"), false);
  assert.equal(await h.page.connect(), true);
  const sent = h.send();
  assert.deepEqual(sent.payload, { text: "question" });
  sent.options.onResponse(response("admitted", null, false));
  assert.match(h.message, /admitted/);
  sent.accepted.resolve({ status: "forwarded" }); await settle();
  assert.match(h.message, /admitted/);
  sent.options.onResponse(response("reply", { text: "result" }));
  assert.equal(h.state.result, "result");
  assert.match(h.message, /Reply applied/);
  await h.page.save();
  assert.equal(await h.page.restore(), true);
  assert.equal(h.state.result, "result");
  assert.equal(h.page.router.isConnected(), false);
  assert.equal(h.clients.length, 1);
  h.page.dispose();
});

test("terminal reply before acceptance cannot regress; invalid/rejected/unknown replies never update", async () => {
  const h = await starterHarness(); await h.page.connect();
  h.control.onSend = sent => sent.options.onResponse(response("reply", { text: "early result" }));
  const early = h.send();
  assert.equal(h.state.result, "early result");
  early.accepted.resolve({ status: "forwarded" }); await settle();
  assert.match(h.message, /Reply applied/);
  h.control.onSend = null;
  for (const packet of [response("rejected", { text: "not a result" }),
    response("reply", { wrong: "shape" }), response("unknown", { text: "not a result" }),
    { type: "route_closed", uncertain: true }]) {
    const sent = h.send();
    sent.options.onResponse(packet);
    const terminal = h.message;
    assert.equal(h.state.result, "early result");
    sent.accepted.resolve({ status: "forwarded" }); await settle();
    assert.equal(h.message, terminal);
  }
  h.page.dispose();
});

test("delayed auth -> Restore fences Connect before socket creation", async () => {
  const h = await starterHarness();
  h.control.authWait = deferred();
  const connect = h.page.connect();
  await settle();
  const restore = h.page.restore();
  h.control.authWait.resolve({ authenticated: true, participant: "page" });
  assert.equal(await connect, false);
  await restore;
  assert.equal(h.clients.length, 0);
  h.page.dispose();
});

test("new Connect fences delayed Restore load; old connection failure cannot close newer client", async () => {
  const h = await starterHarness();
  h.control.loadWait = deferred();
  const restore = h.page.restore(); await settle();
  assert.equal(await h.page.connect(), true);
  const draft = h.page.runtime.snapshot(); draft.layout[0].state.result = "old restore";
  h.control.loadWait.resolve(draft);
  assert.equal(await restore, false);
  assert.equal(h.state.result, "");
  assert.equal(h.page.router.isConnected(), true);
  h.control.connectWait = deferred();
  const oldWait = h.control.connectWait;
  const first = h.page.connect(); await settle();
  h.control.connectWait = null;
  assert.equal(await h.page.connect(), true);
  const latest = h.clients.at(-1);
  oldWait.reject(Error("old failure"));
  assert.equal(await first, false);
  assert.equal(latest.closed, false);
  assert.match(h.connection, /Connected/);
  h.page.dispose();
});

for (const action of ["disconnect", "replace", "dispose"]) {
  test(`late accepted success/failure and responses are fenced after ${action}`, async () => {
    for (const reject of [false, true]) {
      const h = await starterHarness(); await h.page.connect();
      const sent = h.send();
      if (action === "replace") h.page.runtime.replace(h.page.runtime.snapshot());
      else h.page[action]();
      const before = h.message;
      sent.options.onResponse(response("reply", { text: "stale" }));
      if (reject) sent.accepted.reject(Error("late"));
      else sent.accepted.resolve({ status: "forwarded" });
      await settle();
      assert.equal(h.message, before);
      if (action !== "dispose") assert.equal(h.state.result, "");
      h.page.dispose();
    }
  });
}

test("invalid snapshot and altered source/CSS retain last-good draft without execution", async () => {
  const h = await starterHarness();
  h.send("keep this draft");
  const good = h.page.runtime.snapshot();
  for (const mutate of [
    value => { value.layout[0].state = { invalid: true }; },
    value => { value.definitions[0].source = "() => { globalThis.badCacheExecuted = true; }"; },
    value => { value.definitions[0].css += " changed"; },
  ]) {
    h.control.stored = structuredClone(good); mutate(h.control.stored);
    assert.equal(await h.page.restore(), false);
    assert.deepEqual(h.page.runtime.snapshot(), good);
    assert.match(h.message, /last good draft retained/);
  }
  assert.equal(globalThis.badCacheExecuted, undefined);
  h.control.stored = good;
  assert.equal(await h.page.restore(), true);
  assert.equal(await h.page.restore(), true); // no duplicate custom-element registration
  h.page.dispose();
});

test("replacement permits a new explicit request while retired request completion stays inert", async () => {
  const h = await starterHarness(); await h.page.connect();
  const previous = h.send("old");
  h.page.runtime.replace(h.page.runtime.snapshot());
  const next = h.send("new");
  assert.notEqual(previous, next);
  assert.deepEqual(next.payload, { text: "new" });
  previous.options.onResponse(response("reply", { text: "old" }));
  next.options.onResponse(response("reply", { text: "new" }));
  previous.accepted.reject(Error("retired"));
  next.accepted.resolve({ status: "forwarded" });
  await settle();
  assert.equal(h.state.result, "new");
  h.page.dispose();
});

for (const action of ["disconnect", "dispose"]) {
  test(`opening connection completing after ${action} cannot publish or reopen`, async () => {
    const h = await starterHarness(); h.control.connectWait = deferred();
    const connecting = h.page.connect(); await settle();
    assert.equal(h.clients.length, 1);
    h.page[action]();
    const before = h.connection;
    h.control.connectWait.resolve();
    assert.equal(await connecting, false);
    assert.equal(h.connection, before);
    assert.equal(h.page.router.isConnected(), false);
    h.page.dispose();
  });
}

test("save completion distinguishes a saved snapshot from edits made while writing", async () => {
  const h = await starterHarness(); h.control.saveWait = deferred();
  const saving = h.page.save();
  const input = h.elements.root.children[0].querySelector("textarea");
  input.value = "new unsaved edit";
  input.emit("input");
  h.control.saveWait.resolve();
  assert.equal(await saving, true);
  assert.match(h.message, /current edits are not saved/);
  assert.equal(h.control.stored.layout[0].state.draft, "");
  h.page.dispose();
});

test("unauthenticated status cannot connect, and delayed auth after disposal cannot publish", async () => {
  const h = await starterHarness();
  h.control.authWait = deferred();
  let connect = h.page.connect();
  h.control.authWait.resolve({ authenticated: false });
  assert.equal(await connect, false); assert.equal(h.clients.length, 0);
  h.control.authWait = deferred(); connect = h.page.connect();
  h.page.dispose(); const before = h.connection;
  h.control.authWait.resolve({ authenticated: true, participant: "page" });
  assert.equal(await connect, false); assert.equal(h.clients.length, 0);
  assert.equal(h.connection, before);
});
