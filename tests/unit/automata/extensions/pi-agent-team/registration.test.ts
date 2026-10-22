import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { registerAgentTeam } = await import(pathToFileURL(join(process.env.PI_EXTENSION_TEST_ROOT, "index.ts")));

function fixture(options = {}) {
  const tools = new Map(), handlers = new Map(), messages = [];
  registerAgentTeam({
    registerTool(tool) { tools.set(tool.name, tool); },
    on(event, handler) { handlers.set(event, handler); },
    appendEntry() {},
    sendMessage(message) { messages.push(message); },
  }, { workerEnvironment: false, ...options });
  return { tools, handlers, messages };
}

test("extension registration creates no processes; child environment exposes no manager tools", () => {
  const f = fixture();
  assert.equal(f.tools.size, 6);
  assert.equal(f.messages.length, 0);
  const child = fixture({ workerEnvironment: true });
  assert.equal(child.tools.size, 0);
  assert.equal(child.handlers.size, 0);
});
