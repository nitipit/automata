import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const root = process.env.TOKEN_TEST_ROOT;
const pkg = process.env.TOKEN_PI_PACKAGE;
const load = path => import(pathToFileURL(path));
const { default: register, LANDMARK_TYPE, measuredUsage, counted } = await load(join(root, "token-awareness.ts"));
const { default: timestamps } = await load(join(root, "message-timestamps.ts"));
const sdk = await load(join(pkg, "dist/index.js"));
const { ExtensionRunner } = await load(join(pkg, "dist/core/extensions/runner.js"));
const { convertToLlm } = await load(join(pkg, "dist/core/messages.js"));
const aiRoot = join(pkg, "../../@earendil-works/pi-ai/dist");
const { createAssistantMessageEventStream } = await load(join(aiRoot, "index.js"));
const { processResponsesStream } = await load(join(aiRoot, "api/openai-responses-shared.js"));
const cost = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 };
const usage = (input = 0, output = 0, cacheRead = 0, cacheWrite = 0) =>
  ({ input, output, cacheRead, cacheWrite, totalTokens: input + output + cacheRead + cacheWrite, cost });
let clock = 1;
const assistant = (u, content = [{ type: "text", text: "answer" }]) => ({
  role: "assistant", content, timestamp: clock++, usage: u,
  api: "openai-responses", provider: "offline", model: "fixture", stopReason: "stop",
});
const marks = messages => messages.filter(m => m.customType === LANDMARK_TYPE);

function fixture(manager = sdk.SessionManager.inMemory(root)) {
  const handlers = new Map();
  let tool;
  const pi = {
    on(name, fn) { const list = handlers.get(name) ?? []; list.push(fn); handlers.set(name, list); },
    appendEntry: (name, data) => manager.appendCustomEntry(name, data),
    registerTool(value) { tool = value; },
    sendMessage() { assert.fail("No messages, wakeups, or UI delivery"); },
  };
  timestamps(pi);
  register(pi);
  const ctx = { sessionManager: manager };
  const runner = { createContext: () => ctx,
    extensions: [{ path: "offline-test", handlers }],
    emitError(error) { assert.fail(JSON.stringify(error)); } };
  return {
    manager,
    async end() { for (const fn of handlers.get("turn_end") ?? []) await fn({}, ctx); },
    async transform(messages = manager.buildSessionContext().messages) {
      return ExtensionRunner.prototype.emitContext.call(runner, messages);
    },
    async inspect() { return (await tool.execute("inspect", { action: "inspect" }, null, null, ctx)).details; },
    async set(threshold) { return tool.execute("set", { action: "set", threshold }, null, null, ctx); },
    async call(params) { return tool.execute("test", params, null, null, ctx); },
    add(u, content) { return manager.appendMessage(assistant(u, content)); },
  };
}

test("threshold edge, excluded reads, included writes once, one landmark per jump", async () => {
  const f = fixture();
  f.add(usage(99_998, 1, 900_000));
  await f.end();
  assert.equal((await f.inspect()).landmarkCount, 0);
  f.add(usage(0, 0, 800_000, 1));
  await f.end();
  let state = await f.inspect();
  assert.equal(state.landmarkCount, 1);
  assert.equal(state.cumulative.cacheWrite, 1);
  const first = marks(await f.transform())[0];
  assert.match(first.content, /counted=100000/);
  assert.match(first.content, /cacheRead=1700000/);
  f.add(usage(350_000));
  await f.end();
  state = await f.inspect();
  assert.equal(state.landmarkCount, 2);
  assert.equal(counted(state.delta), 0);
  assert.match(marks(await f.transform())[1].content, /input=350000/);
  await f.end();
  assert.equal((await f.inspect()).landmarkCount, 2);
});

test("invalid or missing usage is unknown, valid zero is retained with ambiguity", async () => {
  assert.equal(measuredUsage(undefined), undefined);
  for (const invalid of [null, {}, { input: 1 }, usage(-1), usage(NaN), usage(Infinity), usage(1.5)]) {
    assert.equal(measuredUsage(invalid), undefined);
  }
  assert.deepEqual(measuredUsage(usage()), { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 });
  const f = fixture();
  f.add(undefined);
  f.add(usage());
  f.add(usage(100_000));
  await f.end();
  const state = await f.inspect();
  assert.equal(state.cumulative.unknown, 1);
  assert.equal(state.cumulative.measured, 2);
  assert.equal(state.cumulative.zeroResponses, 1);
  const text = marks(await f.transform())[0].content;
  assert.match(text, /Unknown responses are excluded/);
  assert.match(text, /Zero records may include provider telemetry unavailable/);
});

