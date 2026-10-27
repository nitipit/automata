import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const root = process.env.CONTEXT_TEST_ROOT;
const { default: register, RUNTIME_PRESSURE_TYPE } = await import(pathToFileURL(
  join(root, "context-status.ts"),
));
const native = join(root, "node_modules/@earendil-works/pi-coding-agent/dist/core");
const { ExtensionRunner } = await import(pathToFileURL(join(native, "extensions/runner.js")));
const { convertToLlm } = await import(pathToFileURL(join(native, "messages.js")));

function fixture() {
  const handlers = new Map();
  register({
    on(name, handler) {
      const list = handlers.get(name) ?? [];
      list.push(handler);
      handlers.set(name, list);
    },
    registerTool() {},
    registerCommand() {},
    sendMessage() { assert.fail("Pressure must not steer, persist, or wake the agent"); },
    appendEntry() { assert.fail("Pressure must not mutate session history"); },
  });
  let percent = 74;
  let window = 10000;
  const ctx = {
    model: { provider: "offline", id: "test", contextWindow: 10000 },
    getContextUsage: () => ({
      tokens: percent === null ? null : percent * window / 100,
      percent, contextWindow: window,
    }),
  };
  const runner = {
    createContext: () => ctx,
    extensions: [{ path: "offline-context-status", handlers }],
    emitError(error) { assert.fail(JSON.stringify(error)); },
  };
  return {
    setPercent(value) { percent = value; },
    setWindow(value) { window = value; },
    emit(name) { for (const handler of handlers.get(name) ?? []) handler({}, ctx); },
    transform: (messages) => ExtensionRunner.prototype.emitContext.call(runner, messages),
  };
}

const history = [
  {
    role: "system", content: "Keep the original system instructions.", timestamp: 0,
    toolsAdded: [{ name: "read", description: "Offline read", parameters: { type: "object", properties: {} } }],
  },
  { role: "user", content: "Do the scoped task", timestamp: 1 },
  { role: "assistant", content: [{ type: "toolCall", id: "read-1", name: "read", arguments: {} }] },
  { role: "toolResult", toolCallId: "read-1", toolName: "read", content: [{ type: "text", text: "file evidence" }], timestamp: 2 },
];

function reminders(messages) {
  return messages.filter((message) => message.customType === RUNTIME_PRESSURE_TYPE);
}

test("native nextTurn ordering keeps activity observation historical after a new user input", async (t) => {
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
  now += 600_000; handlers.get("agent_settled")();
  assert.equal(wakes, 0); assert.equal(session._pendingNextTurnMessages.length, 1);
  const observed = now; now += 1000;
  const messages = await AgentSession.prototype._prepareRun.call(session,
    { messageType: "user", prompt: "new input", images: [] });
  assert.deepEqual(messages.map(m => m.role), ["user", "custom"]);
  handlers.get("message_start")({ message: messages[0] });
  assert.equal((await tool.execute()).details.inputAnchorTimestamp, now);
  const llm = convertToLlm(messages);
  assert.match(llm[1].content[0].text, /Historical activity observation/);
  assert.ok(llm[1].content[0].text.includes(new Date(observed).toISOString()));
  assert.ok(llm[1].content[0].text.includes(new Date(1_000_000).toISOString()));
  assert.doesNotMatch(llm[1].content[0].text, /since latest user input/);
  assert.equal(wakes, 0);
});

test("native pre-request transform carries the warning into LLM input without history edits", async () => {
  const f = fixture();
  const original = structuredClone(history);
  f.setPercent(80);
  const transformed = await f.transform(history);
  assert.deepEqual(transformed.slice(0, history.length), history);
  assert.deepEqual(history, original);
  assert.equal(reminders(transformed).length, 1);
  const llm = convertToLlm(transformed);
  // Older Pi converts only conversation messages; newer Pi also carries system state.
  assert.deepEqual(llm.filter((message) => ["assistant", "toolResult"].includes(message.role)),
    history.slice(2)); // Tool-call/result pairing survives in both native layouts.
  const warnings = llm.filter((message) => message.role === "user" && Array.isArray(message.content) &&
    message.content.some((block) => block.type === "text" && block.text.includes("Compaction reminder")));
  assert.equal(warnings.length, 1);
  assert.match(warnings[0].content[0].text, /Context pressure: 80%/);
  assert.doesNotMatch(warnings[0].content[0].text, /reached|crossed|Elapsed:|Model:/);
  assert.match(warnings[0].content[0].text, /existing compaction policy/);
  for (let request = 0; request < 3; request++) {
    const repeated = await f.transform(transformed);
    assert.equal(reminders(repeated).length, 1);
    assert.equal(repeated.length, transformed.length);
    assert.deepEqual(repeated.slice(0, history.length), history);
  }
  assert.deepEqual(history, original);
});

