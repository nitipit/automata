import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
const { registerWebUI, default: register } = await import(pathToFileURL(join(process.env.PI_EXTENSION_TEST_ROOT, "index.ts")));
const env = { AUTOMATA_WEB_CONNECTOR_URL: "http://127.0.0.1:8123/connector", AUTOMATA_WEB_CONNECTOR_TOKEN: "PRIVATE" };
function fixture(handler = async () => ({ ok: true }), config = env) {
  const tools = [], events = new Map(), calls = [];
  const pi = { registerTool(tool) { tools.push(tool); }, on(event, callback) { events.set(event, callback); } };
  registerWebUI(pi, async (url, options) => {
    const call = { url, ...options, payload: JSON.parse(options.body) }; calls.push(call);
    return Response.json(await handler(call));
  }, config);
  return { tools, calls, pi, events, shutdown: () => events.get("session_shutdown")(),
    call: (name, params, signal, toolCallId = "call") => tools.find(tool => tool.name === "web_ui_" + name).execute(toolCallId, params, signal) };
}

test("factory registers actual four-tool surface without network; missing env fails closed", async () => {
  const f = fixture(undefined, {});
  assert.deepEqual(f.tools.map(t => t.name), ["web_ui_execute", "web_ui_subscribe", "web_ui_wait_event", "web_ui_unsubscribe"]);
  assert.equal(f.calls.length, 0);
  assert.equal((await f.call("execute", { code: "return 1;" })).details.error.code, "configuration");
  assert.equal(f.calls.length, 0);
  register(f.pi); // Real default factory is safe without host configuration.
  await f.shutdown();
});

test("orientation is configuration/tool scoped and changes only its own stable section", async () => {
  for (const config of [{}, { ...env, AUTOMATA_WEB_CONNECTOR_TOKEN: "" },
    { ...env, AUTOMATA_WEB_CONNECTOR_URL: "https://example.com/connector" },
    { ...env, AUTOMATA_WEB_CONNECTOR_URL: env.AUTOMATA_WEB_CONNECTOR_URL + "?secret=no" }]) {
    const f = fixture(undefined, config);
    const options = { selectedTools: ["web_ui_execute"], sections: { other: "preserved", automata_web_ui: "stale" } };
    assert.equal(f.events.get("before_agent_start")({ systemPromptOptions: options }), undefined);
    assert.deepEqual(options.sections, { other: "preserved" });
    assert.equal(f.calls.length, 0);
    await f.shutdown();
  }
  const config = { ...env }, f = fixture(undefined, config);
  const options = { selectedTools: ["read", "web_ui_execute"], sections: { other: "preserved" }, customPrompt: "USER CONFIG" };
  f.events.get("before_agent_start")({ systemPromptOptions: options });
  const once = structuredClone(options);
  assert.ok(options.sections.automata_web_ui.length > 0);
  assert.equal(JSON.stringify(options).includes("PRIVATE"), false);
  f.events.get("before_agent_start")({ systemPromptOptions: options });
  assert.deepEqual(options, once);
  options.selectedTools = ["read"];
  f.events.get("before_agent_start")({ systemPromptOptions: options });
  assert.deepEqual(options.sections, { other: "preserved" });
  assert.equal(options.customPrompt, "USER CONFIG");
  assert.equal(f.calls.length, 0);
  await f.shutdown();
});

test("subscribe before execute retains early event; correlation and exact JS roundtrip", async () => {
  let queued;
  const f = fixture(async ({ url, payload }) => {
    if (url.endsWith("/subscribe")) { assert.equal(payload.correlationId, "request-1"); return { ok: true, subscriptionId: "s1" }; }
    if (url.endsWith("/execute")) { queued = { correlationId: "request-1", choice: "yes" }; return { ok: true, value: null }; }
    if (url.endsWith("/wait")) { assert.equal(payload.subscriptionId, "s1"); const event = queued; queued = undefined; return { ok: true, event }; }
    return { ok: true };
  });
  const subscribed = await f.call("subscribe", { name: "choice", correlationId: "request-1" });
  assert.equal(subscribed.details.subscriptionId, "s1");
  const code = "ui.root.textContent='hello'; return null;";
  assert.equal((await f.call("execute", { code })).isError, false);
  assert.equal(f.calls[1].payload.code, code);
  assert.equal(f.calls[1].payload.toolCallId, "call");
  const waited = await f.call("wait_event", { subscriptionId: "s1" });
  assert.deepEqual(waited.details.event, { correlationId: "request-1", choice: "yes" });
  await f.call("unsubscribe", { subscriptionId: "s1" });
  await f.call("unsubscribe", { subscriptionId: "s1" });
  assert.equal(f.calls.filter(c => c.url.endsWith("/unsubscribe")).length, 1);
  await f.shutdown();
});

