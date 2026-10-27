import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { default: register, RUNTIME_PRESSURE_TYPE, pressureThresholdForPercent } = await import(pathToFileURL(join(process.env.CONTEXT_TEST_ROOT, "context-status.ts")));
function fixture() {
  const handlers = new Map(), tools = new Map(), commands = new Map(), sent = [];
  register({ on: (name, fn) => handlers.set(name, fn), registerTool: (tool) => tools.set(tool.name, tool),
    registerCommand: (name, command) => commands.set(name, command),
    sendMessage: (...args) => sent.push(args), appendEntry: () => assert.fail("no persistence") });
  let usage = { tokens: 0, contextWindow: 1_000_000, percent: 0 };
  const ctx = { model: { provider: "openai", id: "test", contextWindow: 1_000_000 },
    getContextUsage: () => usage, hasUI: true, ui: { notify() {} } };
  const emit = (name, event = {}) => handlers.get(name)?.(event, ctx);
  return { ctx, sent, emit, set: (tokens, percent = tokens / 10000, contextWindow = 1_000_000) => { usage = { tokens, percent, contextWindow }; },
    request: (messages = []) => emit("context", { messages }).messages,
    status: async () => (await tools.get("context_status").execute("", {}, undefined, undefined, ctx)).details,
    command: () => commands.get("context-status").handler("", ctx) };
}
function observation(f) { return f.request().find(m => m.customType === RUNTIME_PRESSURE_TYPE); }
test("first reading, exact boundaries, jumps and high water", () => {
  const f = fixture();
  f.set(49_999); assert.equal(observation(f), undefined);
  f.set(50_000); assert.match(observation(f).content, /Context usage: 50,000 \/ 1,000,000 tokens\nWorking model: openai\/test/);
  assert.equal(observation(f), undefined);
  f.set(302_000); assert.match(observation(f).content, /302,000/);
  for (const n of [299_999, 300_000, 349_999]) { f.set(n); assert.equal(observation(f), undefined); }
  f.set(350_000); assert.match(observation(f).content, /350,000/);
  assert.deepEqual(f.sent, []);
});
test("invalid usage does not invent readings or rearm", () => {
  const f = fixture(); f.set(100_000); assert.ok(observation(f));
  for (const n of [null, undefined, NaN, Infinity, -1]) { f.set(n, null); assert.equal(observation(f), undefined); }
  f.set(null, null, 2_000_000); assert.equal(observation(f), undefined);
  f.set(100_000); assert.equal(observation(f), undefined);
  f.set(150_000); assert.ok(observation(f));
});
test("successful resets rearm; failed compaction and request errors do not", () => {
  const f = fixture(); f.set(100_000); assert.ok(observation(f));
  for (const event of ["session_before_compact", "session_compact_failed", "message_end", "message_end"]) {
    f.emit(event, { aborted: true, message: { role: "assistant", stopReason: "error" } });
    assert.equal(observation(f), undefined);
  }
  for (const event of ["session_compact", "session_start", "session_tree"]) {
    f.emit(event); assert.ok(observation(f)); assert.equal(observation(f), undefined);
  }
  f.emit("session_compact"); f.emit("message_end", { message: { role: "assistant", stopReason: "aborted" } });
  assert.ok(observation(f));
});
test("at-most-once attempt across success, error and abort; reset wins over late responses", () => {
  for (const stopReason of ["stop", "error", "aborted"]) {
    const f = fixture(); f.set(100_000); assert.ok(observation(f));
    f.emit("message_end", { message: { role: "assistant", stopReason } });
    assert.equal(observation(f), undefined); // including a retry after failure
    f.set(150_000); assert.ok(observation(f));
    f.emit("session_tree");
    f.emit("message_end", { message: { role: "assistant", stopReason } });
    assert.ok(observation(f)); // late response cannot consume the reset
  }
});
test("provider, model and effective window identity rearm", () => {
  const f = fixture(); f.set(100_000); assert.ok(observation(f));
  f.ctx.model = { ...f.ctx.model }; assert.equal(observation(f), undefined);
  f.ctx.model.id = "other"; assert.ok(observation(f));
  f.ctx.model.provider = "other"; assert.ok(observation(f));
  f.set(100_000, 5, 2_000_000); assert.ok(observation(f));
});
test("missing identity components retain high water and real changes rearm", () => {
  const f = fixture(); f.set(100_000); assert.ok(observation(f));
  const original = { ...f.ctx.model };
  for (const model of [undefined, { ...original, provider: undefined }, { ...original, id: undefined }, original]) {
    f.ctx.model = model; assert.equal(observation(f), undefined);
  }
  f.ctx.model = undefined; f.set(100_000, 5, 2_000_000); assert.ok(observation(f));
  f.ctx.model = original; assert.equal(observation(f), undefined);
  f.ctx.model = { ...original, id: "new" }; assert.ok(observation(f));
});
test("pressure derives from tokens and window despite malformed reported percent", async () => {
  const f = fixture();
  for (const reported of [-1, 0, 80, NaN, Infinity, null]) {
    f.set(900_000, reported);
    const status = await f.status(); assert.equal(status.percent, 90); assert.equal(status.pressure, "critical");
    assert.match(observation(f).content, /Context pressure: 90%/);
  }
});
test("pressure repeats at 80 and 90, combined observation has one usage", () => {
  const f = fixture(); f.set(800_000, 80); const first = observation(f);
  assert.match(first.content, /Context usage: 800,000/); assert.match(first.content, /Context pressure: 80%/);
  assert.equal((first.content.match(/800,000/g) ?? []).length, 1);
  assert.match(observation(f).content, /Compaction reminder/);
  f.set(900_000, 90); assert.match(observation(f).content, /Urgent compaction reminder/);
  assert.match(observation(f).content, /Urgent compaction reminder/);
  f.set(790_000, 79); assert.equal(observation(f), undefined);
  for (const [n, expected] of [[79.9,75],[80,80],[90,90],[95,95],[Infinity,null]]) assert.equal(pressureThresholdForPercent(n), expected);
});
test("temporary messages preserve ordering, tool pairs and never accumulate", () => {
  const f = fixture(); f.set(800_000, 80);
  const history = Object.freeze([{ role: "assistant", content: [{ type: "toolCall", id: "a" }] },
    { role: "toolResult", toolCallId: "a", content: [] }, { role: "custom", customType: "other", content: "keep" },
    { role: "custom", customType: RUNTIME_PRESSURE_TYPE, content: "unowned same-type message", details: { owner: "another-extension" } }]);
  const first = f.request(history), second = f.request(first);
  assert.deepEqual(second.slice(0, history.length), history); assert.equal(second.length, history.length + 1);
  f.set(0); assert.deepEqual(f.request(second), history); assert.deepEqual(f.sent, []);
});
test("manual snapshot is context-only and does not consume observation", async () => {
  const f = fixture(); f.set(302_000); const s = await f.status(); await f.command();
  assert.equal(s.tokens, 302_000); assert.equal(s.provider, "openai"); assert.equal(s.model, "test");
  assert.equal("elapsedMs" in s, false); assert.equal("modelUsage" in s, false); assert.ok(observation(f));
});
