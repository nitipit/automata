import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import { zstdDecompressSync } from "node:zlib";

const root = process.env.FAST_TEST_ROOT;
const pkg = process.env.FAST_PI_PACKAGE;
const load = path => import(pathToFileURL(path));
const { default: register, MODE_TYPE, branchState, supportedRoute } = await load(join(root, "index.ts"));
const sdk = await load(join(pkg, "dist/index.js"));
const { Type } = createRequire(join(pkg, "package.json"))("typebox");
const { SessionManager } = sdk;
const { ExtensionRunner } = await load(join(pkg, "dist/core/extensions/runner.js"));
const { parseArgs } = await load(join(pkg, "dist/cli/args.js"));
const { createAgentSessionServices } = await load(join(pkg, "dist/core/agent-session-services.js"));
const ai = join(pkg, "../../@earendil-works/pi-ai/dist/api");
const responses = await load(join(ai, "openai-responses.js"));
const codex = await load(join(ai, "openai-codex-responses.js"));
const completions = await load(join(ai, "openai-completions.js"));
const model = (provider = "openai", api = "openai-responses", baseUrl = "https://api.openai.com/v1") => ({
  type: "chat", provider, api, baseUrl, id: "gpt-6.1-sol", name: "Offline Sol",
  reasoning: true, input: ["text"], contextWindow: 128000, maxTokens: 16384,
  cost: { input: 1, output: 2, cacheRead: 0.1, cacheWrite: 0 },
});
const codexModel = () => model("openai-codex", "openai-codex-responses", "https://chatgpt.com/backend-api");
const usage = { input: 10000, output: 5, cacheRead: 0, cacheWrite: 0, totalTokens: 10005,
  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } };
const assistant = m => ({ role: "assistant", content: [], timestamp: Date.now(),
  provider: m.provider, api: m.api, model: m.id, stopReason: "stop", usage: structuredClone(usage) });
const payload = (m = model()) => ({ model: m.id, input: [], reasoning: { effort: "high" },
  tools: [{ type: "function", name: "example" }], unrelated: 123, service_tier: "auto" });

function fixture(manager = SessionManager.inMemory(root), selected = model(), launchFlag = false) {
  const handlers = new Map();
  const flags = new Map();
  let command;
  const statuses = [];
  const notifications = [];
  register({
    on(name, fn) { const list = handlers.get(name) ?? []; list.push(fn); handlers.set(name, list); },
    appendEntry: (name, data) => manager.appendCustomEntry(name, structuredClone(data)),
    registerCommand(name, value) { assert.equal(name, "fast"); command = value; },
    registerFlag(name, value) { flags.set(name, value); },
    getFlag(name) { assert.equal(name, "fast"); return launchFlag; },
    registerTool() { assert.fail("No model-callable switching"); },
    registerProvider() { assert.fail("No provider replacement"); },
    setModel() { assert.fail("Preserve selected model"); },
    setThinkingLevel() { assert.fail("Preserve reasoning effort"); },
  });
  const ctx = { model: selected, hasUI: true, sessionManager: manager,
    ui: { setStatus(_key, value) { statuses.push(value); },
      notify(value, kind) { notifications.push({ value, kind }); } } };
  const runner = { createContext: () => ctx, extensions: [{ path: "fast-mode", handlers }],
    emitError(error) { assert.fail(JSON.stringify(error)); } };
  return {
    ctx, manager, handlers, flags, runner, statuses, notifications, command,
    async emit(name, event = {}) { for (const fn of handlers.get(name) ?? []) await fn(event, ctx); },
    async fast(args) { await command.handler(args, ctx); },
    request: body => ExtensionRunner.prototype.emitBeforeProviderRequest.call(runner, body),
    state: () => branchState(manager.getBranch()),
  };
}
async function stderr(action) {
  const output = [];
  const original = console.error;
  console.error = text => output.push(text);
  try { await action(); } finally { console.error = original; }
  return output;
}

// No accidental networking outside explicit local test stubs.
globalThis.fetch = () => assert.fail("Live HTTP requests forbidden");