test("unknown IDs do not reach host; host timeout uncertainty preserved", async () => {
  const f = fixture(async () => ({ ok: false, error: { code: "timeout", message: "JS still running", uncertain: true } }));
  assert.equal((await f.call("wait_event", { subscriptionId: "other-session" })).details.effects, "none");
  assert.equal(f.calls.length, 0);
  const result = await f.call("execute", { code: "await x();", timeoutMs: 100 });
  assert.equal(result.isError, true); assert.equal(result.details.effects, "unknown");
  assert.equal(result.details.error.code, "timeout");
  await f.shutdown();
});

test("malformed host envelopes/results are errors, not apparent success", async () => {
  for (const reply of [{}, { ok: "yes" }, { ok: false }, { ok: true }]) {
    const f = fixture(async () => reply);
    const result = await f.call("execute", { code: "return 1;" });
    assert.equal(result.isError, true); assert.equal(result.details.error.code, "protocol");
    assert.equal(result.details.effects, "unknown");
    await f.shutdown();
  }
});

test("shutdown releases owned subscriptions once and blocks future work", async () => {
  let id = 0;
  const f = fixture(async ({ url }) => url.endsWith("/subscribe") ? { ok: true, subscriptionId: `s${++id}` } : { ok: true });
  await f.call("subscribe", { name: "a" }); await f.call("subscribe", { name: "b" });
  await f.shutdown(); await f.shutdown();
  assert.deepEqual(f.calls.filter(c => c.url.endsWith("/unsubscribe")).map(c => c.payload.subscriptionId).sort(), ["s1", "s2"]);
  const result = await f.call("execute", { code: "return 1;" });
  assert.equal(result.details.error.code, "closed");
  assert.equal(f.calls.length, 4);
});

test("large browser result is omitted from both content and details", async () => {
  const f = fixture(async () => ({ ok: true, value: "x".repeat(50000) }));
  const result = await f.call("execute", { code: "return large;" });
  assert.equal(result.isError, true); assert.equal(result.details.code, "output_limit");
  assert.ok(JSON.stringify(result).length < 1024);
  assert.equal("ui" in result.details, false);
  assert.equal(result.content[0].text.includes("Materialized UI identity"), false);
  await f.shutdown();
});

test("local ownership is bounded and host-invalidated subscriptions are forgotten", async () => {
  let next = 0;
  const f = fixture(async ({ url }) => url.endsWith("/subscribe") ? { ok: true, subscriptionId: `s${++next}` } :
    url.endsWith("/wait") ? { ok: false, error: { code: "subscription_unavailable", message: "expired" } } : { ok: true });
  for (let i = 0; i < 32; i++) await f.call("subscribe", { name: "a" });
  assert.equal((await f.call("subscribe", { name: "a" })).details.error.code, "capacity");
  assert.equal(f.calls.length, 32);
  await f.call("wait_event", { subscriptionId: "s1" });
  assert.equal((await f.call("wait_event", { subscriptionId: "s1" })).details.error.code, "subscription");
  assert.equal((await f.call("subscribe", { name: "a" })).isError, false);
  await f.shutdown();
  assert.equal(f.calls.filter(c => c.url.endsWith("/unsubscribe")).length, 32);
});

test("subscription ownership cannot silently retarget a changed connector", async () => {
  const mutable = { ...env };
  const f = fixture(async () => ({ ok: true, subscriptionId: "owned" }), mutable);
  await f.call("subscribe", { name: "answer" });
  mutable.AUTOMATA_WEB_CONNECTOR_URL = "http://127.0.0.1:9123/connector";
  const result = await f.call("wait_event", { subscriptionId: "owned" });
  assert.equal(result.details.error.code, "configuration");
  assert.equal(result.details.effects, "none");
  assert.equal(f.calls.length, 1);
  await f.shutdown();
  assert.equal(f.calls[1].url, "http://127.0.0.1:8123/connector/unsubscribe");
});

