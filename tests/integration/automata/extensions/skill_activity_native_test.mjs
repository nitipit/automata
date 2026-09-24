// Native Pi tool/event integration + real ShelfDB, using an offline model stub.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { access, mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { homedir } from "node:os";
import { pathToFileURL } from "node:url";

const here = process.env.SKILL_ACTIVITY_EXTENSION;
const { default: register } = await import(pathToFileURL(join(here, "index.ts")));
const sdk = await import(pathToFileURL(process.env.PI_SKILL_ACTIVITY_SDK));
const { createAssistantMessageEventStream } = await import(pathToFileURL(join(
  dirname(dirname(process.env.PI_SKILL_ACTIVITY_SDK)), "../pi-ai/dist/index.js",
)));
const model = {
  id: "fixture", name: "fixture", api: "openai-responses", provider: "fixture",
  baseUrl: "http://unused.invalid", reasoning: false, input: ["text"],
  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
  contextWindow: 32000, maxTokens: 1000,
};
let pendingTool;
let stubCalls = 0;
const root = process.env.SKILL_ACTIVITY_TEST_ROOT;
assert.equal(homedir(), join(root, "home"), "Native test must use its isolated HOME");
const db = join(homedir(), ".agents/var/tools/skill-activity/db");
const legacyDb = join(root, ".agents/var/tools/skill-activity/db");
const skillPath = join(root, "skills/fixture/SKILL.md");
await mkdir(dirname(skillPath), { recursive: true });
await writeFile(skillPath, "---\nname: fixture-skill\ndescription: Test fixture.\n---\n# Fixture Skill\n");
const helper = (action, ...args) => JSON.parse(execFileSync("uv", [
  "run", "--no-project", "--offline", "--script", join(here, "store.py"), action,
  "--db", db, ...args,
], { encoding: "utf8", timeout: 15000, stdio: ["ignore", "pipe", "pipe"] }));
const settings = sdk.SettingsManager.inMemory({
  compaction: { enabled: false }, retry: { enabled: false },
});
const loader = new sdk.DefaultResourceLoader({
  cwd: root, agentDir: join(root, "agent"), settingsManager: settings,
  noExtensions: true, noSkills: true, noContextFiles: true,
  noPromptTemplates: true, noThemes: true,
  extensionFactories: [register, pi => pi.registerProvider("fixture", {
    api: model.api, apiKey: "fixture", baseUrl: model.baseUrl, models: [model],
    streamSimple: () => {
      stubCalls++;
      const call = pendingTool;
      pendingTool = undefined;
      const message = {
        role: "assistant", content: call ? [call] : [{ type: "text", text: "Done." }],
        api: model.api, provider: model.provider, model: model.id,
        stopReason: call ? "toolUse" : "stop", timestamp: Date.now(),
        usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
      const stream = createAssistantMessageEventStream();
      queueMicrotask(() => {
        stream.push({ type: "done", reason: message.stopReason, message });
        stream.end(message);
      });
      return stream;
    },
  })],
  systemPromptOverride: () => "Offline skill-read recording test.",
});
await loader.reload();
assert.deepEqual(loader.getExtensions().errors, []);
const runtime = await sdk.ModelRuntime.create({
  authPath: join(root, "auth.json"), modelsPath: join(root, "models.json"),
  modelsStorePath: join(root, "models-store.json"), allowModelNetwork: false,
});
const { session } = await sdk.createAgentSession({
  cwd: root, agentDir: join(root, "agent"), resourceLoader: loader,
  modelRuntime: runtime, model, settingsManager: settings,
  sessionManager: sdk.SessionManager.inMemory(root), tools: ["read"],
});
try {
  await session.bindExtensions({});
  const tool = session.agent.state.tools.find((t) => t.name === "read");
  assert.ok(tool);
  const read = async (id, args) => {
    pendingTool = { type: "toolCall", id, name: "read", arguments: args };
    await session.prompt("Run the next offline fixture read.");
    const result = session.messages.findLast((m) => m.role === "toolResult" && m.toolCallId === id);
    assert.ok(result, JSON.stringify(session.messages.at(-1)));
    return result;
  };
  assert.deepEqual(helper("list"), []);
  const result = await read("whole-skill", { path: skillPath });
  assert.ok(result.content.some((c) => c.type === "text" && c.text.includes("Fixture Skill")));
  const first = helper("list");
  assert.equal(first.length, 1);
  assert.equal(first[0].skill, "fixture-skill");
  assert.equal(first[0].sessionId, session.sessionManager.getSessionId());
  assert.equal(first[0].path, skillPath);
  assert.equal(first[0].project, root);
  await assert.rejects(access(legacyDb));
  // Historical project data remains untouched; subsequent reads only go global.
  const { source: oldSource, status: oldStatus, ...oldInput } = first[0];
  helper("record", "--db", legacyDb, "--event", JSON.stringify(oldInput));
  const historical = helper("list", "--db", legacyDb);
  assert.equal(first[0].status, "loaded");
  assert.deepEqual(Object.keys(first[0]).sort(), [
    "timestamp", "sessionId", "toolCallId", "project", "skill", "path", "source", "status",
  ].sort());
  await read("whole-skill", { path: skillPath }); // replay should not duplicate
  await read("limited", { path: skillPath, limit: 2 });
  await read("offset", { path: skillPath, offset: 2 });
  await read("missing", { path: join(root, "missing/SKILL.md") }).catch(() => {});
  await read("not-a-skill", { path: join(here, "store.py") });
  await mkdir(join(root, "large"));
  await writeFile(join(root, "large/SKILL.md"), "---\nname: large\n---\n" + "line\n".repeat(3000));
  await read("truncated", { path: join(root, "large/SKILL.md") });
  assert.deepEqual(helper("list"), first);
  await read("reread", { path: skillPath });
  assert.equal(helper("list").length, 2);

  const { source, status, ...validInput } = first[0];
  const { skill, ...missingSkill } = validInput;
  const invalidDb = join(root, "invalid-must-not-create-db");
  const invalidInputs = [
    missingSkill, { ...validInput, skill: 4 }, { ...validInput, skill: "" },
    { ...validInput, sessionId: " " }, { ...validInput, timestamp: "not-a-date" },
    { ...validInput, timestamp: "2026-09-23T12:00:00" },
    { ...validInput, path: "relative/SKILL.md" },
    { ...validInput, conversation: "must-not-be-stored" },
    { ...validInput, source: "shell" }, [], null,
  ];
  for (const invalid of invalidInputs) {
    assert.throws(() => helper("record", "--db", invalidDb, "--event", JSON.stringify(invalid)),
      (error) => error.status === 2 && error.stderr.includes("Invalid skill-activation metadata"));
  }
  await assert.rejects(access(invalidDb));
  assert.equal(helper("list").length, 2);

  // A blocked storage path must not change or reject a successful read.
  let observe;
  register({ on(_name, handler) { observe = handler; }, exec: async () => ({ code: 1 }) });
  const warnings = [];
  const failed = await observe({
    toolName: "read", isError: false, toolCallId: "storage-error",
    input: { path: skillPath }, content: result.content, details: result.details,
  }, { cwd: root, sessionManager: session.sessionManager, hasUI: true,
    ui: { notify: (message) => warnings.push(message) } });
  assert.equal(failed, undefined);
  assert.equal(warnings.length, 1);

  // A second project uses the same global database, retaining its own metadata.
  const otherProject = join(root, "other-project");
  register({
    on(_name, handler) { observe = handler; },
    exec: async (command, args) => ({ code: 0, stdout: execFileSync(command, args, {
      encoding: "utf8", timeout: 15000, stdio: ["ignore", "pipe", "pipe"],
    }), stderr: "" }),
  });
  await observe({
    toolName: "read", isError: false, toolCallId: "other-project-read",
    input: { path: skillPath }, content: result.content, details: result.details,
  }, { cwd: otherProject, sessionManager: { getSessionId: () => "other-project-session" },
    hasUI: false });
  const otherRecords = helper("list", "--project", otherProject, "--limit", "1");
  assert.equal(otherRecords.length, 1);
  assert.equal(otherRecords[0].project, otherProject);
  assert.equal(helper("list", "--project", root).length, 2);
  assert.equal(helper("list").length, 3);
  assert.deepEqual(helper("list", "--db", legacyDb), historical);
  await assert.rejects(access(join(otherProject, ".agents/var/tools/skill-activity/db")));

  const receipt = { sdk: process.env.PI_SKILL_ACTIVITY_SDK, project: root, db,
    sessionId: session.sessionManager.getSessionId(), records: helper("list"),
    checks: ["native Pi read/event", "ShelfDB persistence across processes", "metadata only",
      "duplicate replay", "genuine reread", "skip limited/offset/failed/non-skill/truncated reads",
      "Dictify rejects 11 invalid inputs before DB creation",
      "storage failure preserves read", "global default under isolated home",
      "cross-project observer storage and filtered queries", "historical local data preserved"],
    externalModelCalls: 0, stubCalls };
  await writeFile(join(root, "result.json"), JSON.stringify(receipt, null, 2) + "\n");
  console.log(JSON.stringify(receipt, null, 2));
} finally {
  session.dispose();
}
