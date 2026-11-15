import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

test("native Pi discovers readable skill and keeps orientation a stable additive prompt section", async () => {
  const root = await mkdtemp(join(tmpdir(), "automata-web-guidance-"));
  const sdk = await import(pathToFileURL(join(process.env.PI_TEST_PACKAGE_ROOT, "dist/index.js")));
  const { buildSystemPromptSections, diffSystemPromptSections } = await import(pathToFileURL(join(process.env.PI_TEST_PACKAGE_ROOT, "dist/core/system-prompt.js")));
  const priorURL = process.env.AUTOMATA_WEB_CONNECTOR_URL;
  const priorToken = process.env.AUTOMATA_WEB_CONNECTOR_TOKEN;
  process.env.AUTOMATA_WEB_CONNECTOR_URL = "http://127.0.0.1:8123/connector";
  process.env.AUTOMATA_WEB_CONNECTOR_TOKEN = "FIXTURE-NOT-A-CREDENTIAL";
  let session;
  try {
    const settings = sdk.SettingsManager.inMemory({ packages: [], compaction: { enabled: false } });
    const loader = new sdk.DefaultResourceLoader({
      cwd: root, agentDir: join(root, "agent"), settingsManager: settings,
      additionalExtensionPaths: [join(process.env.PI_EXTENSION_TEST_ROOT, "index.ts")],
      noExtensions: true, noSkills: true, noContextFiles: true,
      noPromptTemplates: true, noThemes: true,
    });
    await loader.reload();
    assert.deepEqual(loader.getExtensions().errors, []);
    const runtime = await sdk.ModelRuntime.create({
      authPath: join(root, "auth.json"), modelsPath: join(root, "models.json"),
      modelsStorePath: join(root, "models-store.json"), allowModelNetwork: false,
    });
    ({ session } = await sdk.createAgentSession({
      cwd: root, agentDir: join(root, "agent"), resourceLoader: loader,
      modelRuntime: runtime, settingsManager: settings,
      sessionManager: sdk.SessionManager.inMemory(root), tools: ["read"],
    }));
    await session.bindExtensions({}); // Runs real session_start -> resources_discover.
    const { skills, diagnostics } = loader.getSkills();
    assert.deepEqual(diagnostics, []);
    assert.equal(skills.length, 1);
    const skill = skills[0];
    assert.equal(skill.name, "automata-web-ui");
    const content = await readFile(skill.filePath, "utf8");
    const reader = sdk.createReadTool(root);
    const read = await reader.execute("read-skill", { path: skill.filePath });
    assert.equal(read.content[0].text, content);
    const runner = session.extensionRunner;
    assert.ok(runner);
    const base = { cwd: root, skills, selectedTools: ["read", "web_ui_execute"],
      customPrompt: "Preserved user prompt", sections: { unrelated: "Preserved section" } };
    const first = await runner.emitBeforeAgentStart({ messageType: "user", prompt: "unused fixture input" }, base);
    assert.deepEqual(first.messages, []);
    assert.equal(first.systemPromptOptions.forceSystemPrompt, undefined);
    assert.equal(first.systemPromptOptions.customPrompt, base.customPrompt);
    assert.equal(first.systemPromptOptions.sections.unrelated, base.sections.unrelated);
    const sections = buildSystemPromptSections(first.systemPromptOptions);
    assert.ok(sections.automata_web_ui);
    assert.ok(sections.skills.includes(skill.filePath));
    assert.equal(JSON.stringify(sections).includes(process.env.AUTOMATA_WEB_CONNECTOR_TOKEN), false);
    // A fresh options object on the next run (also after restored prompt state)
    // must produce no patch or repeated injected conversation messages.
    const second = await runner.emitBeforeAgentStart({ messageType: "custom", message: { customType: "fixture", content: "fixture", display: false } }, base);
    assert.deepEqual(second.messages, []);
    assert.equal(diffSystemPromptSections(structuredClone(sections), buildSystemPromptSections(second.systemPromptOptions)), undefined);
    delete process.env.AUTOMATA_WEB_CONNECTOR_URL;
    const inactive = await runner.emitBeforeAgentStart({ messageType: "user", prompt: "unused fixture input" }, base);
    const patch = diffSystemPromptSections(sections, buildSystemPromptSections(inactive.systemPromptOptions));
    assert.deepEqual(patch, { automata_web_ui: null });
    assert.equal(session.messages.length, 0); // No prompt/provider/model execution.
  } finally {
    session?.dispose();
    if (priorURL === undefined) delete process.env.AUTOMATA_WEB_CONNECTOR_URL;
    else process.env.AUTOMATA_WEB_CONNECTOR_URL = priorURL;
    if (priorToken === undefined) delete process.env.AUTOMATA_WEB_CONNECTOR_TOKEN;
    else process.env.AUTOMATA_WEB_CONNECTOR_TOKEN = priorToken;
    await rm(root, { recursive: true, force: true });
  }
});

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
