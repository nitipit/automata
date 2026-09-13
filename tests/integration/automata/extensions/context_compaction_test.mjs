import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { default: register } = await import(pathToFileURL(
  join(process.env.CONTEXT_TEST_ROOT, "context-compaction.ts"),
));

function fixture() {
  const handlers = new Map();
  const calls = [];
  const sent = [];
  let tool;
  register({
    on(name, handler) { handlers.set(name, handler); },
    registerTool(value) { tool = value; },
    sendMessage(...args) { sent.push(args); },
  });
  const ctx = {
    hasUI: false,
    isIdle: () => true,
    hasPendingMessages: () => false,
    compact(options) { calls.push(options); },
  };
  return {
    tool, ctx, calls, sent,
    emit: (name) => handlers.get(name)({}, ctx),
    request: (params = {}) => tool.execute("test", params),
  };
}

test("instruction schema has no wrapper-specific length constraints", () => {
  const schema = fixture().tool.parameters.properties.customInstructions;
  assert.equal(schema.type, "string");
  assert.equal(schema.minLength, undefined);
  assert.equal(schema.maxLength, undefined);
});

for (const [name, params] of [
  ["omitted", {}],
  ["empty", { customInstructions: "" }],
  ["whitespace", { customInstructions: " \n\t " }],
  ["long Unicode", { customInstructions: " \n" + "บริบท🙂".repeat(1000) + "\n " }],
]) {
  test(`forwards ${name} instructions unchanged only after settling`, async () => {
    const f = fixture();
    const result = await f.request(params);
    assert.equal(result.details.status, "queued");
    assert.equal(result.terminate, true);
    assert.equal(f.calls.length, 0);
    const settled = f.emit("agent_settled");
    assert.equal(f.calls.length, 1);
    assert.equal(f.calls[0].customInstructions, params.customInstructions);
    f.calls[0].onComplete();
    await settled;
    await f.emit("agent_settled");
    assert.equal(f.calls.length, 1);
    assert.deepEqual(f.sent, []);
  });
}

test("keeps first queued instructions and prevents concurrent compaction", async () => {
  const f = fixture();
  const first = await f.request({ customInstructions: "first" });
  const duplicate = await f.request({ customInstructions: "second" });
  assert.equal(duplicate.details.status, "already_queued");
  assert.equal(duplicate.details.requestId, first.details.requestId);
  const settled = f.emit("agent_settled");
  assert.equal(f.calls[0].customInstructions, "first");
  assert.equal((await f.request()).details.status, "in_progress");
  await f.emit("agent_settled");
  assert.equal(f.calls.length, 1);
  f.calls[0].onComplete();
  await settled;
  assert.equal((await f.request()).details.status, "queued");
});

test("waits while busy or while messages are pending", async () => {
  const f = fixture();
  await f.request();
  f.ctx.isIdle = () => false;
  await f.emit("agent_settled");
  f.ctx.isIdle = () => true;
  f.ctx.hasPendingMessages = () => true;
  await f.emit("agent_settled");
  assert.equal(f.calls.length, 0);
  f.ctx.hasPendingMessages = () => false;
  const settled = f.emit("agent_settled");
  f.calls[0].onComplete();
  await settled;
});

for (const event of ["session_compact", "session_start", "session_tree", "session_shutdown"]) {
  test(`${event} clears a queued request`, async () => {
    const f = fixture();
    await f.request();
    await f.emit(event);
    await f.emit("agent_settled");
    assert.equal(f.calls.length, 0);
  });
}

test("reports native failure without automatically retrying", async () => {
  const f = fixture();
  await f.request();
  const settled = f.emit("agent_settled");
  f.calls[0].onError(new Error("native failure"));
  await settled;
  await f.emit("agent_settled");
  assert.equal(f.calls.length, 1);
  assert.equal(f.sent.length, 1);
  assert.equal(f.sent[0][0].details.status, "failed");
  assert.deepEqual(f.sent[0][1], { deliverAs: "nextTurn" });
  assert.equal((await f.request()).details.status, "queued");
});