test("threshold adjustment never resets accrued usage or rewrites landmarks", async () => {
  const f = fixture();
  f.add(usage(60_000));
  await f.end();
  await f.set(200_000);
  assert.equal((await f.inspect()).delta.input, 60_000);
  await f.set(50_000);
  assert.equal((await f.inspect()).pending, true);
  assert.equal((await f.inspect()).landmarkCount, 0);
  const first = marks(await f.transform())[0];
  assert.match(first.content, /Threshold=50000/);
  await f.set(10);
  assert.deepEqual(marks(await f.transform()), [first]);
  for (const value of [0, -1, 1.2, Infinity, NaN, 1_000_000_001, "10", undefined]) {
    await assert.rejects(f.set(value), /threshold/);
  }
  await assert.rejects(f.call({ action: "inspect", threshold: 1 }), /inspect/);
});

test("immutable model-only annotations, tool pairs, no conversation history/UI changes", async () => {
  const f = fixture();
  const user = { role: "user", content: "question", timestamp: clock++ };
  f.manager.appendMessage(user);
  f.add(usage(100_000), [{ type: "toolCall", id: "t", name: "fixture", arguments: {} }]);
  f.manager.appendMessage({ role: "toolResult", toolName: "fixture", toolCallId: "t",
    content: [{ type: "text", text: "result" }], timestamp: clock++ });
  await f.end();
  f.manager.appendMessage({ role: "user", content: "next question", timestamp: clock++ });
  const history = structuredClone(f.manager.getEntries());
  const context = f.manager.buildSessionContext().messages;
  const original = structuredClone(context);
  const one = await f.transform(context);
  const two = await f.transform(context);
  assert.deepEqual(one, two);
  assert.deepEqual(context, original);
  assert.deepEqual(f.manager.getEntries(), history);
  assert.equal(one.findIndex(m => m.customType === LANDMARK_TYPE), 3);
  assert.equal(one[1].role, "assistant");
  assert.equal(one[2].role, "toolResult");
  assert.match(one[0].content, /Runtime message timestamp/);
  assert.ok(convertToLlm(one).some(m => m.role === "user" &&
    JSON.stringify(m.content).includes("Token usage landmark")));
  assert.deepEqual(marks(await f.transform(one)), marks(one));
  assert.equal(f.manager.getEntries().filter(e => e.type === "custom_message").length, 0);
});

test("native persistence/reload, compaction, edits, tree switching and fork ancestry", async () => {
  const manager = sdk.SessionManager.create(root, join(root, "sessions"));
  let f = fixture(manager);
  const origin = manager.appendMessage({ role: "user", content: "origin", timestamp: clock++ });
  f.add(usage(100_000));
  await f.end();
  const first = marks(await f.transform())[0];
  const common = manager.getLeafId();
  await f.set(200_000);
  const omitted = f.add(usage(250_000));
  await f.end();
  manager.appendContextEdit(omitted, null);
  manager.appendCompaction("summary", null, 1000, undefined, false, usage(700_000));
  const before = await f.inspect();
  assert.equal(before.cumulative.input, 350_000, "summary calls excluded, omitted requests still counted");
  assert.equal(marks(await f.transform()).length, 2);
  const path = manager.getSessionFile();
  f = fixture(sdk.SessionManager.open(path, join(root, "sessions")));
  assert.deepEqual((await f.inspect()).cumulative, before.cumulative);
  assert.deepEqual(marks(await f.transform())[0], first);
  const future = f.manager.getLeafId();
  f.manager.branch(common);
  assert.equal((await f.inspect()).threshold, 100_000);
  assert.equal((await f.inspect()).cumulative.input, 100_000);
  assert.equal(marks(await f.transform()).length, 1);
  f.add(usage(50_000));
  await f.end();
  assert.equal((await f.inspect()).delta.input, 50_000);
  f.manager.branch(future);
  assert.equal((await f.inspect()).threshold, 200_000);
  assert.equal((await f.inspect()).cumulative.input, 350_000);
  f.manager.branch(origin);
  assert.equal(marks(await f.transform()).length, 0);
  f.manager.branch(future);
  const parentSessionId = f.manager.getSessionId();
  const forkPath = f.manager.createBranchedSession(future);
  const fork = sdk.SessionManager.open(forkPath, join(root, "sessions"));
  const child = fixture(fork);
  assert.notEqual(fork.getSessionId(), parentSessionId);
  assert.equal((await child.inspect()).cumulative.input, 350_000);
  assert.deepEqual(marks(await child.transform())[0], first, "inherited annotations never relabeled");
  child.add(usage(200_000));
  await child.end();
  assert.match(marks(await child.transform()).at(-1).content, new RegExp(fork.getSessionId()));
  assert.equal((await f.inspect()).cumulative.input, 350_000);
});