test("safe off, explicit premium, syntax, immutable payload and request-only status", async () => {
  const f = fixture();
  await f.emit("session_start", { reason: "startup" });
  assert.equal(f.state().enabled, false);
  assert.equal(f.statuses.at(-1), "Fast: off");
  const original = payload();
  assert.deepEqual(await f.request(original), { ...original, service_tier: "default" });
  assert.equal(original.service_tier, "auto");
  const selected = structuredClone(f.ctx.model);
  for (const action of ["", "status", "toggle", "on extra"]) await f.fast(action);
  assert.equal(f.state().enabled, false);
  assert.equal(f.manager.getBranch().length, 0);
  assert.equal(f.notifications.at(-1).kind, "warning");
  await f.fast("ON");
  assert.equal((await f.request(original)).service_tier, "priority");
  assert.deepEqual(f.ctx.model, selected);
  assert.match(f.notifications.at(-1).value, /premium.*auxiliary/);
  assert.equal(f.statuses.at(-1), "Fast: on");
  assert.match(f.notifications.at(-1).value, /request policy on.*eligible selected route.*response tier not tracked/);
  await f.fast("off");
  assert.equal((await f.request({ ...original, service_tier: "fast" })).service_tier, "default");
  assert.deepEqual(f.command.getArgumentCompletions("o").map(item => item.value), ["on", "off"]);
  assert.equal(f.statuses.at(-1), "Fast: off");
  f.ctx.hasUI = false;
  const statusCount = f.statuses.length;
  const output = await stderr(() => f.fast("status"));
  assert.match(output[0], /request policy off.*request=default.*not tracked/);
  for (const event of ["model_select", "session_tree", "session_shutdown"]) await f.emit(event);
  assert.equal(f.statuses.length, statusCount, "no footer writes without UI");
  f.ctx.hasUI = true;
  await f.emit("session_tree");
  assert.equal(f.statuses.at(-1), "Fast: off");
  f.manager.appendCustomEntry(MODE_TYPE, { version: 1, enabled: true });
  f.ctx.model = undefined;
  await f.emit("model_select");
  assert.equal(f.statuses.at(-1), "Fast: on", "footer shows policy even on unsupported routes");
  await f.fast("status");
  assert.match(f.notifications.at(-1).value, /request policy on.*inactive.*tier not enforced.*not tracked/);
  f.manager.appendCustomEntry(MODE_TYPE, { version: 1, enabled: false });
  await f.emit("session_start", { reason: "reload" });
  assert.equal(f.statuses.at(-1), "Fast: off");
  await f.emit("session_shutdown");
  assert.equal(f.statuses.at(-1), undefined, "shutdown removes footer");
  assert.deepEqual([...f.handlers.keys()].sort(), ["before_provider_request", "model_select",
    "session_shutdown", "session_start", "session_tree"]);
  assert.deepEqual(f.flags.get("fast"), { description: f.flags.get("fast").description,
    type: "boolean", default: false });
});

// Wire policy, not a simulated proof of backend acceptance. Official Codex source:
// openai/codex@822e58cc3d666166c7446c5b1ea2e52f5d09594c
// protocol/src/config_types.rs: Fast.request_value() = priority;
// protocol/src/openai_models.rs: explicit default -> None;
// codex-api/src/common.rs: None service_tier omitted for HTTP and WebSocket.
// Exact passages and pinned links are in the extension README.
test("Codex on uses priority; off clears inherited tiers without mutating other fields", async () => {
  const m = codexModel();
  const f = fixture(undefined, m);
  await f.fast("on");
  assert.equal((await f.request(payload(m))).service_tier, "priority");
  assert.equal(f.statuses.at(-1), "Fast: on");
  assert.match(f.notifications.at(-1).value, /request=priority/);
  await f.fast("off");
  for (const tier of ["priority", "fast", "auto", "default", undefined]) {
    const original = { ...payload(m), service_tier: tier };
    const { service_tier: _removed, ...expected } = original;
    const result = await f.request(original);
    assert.deepEqual(result, expected);
    assert.equal(Object.hasOwn(result, "service_tier"), false);
    assert.equal(original.service_tier, tier);
  }
  assert.equal(f.statuses.at(-1), "Fast: off");
  assert.match(f.notifications.at(-1).value, /request=omitted \(Codex standard request\).*not tracked/);
});

