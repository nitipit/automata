import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { default: register } = await import(pathToFileURL(
  join(process.env.CONTEXT_TEST_ROOT, "context-status.ts"),
));

function fixture() {
  const handlers = new Map();
  const tools = new Map();
  const sent = [];
  register({
    on(name, handler) { handlers.set(name, handler); },
    registerCommand() {},
    registerTool(tool) { tools.set(tool.name, tool); },
    sendMessage(...args) { sent.push(args); },
    appendEntry() { assert.fail("Temporary timestamps must not be persisted"); },
  });
  const ctx = {
    getContextUsage: () => ({ tokens: 100, contextWindow: 10000, percent: 1 }),
  };
  return {
    sent,
    emit: (name, event = {}) => handlers.get(name)(event, ctx),
    status: async () => (await tools.get("context_status").execute(
      "test", {}, undefined, undefined, ctx,
    )).details,
  };
}

const start = Date.parse("2026-09-09T12:00:00.000+07:00");

test("each outgoing copy gets a fresh local timestamp without changing history", (t) => {
  let now = start;
  t.mock.method(Date, "now", () => now);
  const f = fixture();
  const user = Object.freeze({ role: "user", content: "hello", timestamp: start });
  const history = Object.freeze([user]);

  for (let i = 0; i < 3; i++) {
    now = start + i * 1000;
    const { messages } = f.emit("context", { messages: history });
    assert.equal(messages.length, 2);
    assert.equal(messages[0], user);
    const clock = messages.at(-1);
    assert.equal(clock.role, "custom");
    assert.equal(clock.customType, "automata-runtime-time");
    assert.equal(clock.display, false);
    assert.equal(clock.timestamp, now);
    assert.equal(clock.content, `Runtime local time: 2026-09-09T12:00:0${i}.000+07:00`);
  }
  assert.deepEqual(history, [user]);
  assert.deepEqual(f.sent, []); // No sendMessage or extra agent turn.
});

test("refresh replaces only its own snapshot and preserves tool/message order", (t) => {
  t.mock.method(Date, "now", () => start);
  const f = fixture();
  const history = [
    { role: "assistant", content: [{ type: "toolCall", id: "a", name: "read", arguments: {} }] },
    { role: "toolResult", toolCallId: "a", toolName: "read", content: [] },
    { role: "custom", customType: "automata-context-awareness", content: "pressure evidence" },
  ];
  const first = f.emit("context", { messages: history }).messages;
  const second = f.emit("context", { messages: first }).messages;
  assert.equal(second.length, history.length + 1);
  assert.deepEqual(second.slice(0, -1), history);
  assert.equal(first.length, history.length + 1);
  assert.deepEqual(f.sent, []);
});

test("snapshot does not create or reset telemetry; existing threshold delivery remains", async (t) => {
  let now = start;
  t.mock.method(Date, "now", () => now);
  const f = fixture();
  f.emit("context", { messages: [] });
  assert.equal((await f.status()).inputAnchorTimestamp, undefined);

  f.emit("message_start", { message: { role: "user", timestamp: start } });
  const before = await f.status();
  now += 10 * 60 * 1000;
  f.emit("context", { messages: [] });
  const after = await f.status();
  assert.equal(after.inputAnchorTimestamp, start);
  assert.equal(after.elapsedMs, 10 * 60 * 1000);
  assert.deepEqual(after.modelUsage, before.modelUsage);
  assert.deepEqual(f.sent, []);

  f.emit("agent_settled");
  assert.equal(f.sent.length, 1);
  const [signal, options] = f.sent[0];
  assert.equal(signal.customType, "automata-context-awareness");
  assert.equal(signal.details.observations.timeThreshold, 1);
  assert.deepEqual(options, { deliverAs: "nextTurn" });
});