test("native conversion delivers one temporary 50k usage observation without disturbing tool pairs", async () => {
  const f = fixture(); f.setWindow(1_000_000); f.setPercent(30.2);
  const transformed = await f.transform(history);
  assert.equal(reminders(transformed).length, 1);
  const llm = convertToLlm(transformed);
  assert.deepEqual(llm.filter(message => ["assistant", "toolResult"].includes(message.role)), history.slice(2));
  const signal = llm.find(message => message.role === "user" && Array.isArray(message.content) &&
    message.content.some(block => block.type === "text" && block.text.includes("Context usage:")));
  assert.match(signal.content[0].text, /Context usage: 302,000 \/ 1,000,000 tokens\nWorking model: offline\/test/);
  assert.equal(reminders(await f.transform(transformed)).length, 0);
});

test("native transformation observes tool-result growth without waiting for settlement", async () => {
  const f = fixture();
  for (const percent of [50, 74, 75, 79.9, null]) {
    f.setPercent(percent);
    assert.equal(reminders(await f.transform(history)).length, 0);
  }
  for (const percent of [80, 85, 85, 90, 95, 95]) {
    f.setPercent(percent);
    const request = await f.transform([...history, {
      role: "custom", customType: "other-runtime-evidence", content: "preserve this", timestamp: 3,
    }]);
    assert.equal(reminders(request).length, 1);
    assert.equal(reminders(request)[0].details.observations.pressureThreshold, percent);
    assert.equal(reminders(request)[0].content.includes("Urgent"), percent >= 90);
    assert.equal(request.filter((message) => message.customType === "other-runtime-evidence").length, 1);
  }
  f.emit("session_compact_failed");
  assert.equal(reminders(await f.transform(history)).length, 1);
  f.emit("session_compact");
  f.setPercent(null);
  assert.equal(reminders(await f.transform(history)).length, 0);
  f.setPercent(76);
  assert.equal(reminders(await f.transform(history)).length, 0);
  f.setPercent(80);
  assert.equal(reminders(await f.transform(history)).length, 1);
});

test("native runner preserves same-type third-party messages in either extension order", async () => {
  for (const thirdPartyFirst of [true, false]) {
    const handlers = new Map();
    register({ on: (name, fn) => handlers.set(name, [fn]), registerTool() {}, registerCommand() {} });
    const other = { path: "other", handlers: new Map([["context", [event => ({
      messages: [...event.messages, { role: "custom", customType: RUNTIME_PRESSURE_TYPE,
        content: "third-party", timestamp: 5 }],
    })]]]) };
    const own = { path: "context-status", handlers };
    const runner = { createContext: () => ({ model: { provider: "offline", id: "test", contextWindow: 10000 },
      getContextUsage: () => ({ tokens: 8000, contextWindow: 10000, percent: 80 }) }),
      extensions: thirdPartyFirst ? [other, own] : [own, other], emitError: error => assert.fail(JSON.stringify(error)) };
    const transformed = await ExtensionRunner.prototype.emitContext.call(runner, history);
    assert.equal(transformed.filter(m => m.content === "third-party").length, 1);
    assert.deepEqual(transformed.filter(m => ["assistant", "toolResult"].includes(m.role)), history.slice(2));
  }
});

test("native transforms strip every stale pressure entry below 80 or unknown", async () => {
  const f = fixture();
  const unrelated = {
    role: "custom", customType: "other-runtime-evidence", content: "keep this", timestamp: 3,
  };
  const stale = {
    role: "custom", customType: RUNTIME_PRESSURE_TYPE, content: "old pressure", timestamp: 4,
    details: { owner: "automata-context-status:request-local" },
  };
  const unowned = { role: "custom", customType: RUNTIME_PRESSURE_TYPE,
    content: "third-party same-type message", timestamp: 5 };
  const input = [...history, stale, unrelated, unowned, { ...stale }];
  const original = structuredClone(input);
  for (const percent of [85, 95, 79.9, null, 80]) {
    f.setPercent(percent);
    const request = await f.transform(input);
    assert.deepEqual(request.slice(0, history.length + 2), [...history, unrelated, unowned]);
    assert.equal(reminders(request).length, percent !== null && percent >= 80 ? 2 : 1);
    assert.deepEqual(input, original);
  }
});