test("static provider/API/endpoint guards, unknown payloads and 6.1/future IDs", async () => {
  for (const m of [model(), codexModel(), model("openai", "openai-completions"),
    { ...model(), id: "future-model", baseUrl: "https://api.openai.com/v1/" },
    { ...codexModel(), baseUrl: "https://chatgpt.com/backend-api/codex/responses/" }]) {
    assert.equal(supportedRoute(m), true);
    const f = fixture(undefined, m);
    await f.fast("on");
    assert.equal((await f.request(payload(m))).service_tier, "priority");
  }
  for (const m of [model("openrouter"), model("azure-openai"), model("openai", "anthropic-messages"),
    model("openai", "pi-virtual", ""), model("openai", "openai-codex-responses"),
    ...["http://api.openai.com/v1", "https://api.openai.com.evil.test/v1",
      "https://api.openai.com:444/v1", "https://u:p@api.openai.com/v1",
      "https://api.openai.com/v1?route=elsewhere", "https://api.openai.com/v1#other",
      "https://proxy.test/v1", "https://api.openai.com/wrong", "garbage"].map(url => model("openai", "openai-responses", url)),
    { ...codexModel(), baseUrl: "https://chatgpt.com/not-codex" }, undefined]) {
    assert.equal(supportedRoute(m), false);
    const f = fixture();
    f.ctx.model = m;
    await f.fast("off");
    const input = payload();
    assert.strictEqual(await f.request(input), input);
    assert.equal(f.statuses.at(-1), "Fast: off");
    assert.match(f.notifications.at(-1).value, /inactive.*tier not enforced.*not tracked/);
  }
  const f = fixture();
  for (const input of [null, [], "bad", {}, { model: "different", service_tier: "auto" }]) {
    assert.strictEqual(await f.request(input), input);
  }
});

test("launch flag overrides initial active branch only; absent flag preserves history", async () => {
  for (const flag of [true, "true"]) {
    const f = fixture(undefined, model(), flag);
    await f.emit("session_start", { reason: "startup" });
    assert.equal(f.state().enabled, true);
    await f.fast("off");
    for (const reason of ["reload", "new", "resume", "fork"]) await f.emit("session_start", { reason });
    assert.equal(f.state().enabled, false, "launch flag must not undo later manual off");
  }
  const saved = SessionManager.inMemory(root);
  saved.appendCustomEntry(MODE_TYPE, { version: 1, enabled: true });
  const resumed = fixture(saved);
  await resumed.emit("session_start", { reason: "startup" });
  assert.equal(resumed.state().enabled, true, "no flag preserves resumed on policy");
  saved.appendCustomEntry(MODE_TYPE, { version: 1, enabled: false });
  const override = fixture(saved, model(), true);
  await override.emit("session_start", { reason: "startup" });
  assert.equal(override.state().enabled, true, "explicit launch opt-in overrides resumed off");
  assert.equal(fixture().state().enabled, false);
});

test("native tree, fork/open/resume, raw compaction and isolated sessions", async () => {
  const manager = SessionManager.create(root, join(root, "sessions"));
  const f = fixture(manager);
  manager.appendMessage({ role: "user", content: "start", timestamp: Date.now() });
  manager.appendMessage(assistant(f.ctx.model));
  const origin = manager.getLeafId();
  await f.fast("on");
  const on = manager.getLeafId();
  await f.fast("off");
  const off = manager.getLeafId();
  manager.branch(on);
  await f.emit("session_tree");
  assert.equal(f.state().enabled, true);
  manager.branch(origin);
  await f.emit("session_tree");
  assert.equal(f.state().enabled, false);
  manager.branch(on);
  assert.ok(manager.getEntry(off), "abandoned off remains but must not override ancestry");
  const anchor = manager.appendMessage({ role: "user", content: "old", timestamp: Date.now() });
  manager.appendCompaction("summary", anchor, 1000);
  assert.equal(f.state().enabled, true);
  const path = manager.createBranchedSession(manager.getLeafId());
  const copy = fixture(SessionManager.open(path));
  await copy.emit("session_start", { reason: "fork" });
  assert.equal(copy.state().enabled, true);
  const resumed = fixture(SessionManager.open(path));
  await resumed.emit("session_start", { reason: "startup" });
  assert.equal((await resumed.request(payload())).service_tier, "priority");
  assert.equal(fixture().state().enabled, false);
  assert.equal(manager.buildSessionContext().messages.some(message => message.customType === MODE_TYPE), false);
  await f.emit("session_shutdown");
  assert.equal(f.statuses.at(-1), undefined);
  assert.equal(branchState([{ type: "custom", customType: MODE_TYPE,
    data: { version: 1, enabled: "yes" } }]).enabled, false);
});