test("malformed and stale landmark metadata cannot poison baselines or projection", async () => {
  for (const corrupt of [
    null, [], 12, { version: 1 },
    { version: 1, cumulative: null, delta: {} },
  ]) {
    const f = fixture();
    f.add(usage(100_000));
    f.manager.appendCustomEntry(LANDMARK_TYPE, corrupt);
    assert.equal((await f.inspect()).landmarkCount, 0);
    assert.equal(marks(await f.transform()).length, 1, "catch-up replaces invalid baseline");
    assert.equal((await f.inspect()).delta.input, 0);
  }
  const f = fixture();
  f.add(usage(100_000));
  await f.end();
  const valid = f.manager.getLeafEntry().data;
  for (const change of [
    { timestamp: NaN }, { timestamp: "now" }, { sessionId: null },
    { throughEntryId: "future-branch" }, { threshold: 0 },
    { cumulative: { ...valid.cumulative, input: 99_999 } },
    { delta: { ...valid.delta, input: -1 } },
    { cumulative: { ...valid.cumulative, measured: Infinity } },
  ]) {
    f.manager.appendCustomEntry(LANDMARK_TYPE, {
      ...valid, throughEntryId: f.manager.getLeafId(), ...change,
    });
  }
  assert.equal((await f.inspect()).landmarkCount, 1);
  assert.equal(marks(await f.transform()).length, 1);
  assert.equal((await f.inspect()).delta.input, 0);
});

test("no wall-clock trigger; catch-up has actual creation metadata, not historical dates", async () => {
  const f = fixture();
  f.add(usage(1));
  const now = Date.now;
  try {
    Date.now = () => 2_000_000_000_000;
    assert.equal(marks(await f.transform()).length, 0);
    f.add(usage(99_999));
    const marker = marks(await f.transform())[0];
    assert.equal(marker.timestamp, Date.now());
    Date.now = () => 3_000_000_000_000;
    assert.deepEqual(marks(await f.transform()), [marker]);
  } finally { Date.now = now; }
});

test("nested tool, cache warming and branch-summary usage are excluded", async () => {
  const f = fixture();
  const origin = f.add(usage(2, 3, 4, 5));
  f.manager.appendMessage({ role: "toolResult", toolCallId: "nested", toolName: "nested",
    content: [], timestamp: clock++, usage: usage(1_000_000) });
  f.manager.appendUsage("cache_warm", "offline", "fixture", usage(1_000_000));
  assert.equal((await f.inspect()).cumulative.input, 2);
  f.manager.branchWithSummary(origin, "summary", undefined, false, usage(1_000_000));
  assert.equal((await f.inspect()).cumulative.input, 2);
  assert.equal((await f.inspect()).cumulative.cacheWrite, 5);
  assert.equal(marks(await f.transform()).length, 0);
});

test("native Responses normalizer subtracts raw cache read/write before our counting", async () => {
  const output = assistant(usage());
  const model = { id: "fixture", provider: "offline", cost };
  async function* events() {
    yield { type: "response.completed", response: { id: "r", status: "completed", output: [],
      usage: { input_tokens: 150_000, output_tokens: 10,
        input_tokens_details: { cached_tokens: 30_000, cache_write_tokens: 20_000 },
        output_tokens_details: { reasoning_tokens: 5 }, total_tokens: 150_010 } } };
  }
  await processResponsesStream(events(), output, { push() {} }, model);
  assert.equal(output.usage.input, 100_000);
  assert.equal(output.usage.cacheWrite, 20_000);
  assert.equal(output.usage.reasoning, 5);
  assert.equal(counted(measuredUsage(output.usage)), 120_010);
});

