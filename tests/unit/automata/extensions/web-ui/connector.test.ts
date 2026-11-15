import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
const { Connector, ConnectorError, validateConfig } = await import(pathToFileURL(join(process.env.PI_EXTENSION_TEST_ROOT, "connector.ts")));
const config = { origin: "http://127.0.0.1:8123", token: "CONNECTOR-PRIVATE" };
const failure = (code, effects) => error => error instanceof ConnectorError && error.code === code && error.effects === effects;

test("construction is resource-free; strict loopback config separates credentials from URLs", () => {
  let calls = 0;
  const connector = new Connector(async () => { calls++; });
  assert.equal(calls, 0);
  assert.deepEqual(validateConfig(config), config);
  for (const origin of ["http://localhost:8123", "https://127.0.0.1", "http://127.0.0.1/?token=secret", "http://evil.example", "http://user:pw@127.0.0.1", "http://127.0.0.1/path"]) {
    assert.throws(() => validateConfig({ ...config, origin }), failure("configuration", "none"));
  }
  connector.close(); connector.close();
});

test("one exact POST, no redirects/retries, credential only in header", async () => {
  const calls = [];
  const connector = new Connector(async (url, options) => {
    calls.push({ url, options }); return Response.json({ value: "ok" });
  });
  const payload = { code: "return 'สวัสดี';" };
  assert.deepEqual(await connector.post(config, "/connector/execute", payload, 1000), { value: "ok" });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, config.origin + "/connector/execute");
  assert.equal(calls[0].options.headers.Authorization, `Bearer ${config.token}`);
  assert.equal(calls[0].options.headers["User-Agent"], "Automata/1.0");
  assert.equal(calls[0].options.redirect, "error");
  assert.deepEqual(JSON.parse(calls[0].options.body), payload);
  connector.close();
});

test("pre-abort and invalid request never dispatch", async () => {
  let calls = 0;
  const connector = new Connector(async () => { calls++; return Response.json({}); });
  const controller = new AbortController(); controller.abort();
  await assert.rejects(connector.post(config, "/execute", {}, 100, controller.signal), failure("cancelled", "none"));
  await assert.rejects(connector.post(config, "/execute", { code: "x".repeat(65536) }, 100), failure("validation", "none"));
  await assert.rejects(connector.post(config, "//remote", {}, 0), failure("validation", "none"));
  assert.equal(calls, 0);
});

test("deadline stays bounded even if fetch ignores abort; no implicit retry", async () => {
  let calls = 0;
  const connector = new Connector(() => { calls++; return new Promise(() => {}); });
  await assert.rejects(connector.post(config, "/execute", {}, 15), failure("timeout", "unknown"));
  assert.equal(calls, 1);
  connector.close();
});

test("shutdown aborts all active waits; closed connector cannot dispatch", async () => {
  let calls = 0;
  const connector = new Connector(() => { calls++; return new Promise(() => {}); });
  const first = connector.post(config, "/execute", {}, 1000);
  const second = connector.post(config, "/wait", {}, 1000);
  connector.close(); connector.close();
  await assert.rejects(first, failure("cancelled", "unknown"));
  await assert.rejects(second, failure("cancelled", "unknown"));
  await assert.rejects(connector.post(config, "/execute", {}, 100), failure("closed", "none"));
  assert.equal(calls, 2);
});

test("native errors and response failures cannot leak connector secrets", async () => {
  for (const fetcher of [async () => { throw new Error(config.token + config.origin); },
    async () => new Response("bad", { status: 403 }), async () => new Response("not json"),
    async () => new Response("x".repeat(65537))]) {
    const connector = new Connector(fetcher);
    await assert.rejects(connector.post(config, "/execute", {}, 1000), error => {
      assert.equal(error.effects, "unknown");
      assert.doesNotMatch(error.message, /CONNECTOR-PRIVATE|8123/);
      return true;
    });
    connector.close();
  }
});

test("deadline covers response-body stalls", async () => {
  const connector = new Connector(async () => new Response(new ReadableStream({ start() {} })));
  await assert.rejects(connector.post(config, "/wait", {}, 15), failure("timeout", "unknown"));
  connector.close();
});