test("native CLI parses --fast for interactive/print/JSON/RPC and explicit -e under -ne", () => {
  for (const tail of [[], ["--print"], ["--mode", "json"], ["--mode", "rpc"]]) {
    const parsed = parseArgs(["--no-extensions", "-e", join(root, "index.ts"), "--fast", ...tail,
      ...(tail.includes("rpc") ? [] : ["--", "Fixture prompt"])]);
    assert.equal(parsed.noExtensions, true);
    assert.deepEqual(parsed.extensions, [join(root, "index.ts")]);
    assert.equal(parsed.unknownFlags.get("fast"), true);
    assert.deepEqual(parsed.messages, tail.includes("rpc") ? [] : ["Fixture prompt"]);
  }
});

const terminal = (tier, id = "resp_fixture", output = []) => ({ type: "response.completed",
  response: { id, status: "completed", output, ...(tier === undefined ? {} : { service_tier: tier }),
    usage: { input_tokens: 10000, output_tokens: 5, total_tokens: 10005 } } });
const sse = events => new Response(events.map(event => `data: ${JSON.stringify(event)}\n\n`).join(""),
  { headers: { "content-type": "text/event-stream" } });
const fakeJwt = `e30.${Buffer.from(JSON.stringify({ "https://api.openai.com/auth": { chatgpt_account_id: "offline" } })).toString("base64")}.stub`;
const context = { messages: [{ role: "system", content: "Offline test", timestamp: 1 },
  { role: "user", content: "Hi", timestamp: 2 }] };

for (const [name, provider, m] of [["Responses", responses, model()], ["Codex SSE", codex, codexModel()],
  ["Chat Completions", completions, model("openai", "openai-completions")]]) {
  for (const enabled of [false, true]) {
    test(`native ${name} preserves reasoning/model/options; policy=${enabled ? "on" : "off"}`, async () => {
      const f = fixture(undefined, m);
      await f.fast(enabled ? "on" : "off");
      let sent;
      const result = await provider.streamSimple(m, context, {
        apiKey: m.provider === "openai-codex" ? fakeJwt : "offline", reasoning: "high",
        transport: "sse", maxRetries: 0, temperature: 0.2, serviceTier: "priority",
        onPayload: body => f.request(body),
        fetch: async (_url, options) => {
          const body = new Headers(options.headers).get("content-encoding") === "zstd" ?
            zstdDecompressSync(options.body).toString() : options.body;
          sent = JSON.parse(body);
          if (m.api === "openai-completions") return sse([
            { id: "offline", object: "chat.completion.chunk", model: m.id,
              choices: [{ index: 0, delta: { role: "assistant", content: "Hello" }, finish_reason: "stop" }],
              usage: { prompt_tokens: 10000, completion_tokens: 5, total_tokens: 10005 } },
          ]);
          return sse([terminal(undefined)]);
        },
      }).result();
      assert.equal(result.stopReason, "stop", result.errorMessage);
      assert.equal(sent.model, m.id);
      assert.equal(sent.service_tier, enabled ? "priority" : m.provider === "openai-codex" ? undefined : "default");
      assert.equal(Object.hasOwn(sent, "service_tier"), enabled || m.provider !== "openai-codex");
      // Responses itself suppresses temperature for reasoning models; preserve that behavior.
      assert.equal(sent.temperature, m.api === "openai-responses" ? undefined : 0.2);
      assert.equal(m.api === "openai-completions" ? sent.reasoning_effort : sent.reasoning.effort, "high");
      assert.deepEqual(f.state(), { enabled });
      assert.equal(f.manager.getBranch().length, 1, "no response record");
    });
  }
}

