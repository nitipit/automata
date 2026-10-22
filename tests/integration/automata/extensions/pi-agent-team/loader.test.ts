// Native Pi extension loader smoke test. No session, process, or provider is started.
import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { loadExtensions } = await import(pathToFileURL(join(process.env.PI_TEST_PACKAGE_ROOT, "dist/core/extensions/loader.js")));

test("installed Pi loads the TypeScript bundle and registers six tools", async () => {
  const root = process.env.PI_EXTENSION_TEST_ROOT;
  const result = await loadExtensions([join(root, "index.ts")], root);
  assert.deepEqual(result.errors, []);
  assert.equal(result.extensions.length, 1);
  const extension = result.extensions[0];
  assert.deepEqual([...extension.tools.keys()].sort(), ["agent_abort", "agent_read", "agent_send", "agent_start", "agent_status", "agent_stop"]);
  for (const tool of extension.tools.values()) {
    assert.ok(tool.definition.parameters);
    assert.equal(typeof tool.definition.execute, "function");
  }
});
