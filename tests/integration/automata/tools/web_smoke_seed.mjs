/** Native persisted fixture only: synthetic chat/tool history, no model or human. */
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const root = process.env.PI_TEST_PACKAGE_ROOT;
if (!root) throw new Error("Set PI_TEST_PACKAGE_ROOT to the installed Pi package directory");
const { SessionManager } = await import(pathToFileURL(join(root, "dist/index.js")).href);
const [cwd, sessionDir] = process.argv.slice(2);
const manager = SessionManager.create(cwd, sessionDir);
const timestamp = Date.now();
manager.appendMessage({
  role: "user", content: "Synthetic offline persistence fixture (not human input)", timestamp,
});
manager.appendMessage({
  role: "assistant", content: [
    { type: "text", text: "Synthetic assistant owner for offline inline UI checks" },
    { type: "toolCall", id: "smoke-history", name: "web_ui_execute", arguments: {
      code: "window.__historicalJavaScriptReplayed = true; ui.root.textContent = 'DO NOT REPLAY';",
    } },
    { type: "toolCall", id: "smoke-plain-history", name: "web_ui_execute", arguments: { code: "" } },
  ],
  api: "openai-responses", provider: "synthetic", model: "offline-fixture",
  usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
  stopReason: "toolUse", timestamp: timestamp + 1,
});
manager.appendMessage({
  role: "toolResult", toolCallId: "smoke-history", toolName: "web_ui_execute",
  content: [{ type: "text", text: "Synthetic historical UI fixture" }],
  details: { ui: { blockId: "smoke-history", toolCallId: "smoke-history" }, retained: [1, 2] },
  isError: false, timestamp: timestamp + 2,
});
manager.appendMessage({
  role: "toolResult", toolCallId: "smoke-plain-history", toolName: "web_ui_execute",
  content: [{ type: "text", text: "Synthetic no-UI return fixture" }],
  details: { retained: "plain-call" }, isError: false, timestamp: timestamp + 3,
});
console.log(JSON.stringify({ sessionFile: manager.getSessionFile(), sessionId: manager.getSessionId() }));