let sdkNumber = 0;
async function nativeSession({ warming = "off", onFetch, flag = true, customTools = [], useCodex = false } = {}) {
  const work = join(root, `sdk-${sdkNumber++}`);
  mkdirSync(work);
  const m = { ...(useCodex ? codexModel() : model()), promptCache: { short: 300 },
    cost: { input: 50, output: 2, cacheRead: 0.1, cacheWrite: 0 } };
  const sent = [];
  const settings = sdk.SettingsManager.inMemory({ compaction: { enabled: false }, retry: { enabled: false },
    cacheWarming: warming });
  const resourceLoaderOptions = {
    noExtensions: true, noSkills: true, noContextFiles: true, noPromptTemplates: true, noThemes: true,
    extensionFactories: [register, pi => pi.registerProvider(m.provider, {
      api: m.api, apiKey: useCodex ? fakeJwt : "offline", baseUrl: m.baseUrl, models: [m],
      // Test fetch adapter only; the production extension does not register providers.
      streamSimple: (actual, transcript, options) => (useCodex ? codex : responses).streamSimple(actual, transcript, {
        ...options, apiKey: useCodex ? fakeJwt : "offline", maxRetries: 0,
        transport: "sse", ...(useCodex ? { serviceTier: "priority" } : {}),
        fetch: async (_url, init) => {
          const raw = new Headers(init.headers).get("content-encoding") === "zstd" ?
            zstdDecompressSync(init.body).toString() : init.body;
          const body = JSON.parse(raw);
          const request = { body, warm: options.maxTokens === 1 };
          sent.push(request);
          return await onFetch?.(request, sent.length) ?? sse([terminal(undefined, `resp_${sent.length}`)]);
        },
      }),
    })], systemPromptOverride: () => "Offline policy test.",
  };
  const runtime = await sdk.ModelRuntime.create({ authPath: join(work, "fake-auth.json"),
    modelsPath: join(work, "models.json"), modelsStorePath: join(work, "store.json"), allowModelNetwork: false });
  // Exercise the same service flag application as native CLI, not a nonexistent loader option.
  const services = await createAgentSessionServices({ cwd: work, agentDir: join(work, "agent"),
    modelRuntime: runtime, settingsManager: settings, resourceLoaderOptions,
    extensionFlagValues: flag ? new Map([["fast", true]]) : new Map() });
  assert.deepEqual(services.diagnostics, []);
  assert.deepEqual(services.resourceLoader.getExtensions().errors, []);
  const { session } = await sdk.createAgentSession({ cwd: work, agentDir: join(work, "agent"),
    resourceLoader: services.resourceLoader, modelRuntime: runtime, model: m,
    thinkingLevel: "high", settingsManager: settings, sessionManager: SessionManager.inMemory(work),
    tools: customTools.map(tool => tool.name), customTools });
  await session.bindExtensions({});
  return { session, sent };
}
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };
async function warm(session) {
  const warmer = session._cacheWarmer;
  assert.ok(warmer.run, "native warming must actually be scheduled");
  assert.equal(warmer.evaluate(warmer.run).action, "warm", "economics must select warm, not be stubbed");
  clearTimeout(warmer.run.timer); // Accelerate only scheduling, retain native options and hook dispatch.
  await warmer.refresh(warmer.run);
}
const policyEntries = session => session.sessionManager.getBranch().filter(entry => entry.type === "custom");

test("native Codex warming uses priority on and omission off, overriding provider premium", async () => {
  const { session, sent } = await nativeSession({ warming: "idle", useCodex: true });
  try {
    await session.prompt("Seed usage");
    await warm(session);
    assert.equal(sent[0].body.service_tier, "priority");
    assert.equal(sent[1].warm, true);
    assert.equal(sent[1].body.service_tier, "priority");
    await stderr(() => session.prompt("/fast off"));
    await warm(session);
    assert.equal(sent[2].warm, true);
    assert.equal(Object.hasOwn(sent[2].body, "service_tier"), false);
    assert.equal(sent[2].body.model, "gpt-6.1-sol");
    assert.equal(sent[2].body.reasoning.effort, "high");
    await session.prompt("Future main");
    assert.equal(Object.hasOwn(sent[3].body, "service_tier"), false);
    assert.ok(policyEntries(session).every(entry => entry.customType === MODE_TYPE));
  } finally { session.dispose(); }
});

test("native SDK startup flag, command-only no requests, unchanged effort, no outcome records", async () => {
  const { session, sent } = await nativeSession();
  try {
    assert.equal(branchState(session.sessionManager.getBranch()).enabled, true);
    await session.prompt("Fixture");
    assert.equal(sent[0].body.service_tier, "priority");
    assert.equal(sent[0].body.reasoning.effort, "high");
    assert.equal(session.model.id, "gpt-6.1-sol");
    assert.equal(session.thinkingLevel, "high");
    await stderr(() => session.prompt("/fast off"));
    await session.prompt("Second fixture");
    assert.equal(sent[1].body.service_tier, "default");
    assert.equal(sent.length, 2);
    assert.ok(policyEntries(session).every(entry => entry.customType === MODE_TYPE));
  } finally { session.dispose(); }
});

