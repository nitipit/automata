import assert from "node:assert/strict";
import { access, mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

// Explicit SDK opt-in; Python supplies an isolated PI_CODING_AGENT_DIR.
const root = process.env.SESSION_TEST_ROOT;
const { SessionManager } = await import(pathToFileURL(process.env.PI_SESSIONS_NATIVE_SDK));
const { default: register } = await import(pathToFileURL(join(root, "pi-sessions.ts")));
const sourceCwd = join(root, "source");
const targetCwd = join(root, "target");
const runtimeCwd = join(root, "runtime");
for (const cwd of [sourceCwd, targetCwd, runtimeCwd]) await mkdir(cwd);
const source = SessionManager.create(sourceCwd);
source.appendMessage({ role: "user", content: [{ type: "text", text: "Keep /old/project/path unchanged" }], timestamp: Date.now() });
source.appendMessage({
  role: "assistant", content: [{ type: "text", text: "Fixture reply" }],
  api: "openai-responses", provider: "fixture", model: "fixture",
  usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2,
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
  stopReason: "stop", timestamp: Date.now(),
});
source.appendSessionInfo("Fixture source");
const sourcePath = source.getSessionFile();
// Native loader historically mutates this case by appending a newline.
await writeFile(sourcePath, (await readFile(sourcePath, "utf8")).trimEnd());
const before = await readFile(sourcePath);
const tools = new Map();
register({
  registerTool(tool) { tools.set(tool.name, tool); },
  async exec(command, args) {
    assert.equal(command, "trash");
    assert.ok(args[0].startsWith(root + "/"), "never touch real session storage");
    await rename(args[0], args[0] + ".trashed");
    return { code: 0, stderr: "" };
  },
});
const ctx = {
  cwd: runtimeCwd,
  sessionManager: {
    getSessionId: () => "active-fixture",
    getSessionFile: () => undefined,
    getSessionDir: () => join(root, "runtime-store"),
  },
};
const call = (name, params) => tools.get(name).execute("native", params, undefined, undefined, ctx);
const listing = (await call("pi_session_list", { cwd: sourceCwd })).details;
assert.equal(listing.sessions.length, 1);
assert.equal(typeof listing.receipt, "string");
const result = await call("pi_session_copy", {
  copyReceipt: listing.copyReceipt, sessionIds: [source.getSessionId()], targetCwd,
});
assert.equal(result.details.status, "copied", JSON.stringify(result.details));
assert.deepEqual(await readFile(sourcePath), before);
const copies = await SessionManager.list(targetCwd);
assert.equal(copies.length, 1);
assert.notEqual(copies[0].id, source.getSessionId());
assert.equal(copies[0].id, result.details.results[0].sessionId);
assert.equal(copies[0].cwd, targetCwd);
const entries = (await readFile(copies[0].path, "utf8")).trim().split("\n").map(JSON.parse);
assert.equal(entries[0].parentSession, sourcePath);
assert.deepEqual(entries.slice(1), before.toString().split("\n").map(JSON.parse).slice(1));
const reopened = SessionManager.open(copies[0].path);
assert.equal(reopened.getCwd(), targetCwd);
assert.equal(reopened.getSessionId(), copies[0].id);
console.log("Native SDK: destination discovery/reopen, new ID, history and source-byte preservation verified.");

const missingCwd = join(root, "deleted-project");
const orphan = SessionManager.forkFrom(copies[0].path, missingCwd);
const global = (await call("pi_session_list", { scope: "global", directoryStatus: "missing" })).details;
assert.equal(global.sessions.length, 1);
assert.equal(global.sessions[0].id, orphan.getSessionId());
assert.equal(global.sessions[0].cwd, missingCwd);
assert.equal(global.sessions[0].directoryStatus, "missing");
const recovered = await call("pi_session_copy", {
  copyReceipt: global.copyReceipt, sessionIds: [orphan.getSessionId()], targetCwd,
});
assert.equal(recovered.details.status, "copied");
const trashed = await call("pi_session_trash", {
  receipt: global.receipt, sessionIds: [orphan.getSessionId()],
});
assert.equal(trashed.details.status, "trashed");
assert.equal(trashed.details.results[0].cwd, missingCwd);
await access(orphan.getSessionFile() + ".trashed");
await assert.rejects(access(missingCwd));
assert.deepEqual(await readFile(sourcePath), before);
const allIds = [];
let page = (await call("pi_session_list", { scope: "global", limit: 1 })).details;
while (true) {
  allIds.push(...page.sessions.map(s => s.id));
  if (!page.nextCursor) break;
  page = (await call("pi_session_list", { cursor: page.nextCursor })).details;
}
assert.equal(new Set(allIds).size, 3);
console.log("Native SDK: global discovery, orphan recovery, scoped trash adapter and pagination verified.");
