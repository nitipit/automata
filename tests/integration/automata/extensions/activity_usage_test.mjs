import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
const { default: register } = await import(pathToFileURL(join(process.env.CONTEXT_TEST_ROOT, "activity-usage.ts")));
function fixture() {
  const handlers = new Map(), tools = new Map(), commands = new Map(), sent = [];
  register({ on: (name, fn) => handlers.set(name, fn), registerTool: tool => tools.set(tool.name, tool),
    registerCommand: (name, cmd) => commands.set(name, cmd), sendMessage: (...args) => sent.push(args),
    appendEntry: () => assert.fail("unexpected entry") });
  const ctx = { hasUI: true, ui: { notify() {} } };
  return { sent, emit: (name, event = {}) => handlers.get(name)?.(event, ctx),
    status: async () => (await tools.get("activity_usage").execute()).details,
    command: () => commands.get("activity-usage").handler("", ctx) };
}
test("input anchor, assistant usage deduplication, compaction preservation, resets", async t => {
  let now = 1_000_000; t.mock.method(Date, "now", () => now); const f = fixture();
  assert.equal((await f.status()).inputAnchorTimestamp, null);
  f.emit("message_start", { message: { role: "user", timestamp: now } });
  const msg = { role: "assistant", timestamp: now, usage: { input: 100, output: 20, cacheRead: 5, cacheWrite: 2 } };
  f.emit("message_end", { message: msg }); f.emit("message_end", { message: msg });
  f.emit("message_end", { message: { role: "assistant", timestamp: now - 1, usage: { input: 999 } } });
  f.emit("message_end", { message: { role: "toolResult", usage: { input: 999 } } });
  f.emit("session_compact"); now += 1000;
  let status = await f.status(); assert.equal(status.elapsedMs, 1000);
  assert.deepEqual(status.modelUsage, { input: 100, output: 20, cacheRead: 5, cacheWrite: 2, totalTokens: 127 });
  f.emit("message_start", { message: { role: "user", content: "coordinator", timestamp: NaN } });
  status = await f.status(); assert.equal(status.inputAnchorTimestamp, now); assert.equal(status.modelUsage.input, 0);
  await f.command();
  for (const event of ["session_start", "session_tree"]) {
    f.emit(event); assert.equal((await f.status()).inputAnchorTimestamp, null);
    f.emit("message_start", { message: { role: "user", timestamp: now } });
  }
});
test("negative and nonfinite usage fields are ignored; invalid totals fall back to valid components", async () => {
  const f = fixture(); f.emit("message_start", { message: { role: "user", timestamp: 100 } });
  f.emit("message_end", { message: { role: "assistant", timestamp: 101,
    usage: { input: -30, output: 5, cacheRead: Infinity, cacheWrite: 2, totalTokens: -25 } } });
  f.emit("message_end", { message: { role: "assistant", timestamp: 102,
    usage: { input: 4, output: NaN, cacheRead: 3, cacheWrite: -1, totalTokens: Infinity } } });
  f.emit("message_end", { message: { role: "assistant", timestamp: 103,
    usage: { input: 1, output: 2, cacheRead: 3, cacheWrite: 4, totalTokens: 11 } } });
  assert.deepEqual((await f.status()).modelUsage,
    { input: 5, output: 7, cacheRead: 6, cacheWrite: 6, totalTokens: 25 });
});
test("time observations coalesce at settlement without wake, new input clears pending", async t => {
  let now = 1_000_000; t.mock.method(Date, "now", () => now); const f = fixture();
  f.emit("message_start", { message: { role: "user", timestamp: now } });
  now += 600_000; f.emit("turn_end"); now += 1_260_000; f.emit("agent_end");
  assert.equal(f.sent.length, 0); f.emit("agent_settled");
  assert.equal(f.sent.length, 1); assert.equal(f.sent[0][0].details.observations.timeThreshold, 3);
  assert.equal(f.sent[0][0].details.observedAt, now);
  assert.match(f.sent[0][0].content, /Historical activity observation/);
  assert.match(f.sent[0][0].content, new RegExp(new Date(now).toISOString().replaceAll(".", "\\.")));
  assert.doesNotMatch(f.sent[0][0].content, /latest user input/);
  assert.deepEqual(f.sent[0][1], { deliverAs: "nextTurn" }); f.emit("agent_settled"); assert.equal(f.sent.length, 1);
  now += 600_000; f.emit("turn_end"); f.emit("message_start", { message: { role: "user", timestamp: now } });
  f.emit("agent_settled"); assert.equal(f.sent.length, 1); assert.equal((await f.status()).elapsedMs, 0);
});
