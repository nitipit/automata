import test from "node:test";
import assert from "node:assert/strict";
import { load } from "./runtime.mjs";
const { createCacheRecovery } = await load("playspace.js");
const options = { cacheName: "test-owned-core", key: "/draft", origin: "http://127.0.0.1:9999" };

test("ordered writes resolve only after put and preserve the last successful snapshot", async () => {
  let release, stored, attempts = 0;
  const puts = [], states = [];
  const gate = new Promise(resolve => { release = resolve; });
  const cache = {
    async put(key, response) {
      const value = await response.json(); puts.push(value);
      assert.equal(key, "http://127.0.0.1:9999/draft");
      if (++attempts === 1) await gate;
      if (value.fail) throw Error("write");
      stored = value;
    },
    async match() { return stored ? new Response(JSON.stringify(stored)) : undefined; },
  };
  const recovery = createCacheRecovery({ ...options, cacheStorage: { async open() { return cache; } },
    onState: state => states.push(state) });
  const first = recovery.save({ draft: "one" });
  const second = recovery.save({ draft: "two" });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(puts, [{ draft: "one" }]);
  assert.ok(!states.some(state => state.startsWith("Saved")));
  release();
  assert.equal(await first, true); assert.equal(await second, true);
  assert.equal(await recovery.save({ fail: true }), false);
  assert.deepEqual(await recovery.load(), { draft: "two" });
  assert.equal(await recovery.save({ draft: "three" }), true);
  await recovery.flush();
  assert.deepEqual(await recovery.load(), { draft: "three" });
});

test("key admission, malformed/unavailable cache and non-JSON saves never erase entries", async () => {
  assert.throws(() => createCacheRecovery({ ...options, key: "https://elsewhere.test/draft" }));
  assert.throws(() => createCacheRecovery({ ...options, cacheName: "" }));
  const unavailable = createCacheRecovery({ ...options, cacheStorage: null });
  assert.equal(await unavailable.save({ draft: "one" }), false);
  assert.equal(await unavailable.load(), null);
  let erased = false, puts = 0;
  const cacheStorage = { async open() { return {
    async match() { return new Response("not JSON"); },
    async delete() { erased = true; }, async put() { puts++; },
  }; } };
  const recovery = createCacheRecovery({ ...options, cacheStorage });
  assert.equal(await recovery.load(), null);
  assert.equal(await recovery.save({ bad: undefined }), false);
  assert.equal(erased, false); assert.equal(puts, 0);
  recovery.dispose();
  assert.equal(await recovery.save({ draft: "after dispose" }), false);
  assert.equal(await recovery.load(), null);
  assert.equal(puts, 0);
});
