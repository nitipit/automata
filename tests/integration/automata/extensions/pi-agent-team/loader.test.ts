// Native Pi extension loader smoke test. No session, process, or provider is started.
import assert from "node:assert/strict";
import { join, dirname } from "node:path";
import { findPackageJSON } from "node:module";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { loadExtensions } = await import(pathToFileURL(join(process.env.PI_TEST_PACKAGE_ROOT, "dist/core/extensions/loader.js")));
const aiPackage = findPackageJSON("@earendil-works/pi-ai", pathToFileURL(join(process.env.PI_TEST_PACKAGE_ROOT, "package.json")));
const { validateToolArguments } = await import(pathToFileURL(join(dirname(aiPackage), "dist/utils/validation.js")));

test("installed Pi loads the TypeScript bundle and registers seven tools", async () => {
  const root = process.env.PI_EXTENSION_TEST_ROOT;
  const result = await loadExtensions([join(root, "index.ts")], root);
  assert.deepEqual(result.errors, []);
  assert.equal(result.extensions.length, 1);
  const extension = result.extensions[0];
  assert.deepEqual([...extension.tools.keys()].sort(), ["agent_abort", "agent_read", "agent_resume", "agent_send", "agent_start", "agent_status", "agent_stop"]);
  for (const tool of extension.tools.values()) {
    assert.ok(tool.definition.parameters);
    assert.equal(typeof tool.definition.execute, "function");
  }
  const start = extension.tools.get("agent_start").definition;
  const resume = extension.tools.get("agent_resume").definition;
  const args = { workerId: "reviewer", cwd: root, provider: "offline", model: "fake", thinking: "off" };
  const validate = (tool, args) => validateToolArguments(tool, { type: "toolCall", id: "test", name: tool.name, arguments: args });
  assert.deepEqual(validate(start, args), args);
  assert.throws(() => validate(start, { ...args, sessionId: "existing-session" }), /sessionId/);
  assert.throws(() => validate(resume, args), /sessionId/);
  assert.throws(() => validate(resume, { ...args, sessionId: "" }), /sessionId/);
  assert.deepEqual(validate(resume, { ...args, sessionId: "existing-session" }), { ...args, sessionId: "existing-session" });
});
