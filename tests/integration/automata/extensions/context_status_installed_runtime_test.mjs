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
  const ctx = {
    model: { provider: "offline", id: "test", contextWindow: 10000 },
    getContextUsage: () => ({
      tokens: percent === null ? null : percent * 100,
      percent, contextWindow: 10000,
    }),
  };
  const runner = {
    createContext: () => ctx,
    extensions: [{ path: "offline-context-status", handlers }],
    emitError(error) { assert.fail(JSON.stringify(error)); },
  };
  return {
    setPercent(value) { percent = value; },
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
  assert.match(warnings[0].content[0].text, /80% threshold/);
  assert.match(warnings[0].content[0].text, /existing compaction policy/);
  assert.equal(reminders(await f.transform(history)).length, 0);
  assert.deepEqual(history, original);
});

test("native transformation observes tool-result growth without waiting for settlement", async () => {
  const f = fixture();
  f.setPercent(74);
  assert.equal(reminders(await f.transform(history))[0].details.observations.pressureThreshold, 50);
  for (const percent of [75, 80, 85, 90, 95]) {
    f.setPercent(percent);
    const request = await f.transform([...history, {
      role: "custom", customType: "other-runtime-evidence", content: "preserve this", timestamp: 3,
    }]);
    assert.equal(reminders(request)[0].details.observations.pressureThreshold, percent);
    assert.equal(request.filter((message) => message.customType === "other-runtime-evidence").length, 1);
  }
  f.emit("session_compact_failed");
  assert.equal(reminders(await f.transform(history)).length, 0);
  f.emit("session_compact");
  f.setPercent(null);
  assert.equal(reminders(await f.transform(history)).length, 0);
  f.setPercent(76);
  assert.equal(reminders(await f.transform(history))[0].details.observations.pressureThreshold, 75);
});