test("independent concurrent executions return their own correlated values", async () => {
  const f = fixture(async ({ payload }) => { await new Promise(resolve => setTimeout(resolve, payload.code === "first" ? 10 : 1)); return { ok: true, value: payload.code }; });
  const [first, second] = await Promise.all([f.call("execute", { code: "first" }), f.call("execute", { code: "second" })]);
  assert.equal(first.details.value, "first"); assert.equal(second.details.value, "second");
  await f.shutdown();
});

test("native execution owner is internal, metadata persists without altering arbitrary value", async () => {
  const value = { ok: false, execution: "not-an-envelope", ui: { blockId: "other" } };
  const f = fixture(async ({ payload }) => ({ ok: true, value,
    ui: { blockId: payload.toolCallId, toolCallId: payload.toolCallId, unwanted: "PRIVATE" } }));
  const result = await f.call("execute", { code: "ui.root; return arbitrary;" }, undefined, "native-owner");
  assert.deepEqual(f.calls[0].payload, { code: "ui.root; return arbitrary;", toolCallId: "native-owner" });
  assert.deepEqual(result.details.value, value);
  assert.deepEqual(result.details.ui, { blockId: "native-owner", toolCallId: "native-owner" });
  assert.deepEqual(JSON.parse(result.content[0].text), result.details);
  await f.shutdown();
});

test("caught JS failure and oversized value preserve only bounded materialized identity", async () => {
  for (const reply of [
    { ok: false, error: { code: "javascript_error", message: "JS failed", uncertain: true } },
    { ok: true, value: "x".repeat(50000) },
  ]) {
    const ui = { blockId: "call", toolCallId: "call" };
    const f = fixture(async () => ({ ...reply, ui }));
    const result = await f.call("execute", { code: "ui.root; failOrReturn();" });
    assert.equal(result.isError, true);
    assert.deepEqual(result.details.ui, ui);
    assert.equal(result.details.effects, "unknown");
    assert.ok(JSON.stringify(result).length < 1024);
    await f.shutdown();
  }
});

test("oversized value omission keeps validated identity in bounded model-facing content", async () => {
  const toolCallId = '\"\\n😀'.repeat(200);
  const ui = { blockId: toolCallId, toolCallId };
  const f = fixture(async () => ({ ok: true, value: "x".repeat(50000), ui }));
  const result = await f.call("execute", { code: "ui.root; return large;" }, undefined, toolCallId);
  assert.equal(result.details.code, "output_limit");
  assert.deepEqual(result.details.ui, ui);
  assert.ok(result.content[0].text.includes(JSON.stringify({ ui })));
  assert.ok(Buffer.byteLength(result.content[0].text) < 48 * 1024);
  assert.ok(Buffer.byteLength(JSON.stringify(result.details)) < 48 * 1024);
  assert.equal("value" in result.details, false);
  assert.equal(result.content[0].text.includes("x".repeat(100)), false);
  await f.shutdown();

  const oversizedId = "i".repeat(1025);
  const invalid = fixture(async () => ({ ok: true, value: null,
    ui: { blockId: oversizedId, toolCallId: oversizedId } }));
  const rejected = await invalid.call("execute", { code: "ui.root" }, undefined, oversizedId);
  assert.equal(rejected.details.error.code, "protocol");
  assert.equal("ui" in rejected.details, false);
  await invalid.shutdown();
});

test("plain executions have no invented UI marker; foreign metadata fails closed", async () => {
  const plain = fixture(async () => ({ ok: true, value: null }));
  assert.equal("ui" in (await plain.call("execute", { code: "return null" })).details, false);
  await plain.shutdown();
  for (const ui of [null, {}, { blockId: "foreign", toolCallId: "call" }, { blockId: "call", toolCallId: "foreign" }]) {
    const f = fixture(async () => ({ ok: true, value: null, ui }));
    const result = await f.call("execute", { code: "ui.root" });
    assert.equal(result.details.error.code, "protocol");
    assert.equal(result.details.effects, "unknown");
    await f.shutdown();
  }
});
