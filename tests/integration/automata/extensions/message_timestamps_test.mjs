import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { default: register, annotateMessage } = await import(pathToFileURL(
  join(process.env.CONTEXT_TEST_ROOT, "message-timestamps.ts")));
test("installed Pi runner and model conversion preserve timeline and tool records", {
  skip: !process.env.TIMESTAMP_PI_PACKAGE,
}, async () => {
  const core = join(process.env.TIMESTAMP_PI_PACKAGE, "dist/core");
  const { ExtensionRunner } = await import(pathToFileURL(join(core, "extensions/runner.js")));
  const { convertToLlm } = await import(pathToFileURL(join(core, "messages.js")));
  const handlers = new Map();
  register({ on(name, handler) { handlers.set(name, [handler]); } });
  const runner = { createContext: () => ({}), extensions: [{ path: "timestamps", handlers }],
    emitError(error) { assert.fail(JSON.stringify(error)); } };
  const history = [
    { role: "user", content: "hello", timestamp },
    { role: "assistant", timestamp, content: [{ type: "toolCall", id: "a", name: "read", arguments: {} }] },
    { role: "toolResult", timestamp, toolCallId: "a", toolName: "read", content: [] },
    { role: "custom", timestamp, customType: "browser-context", content: "routed input", display: true },
    { role: "assistant", timestamp, content: [{ type: "text", text: "done" }] },
  ];
  const snapshot = structuredClone(history);
  const output = await ExtensionRunner.prototype.emitContext.call(runner, history);
  const llm = convertToLlm(output);
  assert.match(llm[0].content, /Runtime message timestamp/);
  assert.deepEqual(llm.slice(1, 3), history.slice(1, 3));
  assert.match(llm[3].content[0].text, /Runtime message timestamp/);
  assert.equal(llm[4].content[0].text, label);
  assert.deepEqual(history, snapshot);
  assert.deepEqual(await ExtensionRunner.prototype.emitContext.call(runner, output), output);
});

const timestamp = Date.parse("2026-09-28T09:00:00Z");
const label = "[Runtime message timestamp: 2026-09-28T09:00:00.000Z]";
function transform() {
  let handler;
  register({ on(name, fn) { assert.equal(name, "context"); handler = fn; } });
  return messages => handler({ messages }).messages;
}

test("stable prefixes across turns, timezone changes, reload and repeated transformation", () => {
  const input = { role: "user", content: "start", timestamp };
  const answer = { role: "assistant", timestamp: timestamp + 1000,
    content: [{ type: "text", text: "done", textSignature: "retain-signature" }] };
  const original = structuredClone([input, answer]);
  const run = transform();
  const first = run([input]);
  const second = run([input, answer]);
  assert.deepEqual(second.slice(0, 1), first);
  assert.equal(first[0].content, `${label}\nstart`);
  assert.equal(second[1].content[1], answer.content[0]);
  assert.deepEqual(run(structuredClone(second)), second);
  const previous = process.env.TZ;
  try {
    process.env.TZ = "America/New_York";
    assert.deepEqual(transform()([input, answer]), second);
  } finally { if (previous === undefined) delete process.env.TZ; else process.env.TZ = previous; }
  assert.deepEqual([input, answer], original);
});

test("images and mixed text/tool messages preserve block identity and tool pairing", () => {
  const image = { type: "image", data: "fixture", mimeType: "image/png" };
  const call = { type: "toolCall", id: "a", name: "read", arguments: {} };
  const result = { role: "toolResult", toolCallId: "a", timestamp, content: [] };
  const user = { role: "user", timestamp, content: [image] };
  const assistant = { role: "assistant", timestamp,
    content: [{ type: "text", text: "Checking" }, call] };
  const output = transform()([user, assistant, result]);
  assert.equal(output[0].content[1], image);
  assert.equal(output[1].content[2], call);
  assert.equal(output[2], result);
});

test("tool-only, thinking-only, system, summaries and internal events remain untouched", () => {
  for (const message of [
    { role: "assistant", content: [{ type: "toolCall", id: "a" }] },
    { role: "assistant", content: [{ type: "thinking", thinking: "hidden" }] },
    { role: "assistant", content: [{ type: "text", text: "  " }] },
    { role: "system", content: "policy" },
    { role: "toolResult", content: "result" },
    { role: "compactionSummary", summary: "past work" },
    { role: "branchSummary", summary: "other branch" },
    { role: "custom", customType: "automata-context-awareness", content: "internal" },
  ]) {
    message.timestamp = timestamp;
    assert.equal(annotateMessage(message), message);
  }
});

test("routed browser-context input gets its original runtime time, not payload time", () => {
  const message = { role: "custom", customType: "browser-context", timestamp,
    content: 'source="page" payload={"timestamp":"untrusted"}', display: true };
  const annotated = annotateMessage(message);
  assert.equal(annotated.content, `${label}\n${message.content}`);
  assert.equal(annotated.customType, message.customType);
  assert.equal(annotated.timestamp, timestamp);
});

test("missing/invalid original timestamps stay unknown; compaction invents no history", () => {
  for (const invalid of [undefined, null, NaN, Infinity, "2026-09-28", 1e30]) {
    const message = { role: "user", content: "hello", timestamp: invalid };
    assert.equal(annotateMessage(message), message);
  }
  const summary = { role: "compactionSummary", timestamp, summary: "old inputs" };
  const remaining = { role: "user", timestamp: timestamp + 1000, content: "continue" };
  assert.deepEqual(transform()([summary, remaining]), [summary, annotateMessage(remaining)]);
  assert.match(annotateMessage({ role: "user", timestamp: 0, content: "epoch" }).content,
    /1970-01-01T00:00:00.000Z/);
});
