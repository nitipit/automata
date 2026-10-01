import test from "node:test";
import assert from "node:assert/strict";
import { load } from "./runtime.mjs";
const { createCacheRecovery } = await load("recovery.js");

const key = "http://127.0.0.1:8775/__playspace_chat_snapshot_v2__";
test("recovery writes ordered snapshots and reports success only after put", async () => {
  const puts = [], states = [];
  let release;
  let stored;
  const gate = new Promise(resolve => { release = resolve; });
  const cache = {
    async put(_key, response) {
      const value = await response.json();
      puts.push(value);
      if (puts.length === 1) await gate;
      stored = value;
    },
    async match() { return stored ? new Response(JSON.stringify(stored)) : undefined; },
  };
  const recovery = createCacheRecovery({ key, cacheStorage: { async open() { return cache; } }, onState: value => states.push(value) });
  const first = recovery.save({ version: 1, composer: "one" });
  const second = recovery.save({ version: 1, composer: "two" });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(puts, [{ version: 1, composer: "one" }]);
  assert.ok(!states.some(state => state.startsWith("Saved")));
  release();
  assert.equal(await first, true);
  assert.equal(await second, true);
  await recovery.flush();
  assert.equal((await recovery.load()).composer, "two");
  assert.deepEqual(puts.map(value => value.composer), ["one", "two"]);
  assert.ok(states.some(state => state.startsWith("Saved v2 locally")));
});

test("unavailable/malformed storage is visible and never erased", async () => {
  const states = [];
  const unavailable = createCacheRecovery({ key, cacheStorage: null, onState: value => states.push(value) });
  assert.equal(await unavailable.save({ version: 1 }), false);
  assert.equal(await unavailable.load(), null);
  assert.ok(states.some(state => state.startsWith("Not saved")));
  let erased = false;
  const broken = createCacheRecovery({ key, cacheStorage: { async open() { return {
    async match() { return new Response("bad JSON"); },
    async delete() { erased = true; },
  }; } }, onState: value => states.push(value) });
  assert.equal(await broken.load(), null);
  assert.equal(erased, false);
  assert.ok(states.some(state => state.includes("malformed")));
  broken.dispose();
  const count = states.length;
  await broken.load();
  assert.equal(states.length, count);
});

test("failed write does not poison the next ordered save", async () => {
  let attempt = 0;
  let saved;
  const recovery = createCacheRecovery({ key, cacheStorage: { async open() { return {
    async put(_key, response) { if (++attempt === 1) throw Error("storage"); saved = await response.json(); },
  }; } } });
  assert.equal(await recovery.save({ composer: "first" }), false);
  assert.equal(await recovery.save({ composer: "second" }), true);
  assert.deepEqual(saved, { composer: "second" });
});