test("native chat rendering ignores metadata without a registered renderer", async () => {
  const { InteractiveMode } = await load(join(pkg, "dist/modes/interactive/interactive-mode.js"));
  const mode = { session: { extensionRunner: { getEntryRenderer: () => undefined } },
    chatContainer: { addChild() { assert.fail("metadata must not enter chat UI"); } } };
  InteractiveMode.prototype.addCustomEntryToChat.call(mode, { type: "custom", customType: LANDMARK_TYPE });
});

test("long-history replay stays stable with ordered linear matching", async t => {
  const f = fixture();
  for (let i = 0; i < 5000; i++) {
    f.add(usage(50));
    if ((i + 1) % 2000 === 0) await f.end();
  }
  const start = performance.now();
  const messages = await f.transform();
  const elapsed = performance.now() - start;
  assert.equal(marks(messages).length, 2);
  assert.equal(messages.length, 5002);
  assert.deepEqual(marks(await f.transform()), marks(messages));
  t.diagnostic(`5000-assistant native projection and transform: ${elapsed.toFixed(1)}ms (offline local observation)`);
});

test("native AgentSession tool-only completion produces one durable mark, no extra request", async () => {
  const model = { id: "fixture", name: "fixture", api: "openai-responses", provider: "offline",
    baseUrl: "http://unused.invalid", reasoning: false, input: ["text"], cost,
    contextWindow: 1_000_000, maxTokens: 1000 };
  let requests = 0;
  const received = [];
  const settings = sdk.SettingsManager.inMemory({ compaction: { enabled: false }, retry: { enabled: false } });
  const loader = new sdk.DefaultResourceLoader({
    cwd: root, agentDir: join(root, "agent"), settingsManager: settings,
    noExtensions: true, noSkills: true, noContextFiles: true, noPromptTemplates: true, noThemes: true,
    extensionFactories: [register, pi => pi.registerProvider("offline", {
      api: model.api, apiKey: "fixture", baseUrl: model.baseUrl, models: [model],
      streamSimple: (_model, context) => {
        received.push(structuredClone(context.messages));
        const first = requests++ === 0;
        const message = assistant(usage(first ? 100_000 : 1), first ?
          [{ type: "toolCall", id: "inspect", name: "token_awareness", arguments: { action: "inspect" } }] :
          [{ type: "text", text: "done" }]);
        message.stopReason = first ? "toolUse" : "stop";
        const stream = createAssistantMessageEventStream();
        queueMicrotask(() => { stream.push({ type: "done", reason: message.stopReason, message }); stream.end(message); });
        return stream;
      },
    })], systemPromptOverride: () => "Offline token landmark test.",
  });
  await loader.reload();
  assert.deepEqual(loader.getExtensions().errors, []);
  const runtime = await sdk.ModelRuntime.create({ authPath: join(root, "auth.json"),
    modelsPath: join(root, "models.json"), modelsStorePath: join(root, "models-store.json"),
    allowModelNetwork: false });
  const { session } = await sdk.createAgentSession({ cwd: root, agentDir: join(root, "agent"),
    resourceLoader: loader, modelRuntime: runtime, model, settingsManager: settings,
    sessionManager: sdk.SessionManager.inMemory(root), tools: [] });
  try {
    await session.bindExtensions({});
    await session.prompt("Run the fixture");
    assert.equal(requests, 2);
    assert.ok(JSON.stringify(received[1]).includes("Token usage landmark"));
    assert.equal(session.messages.filter(m => m.customType === LANDMARK_TYPE).length, 0);
    const entries = session.sessionManager.getBranch();
    const marker = entries.findIndex(e => e.customType === LANDMARK_TYPE);
    assert.ok(marker > entries.findIndex(e => e.type === "message" && e.message.role === "toolResult"));
    assert.equal(entries.filter(e => e.customType === LANDMARK_TYPE).length, 1);
  } finally { session.dispose(); }
});
