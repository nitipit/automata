import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const root = process.env.CONTEXT_TEST_ROOT;
const { default: register, COMPACTION_PLAN_TYPE } = await import(pathToFileURL(join(root, "context-status.ts")));
const native = join(root, "node_modules/@earendil-works/pi-coding-agent/dist/core");
const { ExtensionRunner } = await import(pathToFileURL(join(native, "extensions/runner.js")));
const { convertToLlm } = await import(pathToFileURL(join(native, "messages.js")));
const owner = "automata-context-status:request-local";

function fixture() {
  const handlers = new Map();
  register({
    on(name, handler) { handlers.set(name, [...handlers.get(name) ?? [], handler]); },
    registerTool() {}, registerCommand() {},
    sendMessage() { assert.fail("must not steer, persist, or wake the agent"); },
    appendEntry() { assert.fail("must not mutate session history"); },
  });
  let tokens = 0;
  const ctx = {
    model: { provider: "openai", id: "gpt-6.1-sol", contextWindow: 1_050_000 },
    getContextUsage: () => ({ tokens, percent: 0, contextWindow: 1_050_000 }),
  };
  const runner = { createContext: () => ctx, extensions: [{ path: "offline-context-status", handlers }],
    emitError: error => assert.fail(JSON.stringify(error)) };
  return { ctx, handlers, runner, set: value => { tokens = value; },
    transform: messages => ExtensionRunner.prototype.emitContext.call(runner, messages) };
}
const history = [
  { role: "system", content: "Keep original instructions.", timestamp: 0,
    toolsAdded: [{ name: "read", description: "Offline read", parameters: { type: "object", properties: {} } }] },
  { role: "user", content: "Do the scoped task", timestamp: 1 },
  { role: "assistant", content: [{ type: "toolCall", id: "read-1", name: "read", arguments: {} }] },
  { role: "toolResult", toolCallId: "read-1", toolName: "read", content: [{ type: "text", text: "file evidence" }], timestamp: 2 },
];
const plans = messages => messages.filter(message => message.customType === COMPACTION_PLAN_TYPE && message.details?.owner === owner);

test("activity remains on-demand without native nextTurn messages or wake-ups", async (t) => {
  const { default: registerActivity } = await import(pathToFileURL(join(root, "activity-usage.ts")));
  const { AgentSession } = await import(pathToFileURL(join(native, "agent-session.js")));
  let now = 1_000_000; t.mock.method(Date, "now", () => now);
  const handlers = new Map(); let tool; let wakes = 0;
  const session = {
    _pendingNextTurnMessages: [], _baseSystemPromptOptions: { selectedTools: [] },
    _findLastAssistantMessage: () => undefined,
    _extensionRunner: { emitBeforeAgentStart: async (_trigger, options) => ({ systemPromptOptions: options, messages: [] }) },
    getActiveToolNames: () => [],
    _normalizePromptImages: async () => ({ hints: [], images: [] }),
    _preparePromptAndToolLoadout: () => undefined,
    _startRun: () => { wakes++; },
  };
  registerActivity({ on: (name, fn) => handlers.set(name, fn), registerCommand() {},
    registerTool: value => { tool = value; },
    sendMessage: (message, options) => AgentSession.prototype.sendCustomMessage.call(session, message, options) });
  handlers.get("message_start")({ message: { role: "user", timestamp: now } });
  now += 600_000;
  for (const event of ["turn_end", "agent_end", "agent_settled"]) handlers.get(event)?.();
  assert.equal(wakes, 0); assert.equal(session._pendingNextTurnMessages.length, 0);
  assert.equal((await tool.execute()).details.elapsedMs, 600_000);
  now += 1000;
  const messages = await AgentSession.prototype._prepareRun.call(session,
    { messageType: "user", prompt: "new input", images: [] });
  assert.deepEqual(messages.map(m => m.role), ["user"]);
  handlers.get("message_start")({ message: messages[0] });
  assert.equal((await tool.execute()).details.inputAnchorTimestamp, now);
  assert.equal(convertToLlm(messages).length, 1);
  assert.equal(wakes, 0);
});

test("native request conversion delivers one planning notice and preserves tool pairs", async () => {
  const f = fixture(), original = structuredClone(history);
  f.set(400_000);
  const transformed = await f.transform(history);
  assert.deepEqual(transformed.slice(0, history.length), history);
  assert.deepEqual(history, original);
  assert.equal(plans(transformed).length, 1);
  const llm = convertToLlm(transformed);
  assert.deepEqual(llm.filter(m => ["assistant", "toolResult"].includes(m.role)), history.slice(2));
  const delivered = llm.filter(m => m.role === "user" && Array.isArray(m.content) &&
    m.content.some(block => block.type === "text" && block.text.includes(plans(transformed)[0].content)));
  assert.equal(delivered.length, 1);
  for (let n = 0; n < 3; n++) {
    const repeated = await f.transform(transformed);
    assert.equal(plans(repeated).length, 1);
    assert.equal(repeated.length, transformed.length);
  }
});

test("native transforms react to current usage, model switches, and post-compaction unknown usage", async () => {
  const f = fixture();
  for (const tokens of [50_000, 100_000, 399_999, null]) {
    f.set(tokens); assert.equal(plans(await f.transform(history)).length, 0);
  }
  f.set(400_000); assert.equal(plans(await f.transform(history)).length, 1);
  f.ctx.model.id = "gpt-6-luna"; assert.equal(plans(await f.transform(history)).length, 0);
  f.set(800_000); assert.equal(plans(await f.transform(history)).length, 1);
  f.set(null); assert.equal(plans(await f.transform(history)).length, 0);
  f.set(20_000); assert.equal(plans(await f.transform(history)).length, 0);
  // No compaction hooks exist: the native threshold/manual/overflow paths are untouched.
  assert.deepEqual([...f.handlers.keys()], ["context"]);
});

test("native runner preserves third-party same-type messages in either extension order", async () => {
  for (const thirdPartyFirst of [true, false]) {
    const f = fixture(); f.set(400_000);
    const other = { path: "other", handlers: new Map([["context", [event => ({
      messages: [...event.messages, { role: "custom", customType: COMPACTION_PLAN_TYPE,
        content: "third-party", timestamp: 5 }],
    })]]]) };
    const own = f.runner.extensions[0];
    f.runner.extensions = thirdPartyFirst ? [other, own] : [own, other];
    const transformed = await f.transform(history);
    assert.equal(transformed.filter(m => m.content === "third-party").length, 1);
    assert.equal(plans(transformed).length, 1);
    assert.deepEqual(transformed.filter(m => ["assistant", "toolResult"].includes(m.role)), history.slice(2));
  }
});

test("native transform strips only owned current and legacy notices, even below threshold", async () => {
  const f = fixture();
  const unrelated = { role: "custom", customType: COMPACTION_PLAN_TYPE, content: "keep", timestamp: 3 };
  const stale = { role: "custom", customType: COMPACTION_PLAN_TYPE, content: "old plan", timestamp: 4, details: { owner } };
  const legacy = { ...stale, customType: "automata-context-pressure" };
  const input = [...history, stale, unrelated, legacy, { ...stale }];
  const original = structuredClone(input);
  for (const tokens of [400_000, 900_000, 399_999, null]) {
    f.set(tokens);
    const result = await f.transform(input);
    assert.deepEqual(result.slice(0, history.length + 1), [...history, unrelated]);
    assert.equal(plans(result).length, tokens !== null && tokens >= 400_000 ? 1 : 0);
    assert.deepEqual(input, original);
  }
});
