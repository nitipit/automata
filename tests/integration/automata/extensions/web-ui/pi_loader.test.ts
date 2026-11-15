import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

test("installed Pi loader discovers browser tools without host/network resources", async () => {
  const { loadExtensions } = await import(pathToFileURL(join(process.env.PI_TEST_PACKAGE_ROOT, "dist/core/extensions/loader.js")));
  const loaded = await loadExtensions([join(process.env.PI_EXTENSION_TEST_ROOT, "index.ts")], process.cwd());
  assert.deepEqual(loaded.errors, []);
  assert.equal(loaded.extensions.length, 1);
  const extension = loaded.extensions[0];
  assert.deepEqual([...extension.tools.keys()], ["web_ui_execute", "web_ui_subscribe", "web_ui_wait_event", "web_ui_unsubscribe"]);
  const { definition } = extension.tools.get("web_ui_execute");
  assert.equal(definition.parameters.type, "object");
  assert.equal(definition.parameters.properties.code.type, "string");
  // Actual definition execution; configuration missing means no HTTP is attempted.
  const priorURL = process.env.AUTOMATA_WEB_CONNECTOR_URL;
  delete process.env.AUTOMATA_WEB_CONNECTOR_URL;
  try {
    const result = await definition.execute("probe", { code: "return 1;" }, undefined, undefined, {});
    assert.equal(result.isError, true);
    assert.equal(result.details.error.code, "configuration");
  } finally {
    if (priorURL !== undefined) process.env.AUTOMATA_WEB_CONNECTOR_URL = priorURL;
  }
  for (const handler of extension.handlers.get("session_shutdown") ?? []) await handler({}, {});
});
