import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const {
  default: register, pressureThresholdForPercent, RUNTIME_PRESSURE_TYPE,
} = await import(pathToFileURL(
  join(process.env.CONTEXT_TEST_ROOT, "context-status.ts"),
));

function fixture() {
  const handlers = new Map();
  const tools = new Map();
  const commands = new Map();
  const notifications = [];
  const sent = [];
  register({
    on(name, handler) { handlers.set(name, handler); },
    registerCommand(name, command) { commands.set(name, command); },
    registerTool(tool) { tools.set(tool.name, tool); },
    sendMessage(...args) { sent.push(args); },
    appendEntry() { assert.fail("Temporary timestamps must not be persisted"); },
  });
  const ctx = {
    hasUI: true,
    ui: { notify(...args) { notifications.push(args); } },
    model: { provider: "offline", id: "test", contextWindow: 10000 },
    getContextUsage: () => ({ tokens: 100, contextWindow: 10000, percent: 1 }),
  };
  return {
    ctx, handlers, sent, notifications,
    commandStatus: () => commands.get("context-status").handler("", ctx),
    setPercent(percent, contextWindow = 10000) {
      ctx.model.contextWindow = contextWindow;
      ctx.getContextUsage = () => ({
        tokens: percent === null ? null : percent * contextWindow / 100,
        contextWindow, percent,
      });
    },
    emit: (name, event = {}) => handlers.get(name)?.(event, ctx),
    status: async () => (await tools.get("context_status").execute(
      "test", {}, undefined, undefined, ctx,
    )).details,
  };
}

const start = Date.parse("2026-09-09T12:00:00.000+07:00");

test("context status no longer injects a changing clock", (t) => {
  let now = start;
  t.mock.method(Date, "now", () => now);
  const f = fixture();
  const user = Object.freeze({ role: "user", content: "hello", timestamp: start });
  const history = Object.freeze([user]);

  for (let i = 0; i < 3; i++) {
    now = start + i * 1000;
    const { messages } = f.emit("context", { messages: history });
    assert.deepEqual(messages, history);
    assert.equal(messages[0], user);
  }
  assert.deepEqual(history, [user]);
  assert.deepEqual(f.sent, []); // No sendMessage or extra agent turn.
});

