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
  return { tools, calls, pi, shutdown: () => events.get("session_shutdown")(),
    call: (name, params, signal) => tools.find(tool => tool.name === "web_ui_" + name).execute("call", params, signal) };
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
  const code = "document.querySelector('#generated-ui').textContent='hello'; return null;";
  assert.equal((await f.call("execute", { code })).isError, false);
  assert.equal(f.calls[1].payload.code, code);
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
