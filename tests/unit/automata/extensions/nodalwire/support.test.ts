import assert from "node:assert/strict";
import { mkdtemp, writeFile, chmod, symlink, mkdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const root = process.env.PI_EXTENSION_TEST_ROOT;
assert.ok(root, "PI_EXTENSION_TEST_ROOT must select the current repository bundle");
const { validName, validateNativeMessage, safeTransportError, withJoinCredential } =
  await import(pathToFileURL(join(root, "safety.ts")).href);
const { ReplyReferences } = await import(pathToFileURL(join(root, "reply-references.ts")).href);
const binding = { endpoint: "tcp://127.0.0.1:5555", network: "review" };
const native = (changes = {}) => ({
  id: "a".repeat(32), sender: "peer", network: "review", payload: Uint8Array.of(42), ...changes,
});
const config = () => ({ aliases: { review: { ...binding, env: "NW_TEST_JOIN" } } });
const SECRET = "PRIVATE-TOKEN-not-for-diagnostics";
const fixedCredentialError = error => {
  assert.equal(error.message, "NodalWire join credential configuration or reference is invalid");
  assert.equal(error.cause, undefined);
  return true;
};

async function credentialFixture(t, value = config()) {
  const directory = await mkdtemp(join(tmpdir(), "nw-support-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const path = join(directory, "aliases.json");
  await writeFile(path, typeof value === "string" ? value : JSON.stringify(value), { mode: 0o600 });
  return { directory, path };
}

test("native route names and IDs use exact bounded ASCII syntax", () => {
  for (const name of ["a", "0", "peer-_.7", "a".repeat(128)]) assert.equal(validName(name), true);
  for (const name of [undefined, null, 7, "", "_peer", "peer name", "peer\n", "ไทย", "a".repeat(129)]) {
    assert.equal(validName(name), false);
  }
  validateNativeMessage(native());
  validateNativeMessage(native({ reply_to: "b".repeat(32), payload: Buffer.from("bytes") }));
  for (const value of [null, {}, native({ id: "A".repeat(32) }), native({ id: "a".repeat(31) }),
    native({ reply_to: "" }), native({ reply_to: null }), native({ sender: SECRET + "\n" }),
    native({ network: "bad/network" }), native({ payload: [1] }),
    { get id() { throw new Error(SECRET); } }]) {
    assert.throws(() => validateNativeMessage(value), error => {
      assert.equal(error.message, "Invalid native message metadata");
      return true;
    });
  }
});

test("transport diagnostics allow only known operations/codes and preserve uncertainty", () => {
  for (const code of ["join_denied", "not_member", "destination_not_member", "network_not_found",
    "route_denied", "destination_unavailable", "destination_full", "pending_full", "local_queue_full"]) {
    const result = safeTransportError({ code, message: SECRET, cause: new Error(SECRET) }, "join");
    assert.match(result.message, new RegExp(`\\(${code}\\)`));
    assert.doesNotMatch(result.message, /PRIVATE/);
    assert.equal(result.cause, undefined);
  }
  for (const error of [new Error(SECRET), SECRET, undefined, { code: SECRET, name: SECRET },
    { name: "ReceiptTimeout", message: SECRET }, { name: "AbortError", reason: SECRET },
    { code: "closed" }, { code: "connection_failed" }, { code: "invalid_receipt" },
    { get code() { throw new Error(SECRET); } }]) {
    const result = safeTransportError(error, SECRET);
    assert.match(result.message, /NodalWire operation .*effect uncertain/);
    assert.doesNotMatch(result.message, /PRIVATE/);
    assert.equal(result.cause, undefined);
  }
});

test("omitted credential reference does no configuration or environment I/O", async () => {
  let calls = 0;
  const result = await withJoinCredential("/not/a/readable/config", undefined, binding, async credential => {
    calls++;
    assert.equal(credential, undefined);
    return 17;
  }, new Proxy({}, { get() { throw new Error("must not inspect env"); } }));
  assert.equal(result, 17);
  assert.equal(calls, 1);
});

test("credential aliases bind exact endpoint/network and resolve environment lazily", async t => {
  const { path } = await credentialFixture(t);
  const env = { NW_TEST_JOIN: SECRET };
  const seen = [];
  for (const value of [SECRET, "changed", "!", "~".repeat(1024)]) {
    env.NW_TEST_JOIN = value;
    const result = await withJoinCredential(path, "review", binding, async credential => {
      seen.push(credential);
      return "joined";
    }, env);
    assert.equal(result, "joined");
  }
  assert.deepEqual(seen, [SECRET, "changed", "!", "~".repeat(1024)]);
  for (const route of [{ ...binding, network: "other" }, { ...binding, endpoint: "tcp://localhost:5555" }]) {
    await assert.rejects(withJoinCredential(path, "review", route, async () => assert.fail("must not dispatch"), env), fixedCredentialError);
  }
  await assert.rejects(withJoinCredential(path, "unknown", binding, async () => assert.fail(), env), fixedCredentialError);
});

test("credential lookup rejects missing, inherited, whitespace, Unicode and oversized secrets without fallback", async t => {
  const { path } = await credentialFixture(t);
  for (const env of [{}, Object.create({ NW_TEST_JOIN: SECRET }),
    ...["", " ", "token\n", " token", "token ", "\x7f", "ไทย", "a".repeat(1025)].map(NW_TEST_JOIN => ({ NW_TEST_JOIN }))]) {
    await assert.rejects(withJoinCredential(path, "review", binding, async () => assert.fail("must not dispatch"), env), fixedCredentialError);
  }
  for (const [selected, ref] of [[undefined, "review"], [path, "bad/ref"], ["/missing/" + SECRET, "review"]]) {
    await assert.rejects(withJoinCredential(selected, ref, binding, async () => assert.fail()), fixedCredentialError);
  }
});

test("strict configuration rejects extra fields, invalid aliases and malformed entries", async t => {
  const bad = [null, [], {}, { aliases: [] }, { aliases: {}, credential: SECRET },
    { aliases: { "bad/name": { ...binding, env: "NW_TEST_JOIN" } } },
    { aliases: { review: { ...binding, env: "NW_TEST_JOIN", credential: SECRET } } },
    { aliases: { review: { ...binding } } },
    { aliases: { review: { ...binding, network: "bad/network", env: "NW_TEST_JOIN" } } },
    { aliases: { review: { ...binding, endpoint: 1, env: "NW_TEST_JOIN" } } },
    { aliases: { review: { ...binding, env: "!shell command" } } },
    { aliases: { review: { ...binding, env: "" } } },
    { aliases: Object.fromEntries(Array.from({ length: 65 }, (_, n) => [`alias${n}`, { ...binding, env: "NW_TEST_JOIN" }])) },
    '{"aliases":', '{"aliases":{},"__proto__":{}}'];
  for (const value of bad) {
    const { path } = await credentialFixture(t, value);
    await assert.rejects(withJoinCredential(path, "review", binding, async () => assert.fail(), { NW_TEST_JOIN: SECRET }), fixedCredentialError);
  }
});

test("configuration size and alias count accept exact bounds", async t => {
  const value = config();
  for (let n = 1; n < 64; n++) value.aliases[`alias${n}`] = { ...binding, env: "NW_TEST_JOIN" };
  const json = JSON.stringify(value);
  const { path } = await credentialFixture(t, json + " ".repeat(32768 - Buffer.byteLength(json)));
  assert.equal(await withJoinCredential(path, "review", binding, async () => true, { NW_TEST_JOIN: SECRET }), true);
  await writeFile(path, json + " ".repeat(32769 - Buffer.byteLength(json)));
  await assert.rejects(withJoinCredential(path, "review", binding, async () => assert.fail()), fixedCredentialError);
  await writeFile(path, Buffer.from([0xff]));
  await assert.rejects(withJoinCredential(path, "review", binding, async () => assert.fail()), fixedCredentialError);
});

test("configuration refuses symlinks, directories and unsafe POSIX permissions", async t => {
  const { directory, path } = await credentialFixture(t);
  const link = join(directory, "link.json");
  await symlink(path, link);
  const folder = join(directory, "folder");
  await mkdir(folder);
  for (const selected of [link, folder]) {
    await assert.rejects(withJoinCredential(selected, "review", binding, async () => assert.fail()), fixedCredentialError);
  }
  if (process.platform !== "win32") {
    for (const mode of [0o620, 0o602, 0o666]) {
      await chmod(path, mode);
      await assert.rejects(withJoinCredential(path, "review", binding, async () => assert.fail()), fixedCredentialError);
    }
    await chmod(path, 0o600);
    assert.equal(await withJoinCredential(path, "review", binding, async () => true, { NW_TEST_JOIN: SECRET }), true);
  }
});

test("callback errors propagate internally, without being mistaken for configuration failure", async t => {
  const { path } = await credentialFixture(t);
  const failure = new Error(SECRET);
  await assert.rejects(withJoinCredential(path, "review", binding, async () => { throw failure; }, { NW_TEST_JOIN: SECRET }), error => error === failure);
});

test("reply references snapshot immutable metadata, retain no content and consume once", () => {
  const refs = new ReplyReferences();
  const incoming = native({ reply_to: "b".repeat(32) });
  const ref = refs.add(1, incoming);
  assert.equal(typeof ref, "string");
  assert.notEqual(ref, incoming.id);
  incoming.sender = "changed";
  incoming.payload[0] = 99;
  const saved = refs.take(1, ref);
  assert.deepEqual(saved, { ...native({ reply_to: "b".repeat(32) }), payload: new Uint8Array(0) });
  assert.ok(Object.isFrozen(saved));
  assert.throws(() => { saved.sender = "mutated"; }, TypeError);
  assert.throws(() => refs.take(1, ref), /unavailable or expired/);
  assert.throws(() => refs.take(1, SECRET), error => !error.message.includes(SECRET));
});

test("TTL expires at exact monotonic boundary and failed lookup never refreshes it", () => {
  let now = 100;
  const refs = new ReplyReferences({ ttlMs: 10, now: () => now });
  const ref = refs.add(1, native());
  now = 109;
  assert.throws(() => refs.take(2, ref), /unavailable/);
  now = 110;
  assert.throws(() => refs.take(1, ref), /expired/);
  const later = refs.add(1, native());
  now = 119;
  assert.equal(refs.take(1, later).sender, "peer");
});

test("capacity rejects allocation without evicting live refs, then lazy expiry releases space", () => {
  let now = 0;
  const refs = new ReplyReferences({ capacity: 2, ttlMs: 10, now: () => now });
  const first = refs.add(1, native());
  const second = refs.add(1, native());
  assert.notEqual(first, second);
  assert.equal(refs.add(1, native()), undefined);
  assert.equal(refs.take(1, first).sender, "peer");
  const third = refs.add(1, native());
  assert.equal(typeof third, "string");
  now = 10;
  assert.equal(typeof refs.add(1, native()), "string");
  for (const ref of [second, third]) assert.throws(() => refs.take(1, ref), /expired/);
});

test("generation, network invalidation, deletion and clear isolate routing references", () => {
  const refs = new ReplyReferences();
  const a = refs.add(1, native());
  const b = refs.add(2, native());
  const c = refs.add(1, native({ network: "other" }));
  assert.throws(() => refs.take(2, a), /unavailable/);
  refs.invalidateNetwork(1, "review");
  assert.throws(() => refs.take(1, a), /unavailable/);
  assert.equal(refs.take(2, b).network, "review");
  assert.equal(refs.take(1, c).network, "other");
  const d = refs.add(3, native());
  refs.delete(d);
  refs.delete(d);
  assert.throws(() => refs.take(3, d), /unavailable/);
  const e = refs.add(3, native());
  refs.clear(); refs.clear();
  assert.throws(() => refs.take(3, e), /unavailable/);
});

test("reply reference limits and incoming metadata are validated before allocation", () => {
  for (const capacity of [0, -1, 1.5, Infinity, NaN]) assert.throws(() => new ReplyReferences({ capacity }));
  for (const ttlMs of [0, -1, Infinity, NaN]) assert.throws(() => new ReplyReferences({ ttlMs }));
  const refs = new ReplyReferences({ capacity: 1 });
  assert.throws(() => refs.add(1, native({ network: "bad/name" })), /Invalid native/);
  assert.throws(() => refs.add(NaN, native()), /generation/);
  assert.equal(typeof refs.add(1, native()), "string");
});