test("context status preserves tool/message order without a clock suffix", (t) => {
  t.mock.method(Date, "now", () => start);
  const f = fixture();
  const history = [
    { role: "assistant", content: [{ type: "toolCall", id: "a", name: "read", arguments: {} }] },
    { role: "toolResult", toolCallId: "a", toolName: "read", content: [] },
    { role: "custom", customType: "automata-context-awareness", content: "pressure evidence" },
  ];
  const first = f.emit("context", { messages: history }).messages;
  const second = f.emit("context", { messages: first }).messages;
  assert.equal(second.length, history.length);
  assert.deepEqual(second, history);
  assert.equal(first.length, history.length);
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

function pressure(f, history = []) {
  return f.emit("context", { messages: history }).messages.filter(
    (message) => message.customType === RUNTIME_PRESSURE_TYPE,
  );
}

function threshold(f) {
  const signals = pressure(f);
  assert.ok(signals.length <= 1);
  return signals[0]?.details.observations.pressureThreshold;
}

test("thresholds are exact, bounded, and reject unknown/non-finite usage", () => {
  for (const [percent, expected] of [
    [undefined, null], [null, null], [NaN, null], [Infinity, null], [-1, null],
    [0, null], [49.999, null], [50, 50], [74.999, 50], [75, 75], [79.999, 75],
    [80, 80], [85, 85], [89.999, 85], [90, 90], [95, 95], [100, 95], [120, 95],
  ]) assert.equal(pressureThresholdForPercent(percent), expected, String(percent));
});

test("every request at 80+ carries one measured reminder, with urgency at 90+", () => {
  const f = fixture();
  f.emit("message_start", { message: { role: "user", timestamp: start } });
  f.emit("agent_start");
  for (const value of [50, 75, 79.9, 80, 80, 85, 85, 90, 95, 95]) {
    f.setPercent(value);
    f.emit("turn_end");
    assert.deepEqual(f.sent, []);
    if (value < 80) {
      assert.deepEqual(pressure(f), []);
      continue;
    }
    for (let request = 0; request < 3; request++) {
      const signals = pressure(f);
      assert.equal(signals.length, 1);
      const [signal] = signals;
      assert.equal(signal.details.observations.pressureThreshold, value);
      assert.match(signal.content, new RegExp(`Context pressure: ${value}%`));
      assert.doesNotMatch(signal.content, /reached|crossed|Elapsed:|Model:/);
      assert.equal(signal.display, false);
      assert.equal(signal.details.kind, "pressure-reminder");
      if (value < 90) {
        assert.match(signal.content, /next stable boundary/);
        assert.doesNotMatch(signal.content, /Urgent/);
      } else assert.match(signal.content, /Urgent compaction reminder/);
    }
  }
  assert.deepEqual(f.sent, []); // No steering, wakeup or end-of-run dependency.
});

test("fluctuations use current measured pressure, with no backlog or hysteresis", () => {
  const f = fixture();
  f.setPercent(89);
  assert.equal(threshold(f), 85);
  for (const value of [89.9, 84, 30, 50, 75, 79.9, 80, 85, 89]) {
    f.setPercent(value);
    assert.equal(threshold(f), value < 80 ? undefined : pressureThresholdForPercent(value));
  }
  f.setPercent(110);
  assert.equal(threshold(f), 95);
  assert.equal(threshold(f), 95);
});

test("new user inputs reset telemetry without suppressing recurring pressure", async (t) => {
  t.mock.method(Date, "now", () => start);
  const f = fixture();
  f.setPercent(80);
  assert.equal(threshold(f), 80);
  for (const content of ["human input", "coordinator input"]) {
    f.emit("message_start", { message: { role: "user", timestamp: start, content } });
    f.emit("agent_start");
    assert.equal(threshold(f), 80);
    assert.equal((await f.status()).inputAnchorTimestamp, start);
  }
  f.setPercent(85);
  assert.equal(threshold(f), 85);
});

test("unknown usage never warns or invents a reading, and valid usage resumes advice", () => {
  const f = fixture();
  f.setPercent(null);
  assert.equal(threshold(f), undefined);
  f.ctx.getContextUsage = () => ({ tokens: null, percent: 95, contextWindow: 10000 });
  assert.equal(threshold(f), undefined);
  f.setPercent(80);
  assert.equal(threshold(f), 80);
  f.setPercent(null);
  assert.equal(threshold(f), undefined);
  f.setPercent(80);
  assert.equal(threshold(f), 80);
  for (const value of [undefined, NaN, Infinity]) {
    f.ctx.getContextUsage = () => ({ tokens: null, percent: value, contextWindow: 10000 });
    assert.equal(threshold(f), undefined);
  }
  f.ctx.getContextUsage = () => ({ tokens: 8500, contextWindow: 10000 });
  assert.equal(threshold(f), 85); // Supported token/window fallback.
});

test("compaction lifecycle preserves time/usage telemetry and reads current pressure", async (t) => {
  let now = start;
  t.mock.method(Date, "now", () => now);
  const f = fixture();
  f.emit("message_start", { message: { role: "user", timestamp: start } });
  const assistant = { role: "assistant", timestamp: start, usage: { input: 100, output: 20 } };
  f.emit("message_end", { message: assistant });
  f.emit("message_end", { message: assistant }); // Provider usage counted once.
  f.emit("message_end", { message: { role: "toolResult", usage: { input: 999 } } });
  f.setPercent(85);
  assert.equal(threshold(f), 85);
  f.emit("session_before_compact");
  f.emit("session_compact_failed", { aborted: true });
  assert.equal(threshold(f), 85);
  now += 1000;
  f.emit("session_compact");
  f.setPercent(null); // Pi reports unknown until a post-compaction response.
  assert.equal(threshold(f), undefined);
  f.setPercent(76);
  assert.equal(threshold(f), undefined);
  f.setPercent(85);
  assert.equal(threshold(f), 85);
  const status = await f.status();
  assert.equal(status.inputAnchorTimestamp, start);
  assert.equal(status.elapsedMs, 1000);
  assert.equal(status.modelUsage.input, 100);
  assert.equal(status.modelUsage.output, 20);
  assert.equal(status.modelUsage.totalTokens, 120);
});

test("effective model/provider/window changes always use fresh readings", () => {
  const f = fixture();
  f.setPercent(80);
  assert.equal(threshold(f), 80);
  f.ctx.model = { ...f.ctx.model };
  assert.equal(threshold(f), 80);
  f.ctx.model.id = "other";
  assert.equal(threshold(f), 80);
  f.ctx.model.provider = "other-provider";
  assert.equal(threshold(f), 80);
  f.setPercent(80, 20000);
  assert.equal(threshold(f), 80);
  f.setPercent(null, 30000);
  assert.equal(threshold(f), undefined);
  f.setPercent(80, 30000);
  assert.equal(threshold(f), 80);
});

test("session navigation and compaction do not suppress repeated current pressure", () => {
  const f = fixture();
  f.setPercent(95);
  assert.equal(threshold(f), 95);
  for (const event of ["session_start", "session_tree"]) {
    f.emit(event);
    assert.equal(threshold(f), 95);
  }
  f.emit("session_compact_failed", { errorMessage: "offline failure" });
  assert.equal(threshold(f), 95);
  f.emit("session_compact");
  assert.equal(threshold(f), 95); // Compacted context may still be large.
});

test("manual diagnostics and settlement do not consume or queue pressure reminders", async () => {
  const f = fixture();
  f.setPercent(80);
  assert.equal((await f.status()).percent, 80);
  await f.commandStatus();
  assert.match(f.notifications[0][0], /Usage: 8,000 \/ 10,000 tokens \(80%\)/);
  assert.equal(f.notifications[0][1], "info");
  assert.equal(threshold(f), 80);
  f.emit("turn_end");
  f.emit("agent_end");
  f.emit("agent_settled");
  assert.deepEqual(f.sent, []);
  assert.equal(threshold(f), 80);
  f.setPercent(75);
  assert.equal((await f.status()).pressure, "high"); // Independent diagnostic bands stay useful.
  assert.equal(threshold(f), undefined);
});

test("ephemeral reminders preserve history and tool pairs and never accumulate", () => {
  const f = fixture();
  const history = Object.freeze([
    Object.freeze({ role: "assistant", content: [{ type: "toolCall", id: "a", name: "read", arguments: {} }] }),
    Object.freeze({ role: "toolResult", toolCallId: "a", toolName: "read", content: [] }),
    Object.freeze({ role: "custom", customType: "another-extension", content: "keep me" }),
  ]);
  f.setPercent(80);
  const first = f.emit("context", { messages: history }).messages;
  assert.deepEqual(first.slice(0, history.length), history);
  assert.equal(first.length, history.length + 1);
  const second = f.emit("context", { messages: first }).messages;
  assert.deepEqual(second.slice(0, history.length), history);
  assert.equal(second.length, history.length + 1);
  assert.equal(second.filter((message) => message.customType === RUNTIME_PRESSURE_TYPE).length, 1);
  assert.notEqual(second.at(-1), first.at(-1));
  for (const value of [79.9, null]) {
    f.setPercent(value);
    const stale = Object.freeze([...second, Object.freeze({
      role: "custom", customType: RUNTIME_PRESSURE_TYPE, content: "old pressure", timestamp: 0,
    })]);
    assert.deepEqual(f.emit("context", { messages: stale }).messages, history);
    assert.equal(stale.length, history.length + 2);
  }
  assert.equal(history.length, 3);
  assert.deepEqual(f.sent, []);
});

test("time observations still coalesce at settlement and do not duplicate pressure", (t) => {
  let now = start;
  t.mock.method(Date, "now", () => now);
  const f = fixture();
  f.emit("message_start", { message: { role: "user", timestamp: start } });
  now += 10 * 60 * 1000;
  f.emit("turn_end");
  now += 21 * 60 * 1000;
  f.setPercent(92);
  f.emit("agent_end");
  assert.equal(threshold(f), 90);
  f.emit("agent_settled");
  assert.equal(f.sent.length, 1);
  assert.deepEqual(f.sent[0][0].details.observations, { timeThreshold: 3 });
  assert.doesNotMatch(f.sent[0][0].content, /compaction reminder/i);
  f.emit("agent_settled");
  assert.equal(f.sent.length, 1);
  assert.equal(threshold(f), 90);
});
