import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { default: register, COMPACTION_PLAN_TYPE } = await import(pathToFileURL(
  join(process.env.CONTEXT_TEST_ROOT, "context-status.ts"),
));
const owner = "automata-context-status:request-local";
function fixture(id = "gpt-6.1-sol", provider = "openai") {
  const handlers = new Map(), tools = new Map(), commands = new Map(), notices = [];
  register({ on: (name, fn) => handlers.set(name, fn), registerTool: tool => tools.set(tool.name, tool),
    registerCommand: (name, command) => commands.set(name, command),
    sendMessage: () => assert.fail("no wake-up or queued message"),
    appendEntry: () => assert.fail("no persistence"),
    getSettings: () => assert.fail("no settings access or mutation") });
  let usage = { tokens: 0, contextWindow: 1_050_000, percent: 0 };
  const ctx = { model: { provider, id, contextWindow: 1_050_000 },
    getContextUsage: () => usage, hasUI: true,
    compact: () => assert.fail("never compact automatically"), ui: { notify: (...args) => notices.push(args) } };
  const emit = (name, event = {}) => handlers.get(name)?.(event, ctx);
  return { ctx, notices, handlers, emit,
    set: (tokens, contextWindow = 1_050_000, percent = 0) => { usage = { tokens, contextWindow, percent }; },
    setUsage: value => { usage = value; },
    request: (messages = []) => emit("context", { messages }).messages,
    status: async () => (await tools.get("context_status").execute("", {}, undefined, undefined, ctx)),
    command: () => commands.get("context-status").handler("", ctx) };
}
function plan(f) { return f.request().find(m => m.customType === COMPACTION_PLAN_TYPE); }

for (const [model, threshold] of [["gpt-6.2-astra", 200_000], ["gpt-6.2-sol", 400_000],
  ["gpt-6-astra", 200_000], ["gpt-6.1-sol", 400_000],
  ["gpt-6.1-terra", 400_000], ["gpt-6-luna", 800_000]]) {
  test(`${model}: below, equal, above, and repeated threshold requests`, async () => {
    const f = fixture(model);
    for (const tokens of [0, 50_000, 100_000, threshold - 1]) {
      f.set(tokens); assert.equal(plan(f), undefined);
    }
    for (const tokens of [threshold, threshold + 1, threshold + 50_000]) {
      f.set(tokens);
      const first = plan(f), second = plan(f);
      assert.equal(first.details.status.tokens, tokens);
      assert.equal(first.details.status.planningThresholdTokens, threshold);
      assert.equal(first.details.status.planningRequired, true);
      assert.deepEqual(second.details, first.details);
      assert.equal(f.request().length, 1);
    }
    f.set(threshold - 1); assert.equal(plan(f), undefined);
    const status = (await f.status()).details;
    assert.equal(status.planningRequired, false);
    assert.equal(status.planningThresholdTokens, threshold);
  });
}

test("thresholds are used-token counts, independent of reported percentage or window", async () => {
  const f = fixture();
  for (const window of [500_000, 1_050_000, 2_000_000, null]) {
    for (const percent of [0, 90, 99, NaN, Infinity, null]) {
      f.set(399_999, window, percent); assert.equal(plan(f), undefined);
      f.set(400_000, window, percent); assert.ok(plan(f));
    }
  }
  assert.equal((await f.status()).details.contextWindow, 1_050_000);
});

test("unknown and malformed usage does not invent a trigger", async () => {
  const f = fixture();
  for (const tokens of [null, undefined, NaN, Infinity, -1]) {
    f.set(tokens, 1_050_000, 99); assert.equal(plan(f), undefined);
    const s = (await f.status()).details;
    assert.equal(s.tokens, null); assert.equal(s.planningRequired, false);
  }
  f.setUsage(undefined); assert.equal(plan(f), undefined);
  f.set(400_000); assert.ok(plan(f));
});

test("model and provider switches use exact current identity, no inferred aliases", async () => {
  const f = fixture(); f.set(400_000); assert.ok(plan(f));
  f.ctx.model.id = "gpt-6-luna"; assert.equal(plan(f), undefined);
  f.ctx.model.id = "gpt-6-astra"; assert.ok(plan(f));
  for (const model of [undefined, { id: "gpt-6-astra" }, { provider: "other", id: "gpt-6-astra" },
    { provider: "openai", id: "unconfigured" }, { provider: "openai", id: "gpt-6-astra-snapshot" }]) {
    f.ctx.model = model; f.set(900_000); assert.equal(plan(f), undefined);
    assert.equal((await f.status()).details.planningThresholdTokens, null);
  }
});

test("confirmed compaction follows fresh usage; failure never runs or retries compaction", () => {
  const f = fixture(); f.set(400_000); assert.ok(plan(f));
  f.emit("session_compact_failed", { aborted: true }); assert.ok(plan(f));
  f.emit("session_compact"); f.set(null); assert.equal(plan(f), undefined);
  f.set(50_000); assert.equal(plan(f), undefined);
  f.set(400_000); assert.ok(plan(f));
  // The extension owns only request transformation, never any compaction lifecycle gate.
  assert.deepEqual([...f.handlers.keys()], ["context"]);
});

test("temporary messages preserve ordering, tool pairs, and other owners", () => {
  const f = fixture(); f.set(400_000);
  const history = Object.freeze([
    { role: "assistant", content: [{ type: "toolCall", id: "a" }] },
    { role: "toolResult", toolCallId: "a", content: [] },
    { role: "custom", customType: "other", content: "keep" },
    { role: "custom", customType: COMPACTION_PLAN_TYPE, content: "unowned" },
    { role: "custom", customType: "automata-context-pressure", content: "another owner", details: { owner: "other" } },
  ]);
  const first = f.request(history), second = f.request(first);
  assert.deepEqual(second.slice(0, history.length), history);
  assert.equal(second.length, history.length + 1);
  const stale = { role: "custom", customType: "automata-context-pressure", content: "legacy", details: { owner } };
  f.set(0); assert.deepEqual(f.request([...second, stale, stale]), history);
  f.set(null); assert.deepEqual(f.request(second), history);
  assert.equal(history.length, 5);
});

test("manual snapshot and command are context-only with no extra activity state", async () => {
  const f = fixture(); f.set(400_000);
  const result = await f.status(); await f.command();
  assert.equal(result.details.tokens, 400_000);
  assert.equal(result.details.provider, "openai");
  for (const field of ["elapsedMs", "modelUsage", "percent", "pressure"]) {
    assert.equal(field in result.details, false);
  }
  assert.equal(f.notices[0][0], result.content[0].text);
  assert.ok(plan(f));
});