test("native SDK no-flag session is isolated; reload preserves manual off despite startup opt-in", async () => {
  const first = await nativeSession();
  const second = await nativeSession({ flag: false });
  try {
    assert.equal(branchState(first.session.sessionManager.getBranch()).enabled, true);
    assert.equal(branchState(second.session.sessionManager.getBranch()).enabled, false);
    await second.session.prompt("Independent fixture");
    assert.equal(second.sent[0].body.service_tier, "default");
    await stderr(() => first.session.prompt("/fast off"));
    await first.session.reload();
    assert.equal(branchState(first.session.sessionManager.getBranch()).enabled, false);
    await first.session.prompt("After reload");
    assert.equal(first.sent[0].body.service_tier, "default");
    assert.deepEqual(policyEntries(first.session).map(entry => entry.data.enabled), [true, false]);
  } finally { first.session.dispose(); second.session.dispose(); }
});

for (const failMain of [false, true]) {
  test(`native overlapping warm deliberately follows current off policy; failed main=${failMain}`, async () => {
    const entered = deferred();
    const release = deferred();
    const { session, sent } = await nativeSession({ warming: "streaming", onFetch: async (request, index) => {
      if (index === 2 && !request.warm) { entered.resolve(); await release.promise;
        if (failMain) return new Response(JSON.stringify({ error: { message: "offline rejection" } }),
          { status: 400, headers: { "content-type": "application/json" } }); }
    } });
    try {
      await session.prompt("Seed usage");
      const main = session.prompt("Main in flight");
      await Promise.race([entered.promise, main.then(() => assert.fail("Main never reached fetch gate"))]);
      await stderr(() => session.prompt("/fast off"));
      await warm(session);
      assert.equal(sent[1].body.service_tier, "priority", "already-dispatched main is unchanged");
      assert.equal(sent[2].warm, true);
      assert.equal(sent[2].body.service_tier, "default", "future warm deliberately uses current policy");
      release.resolve(); await main;
      const lastAssistant = session.messages.filter(message => message.role === "assistant").at(-1);
      assert.equal(lastAssistant.stopReason, failMain ? "error" : "stop");
      assert.deepEqual(branchState(session.sessionManager.getBranch()), { enabled: false });
      assert.ok(policyEntries(session).every(entry => entry.customType === MODE_TYPE));
      assert.ok(session.sessionManager.getBranch().some(entry => entry.type === "usage" && entry.kind === "cache_warm"));
    } finally { release.resolve(); session.dispose(); }
  });
}

test("native idle warming keeps useful refresh and cannot leave fake pending status", async () => {
  const { session, sent } = await nativeSession({ warming: "idle" });
  try {
    await session.prompt("Seed usage");
    await warm(session);
    assert.equal(sent[1].warm, true);
    assert.equal(sent[1].body.service_tier, "priority");
    const output = await stderr(() => session.prompt("/fast status"));
    assert.match(output[0], /request policy on.*not tracked/);
    assert.doesNotMatch(output[0], /pending|observed=/);
    assert.ok(policyEntries(session).every(entry => entry.customType === MODE_TYPE));
  } finally { session.dispose(); }
});

test("real slow tool plus warm refresh preserves policy, follow-up and session metadata", async () => {
  const entered = deferred();
  const release = deferred();
  const item = { type: "function_call", id: "fc_pause", call_id: "call_pause", name: "pause", arguments: "{}" };
  const { session, sent } = await nativeSession({ warming: "streaming",
    customTools: [{ name: "pause", label: "pause", description: "Offline pause fixture",
      parameters: Type.Object({}), execute: async () => {
        entered.resolve(); await release.promise; return { content: [], details: undefined };
      } }],
    onFetch: async (_request, index) => index === 1 ? sse([
      { type: "response.output_item.added", output_index: 0, item },
      { type: "response.output_item.done", output_index: 0, item },
      terminal(undefined, "resp_tool", [item]),
    ]) : undefined,
  });
  try {
    const main = session.prompt("Use fixture");
    await Promise.race([entered.promise, main.then(() => assert.fail("Tool never entered"))]);
    await stderr(() => session.prompt("/fast off"));
    await warm(session);
    assert.equal(sent[1].warm, true);
    assert.equal(sent[1].body.service_tier, "default");
    release.resolve(); await main;
    assert.equal(sent[2].body.service_tier, "default");
    assert.ok(session.sessionManager.getBranch().some(entry => entry.type === "message" && entry.message.role === "toolResult"));
    assert.ok(policyEntries(session).every(entry => entry.customType === MODE_TYPE));
  } finally { release.resolve(); session.dispose(); }
});
