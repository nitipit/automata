import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { default: register } = await import(pathToFileURL(
  join(process.env.CONTEXT_TEST_ROOT, "context-compaction.ts"),
));

const model = {
  provider: "cheap",
  id: "compact",
  input: ["text"],
  contextWindow: 128000,
  maxTokens: 8192,
};
const activeModel = { ...model, provider: "expensive", id: "bigger" };

function preparation() {
  return {
    firstKeptEntryId: "kept-entry",
    messagesToSummarize: [{ role: "user", content: [{ type: "text", text: "old" }] }],
    turnPrefixMessages: [],
    isSplitTurn: false,
    tokensBefore: 1234,
    previousSummary: "previous",
    fileOps: { read: new Set(), edited: new Set() },
    settings: { enabled: true, reserveTokens: 1000, keepRecentTokens: 500 },
  };
}

function fixture({
  auth = { ok: true, apiKey: "cheap-key", env: { TEST: "1" } },
  runtimeModel = model,
  sendThrows = false,
} = {}) {
  const handlers = new Map();
  const calls = [];
  const sent = [];
  let tool;
  let currentSessionId = "session-1";
  let throwOnSessionId = false;
  const sessionManager = {
    getSessionId() {
      if (throwOnSessionId) throw new Error("session getter failed");
      return currentSessionId;
    },
    setSessionId(value) { currentSessionId = value; },
    throwOnGet(value) { throwOnSessionId = value; },
  };
  const ctx = {
    hasUI: false,
    isIdle: () => true,
    hasPendingMessages: () => false,
    model: activeModel,
    thinkingLevel: "high",
    cwd: process.env.CONTEXT_TEST_ROOT,
    isProjectTrusted: () => false,
    sessionManager,
    modelRegistry: {
      find(provider, id) {
        return provider === runtimeModel.provider && id === runtimeModel.id ? runtimeModel
          : provider === activeModel.provider && id === activeModel.id ? activeModel : undefined;
      },
      getProvider() {
        return {
          streamSimple(effectiveModel, context, options) {
            globalThis.__providerCalls ??= [];
            globalThis.__providerCalls.push({ effectiveModel, context, options });
            if (globalThis.__providerFailAtCall === globalThis.__providerCalls.length) {
              throw new Error(`offline provider failure ${globalThis.__providerCalls.length}`);
            }
            return {
              result: async () => {
                const trigger = globalThis.__triggerBetweenCalls;
                globalThis.__triggerBetweenCalls = undefined;
                if (trigger) await trigger();
                return {
                  role: "assistant",
                  content: [{ type: "text", text: "offline summary" }],
                  stopReason: "stop",
                  usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2,
                    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
                };
              },
            };
          },
        };
      },
      async getApiKeyAndHeaders() {
        return typeof auth === "function" ? await auth() : auth;
      },
    },
    compact(options) { calls.push(options); },
  };
  register({
    on(name, handler) { handlers.set(name, handler); },
    registerTool(value) { tool = value; },
    sendMessage(...args) {
      if (sendThrows) throw new Error("continuation delivery failed");
      sent.push(args);
    },
  });
  return {
    tool,
    ctx,
    calls,
    sent,
    sessionManager,
    handlers,
    emit: async (name, event = {}) => handlers.get(name)(event, ctx),
    request: (params = {}) => tool.execute("test", params, undefined, undefined, ctx),
  };
}

function compactEvent(overrides = {}) {
  return {
    customInstructions: "focus on the handoff",
    preparation: preparation(),
    signal: new AbortController().signal,
    ...overrides,
  };
}

function splitPreparation({ prefixOnly = false } = {}) {
  return {
    ...preparation(),
    isSplitTurn: true,
    messagesToSummarize: prefixOnly ? [] : preparation().messagesToSummarize,
    turnPrefixMessages: [{ role: "user", content: [{ type: "text", text: "prefix" }] }],
  };
}

function guidanceBlocks(context) {
  const finalMessage = context.messages.at(-1);
  return finalMessage.content.filter(
    (block) => block.type === "text" && block.text.includes("[Compaction handoff guidance]"),
  );
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  Object.freeze(value);
  for (const child of Object.values(value)) deepFreeze(child);
  return value;
}

function waitTick() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

async function completeNative(f, overrides = {}) {
  const result = await f.emit("session_before_compact", compactEvent(overrides));
  assert.equal(result.cancel, undefined);
  assert.ok(result.compaction);
  f.calls[0].onComplete(result.compaction);
}

test("instruction and explicit model schemas are unconstrained strings", () => {
  const schema = fixture().tool.parameters;
  assert.equal(schema.properties.customInstructions.type, "string");
  assert.equal(schema.properties.customInstructions.minLength, undefined);
  assert.equal(schema.properties.customInstructions.maxLength, undefined);
  assert.equal(schema.properties.model.type, "string");
  assert.ok(!schema.required?.includes("model"));
});

test("uses the native compaction result only after settling and preserves settings", async () => {
  const f = fixture();
  const result = await f.request({ model: "cheap/compact", customInstructions: "focus" });
  assert.equal(result.details.status, "queued");
  assert.equal(f.calls.length, 0);

  const settled = f.emit("agent_settled");
  assert.equal(f.calls.length, 1);
  assert.equal((await f.request({ model: "cheap/compact" })).details.status, "in_progress");
  await completeNative(f);
  await settled;

  const nativeCall = globalThis.__nativeCompactions.at(-1);
  assert.strictEqual(nativeCall.preparation.firstKeptEntryId, "kept-entry");
  assert.equal(nativeCall.preparation.tokensBefore, 1234);
  assert.equal(nativeCall.customInstructions, undefined);
  const guidanceBlocks = globalThis.__providerCalls.at(-1).context.messages.at(-1).content
    .filter((block) => block.type === "text" && block.text.includes("[Compaction handoff guidance]"));
  assert.equal(guidanceBlocks.length, 1);
  assert.equal(guidanceBlocks[0].text, "\n\n[Compaction handoff guidance]\nfocus on the handoff");
  assert.equal(nativeCall.model, model);
  assert.equal(nativeCall.thinkingLevel, "high");
  assert.equal(nativeCall.env.TEST, "1");
  assert.strictEqual(f.ctx.model, activeModel);
  assert.equal(f.ctx.thinkingLevel, "high");
  assert.deepEqual(f.sent, []);
});

test("keeps the first queued request and prevents concurrent compaction", async () => {
  const f = fixture();
  const first = await f.request({ model: "cheap/compact", customInstructions: "first" });
  const duplicate = await f.request({ model: "cheap/compact", customInstructions: "second" });
  assert.equal(duplicate.details.status, "already_queued");
  assert.equal(duplicate.details.requestId, first.details.requestId);
  const settled = f.emit("agent_settled");
  assert.equal(f.calls.length, 1);
  await completeNative(f, { customInstructions: "first" });
  await settled;
  assert.equal((await f.request({ model: "cheap/compact" })).details.status, "queued");
});

test("waits while busy or while messages are pending", async () => {
  const f = fixture();
  await f.request({ model: "cheap/compact" });
  f.ctx.isIdle = () => false;
  await f.emit("agent_settled");
  f.ctx.isIdle = () => true;
  f.ctx.hasPendingMessages = () => true;
  await f.emit("agent_settled");
  assert.equal(f.calls.length, 0);
  f.ctx.hasPendingMessages = () => false;
  const settled = f.emit("agent_settled");
  await completeNative(f);
  await settled;
});

for (const event of ["session_start", "session_tree", "session_shutdown"]) {
  test(`${event} clears a queued request`, async () => {
    const f = fixture();
    await f.request({ model: "cheap/compact" });
    await f.emit(event);
    await f.emit("agent_settled");
    assert.equal(f.calls.length, 0);
  });
}

test("another compaction satisfies a queued request without starting native compaction", async () => {
  const f = fixture();
  await f.request({ model: "cheap/compact" });
  await f.emit("session_compact");
  await f.emit("agent_settled");
  assert.equal(f.calls.length, 0);
  assert.equal(f.sent.length, 0);
});

test("resumes once after success and preserves nonblank text verbatim", async () => {
  for (const resumeMessage of [undefined, "", "   ", "  continue Ω\n"]) {
    const f = fixture();
    const params = resumeMessage === undefined ? {} : { resumeMessage };
    await f.request({ model: "cheap/compact", ...params });
    const settled = f.emit("agent_settled");
    const result = await f.emit("session_before_compact", compactEvent({ customInstructions: "" }));
    assert.equal(result.cancel, undefined);
    f.calls[0].onComplete(result.compaction);
    await settled;
    assert.deepEqual(f.sent, []);
    await waitTick();
    if (resumeMessage?.trim()) {
      assert.equal(f.sent.length, 1);
      assert.equal(f.sent[0][0].content, resumeMessage);
      assert.deepEqual(f.sent[0][1], { triggerTurn: true });
    } else {
      assert.deepEqual(f.sent, []);
    }
  }
});

test("defers resume guidance without starting a turn when work intervenes", async () => {
  for (const mode of ["busy", "pending", "agent_start"]) {
    const f = fixture();
    await f.request({ model: "cheap/compact", resumeMessage: "defer me" });
    const settled = f.emit("agent_settled");
    const result = await f.emit("session_before_compact", compactEvent({ customInstructions: "" }));
    f.calls[0].onComplete(result.compaction);
    if (mode === "busy") f.ctx.isIdle = () => false;
    if (mode === "pending") f.ctx.hasPendingMessages = () => true;
    if (mode === "agent_start") await f.emit("agent_start");
    await settled;
    await waitTick();
    assert.equal(f.sent.length, 1);
    assert.equal(f.sent[0][0].content, "defer me");
    assert.deepEqual(f.sent[0][1], { deliverAs: "nextTurn", triggerTurn: false });
  }
});

test("does not resume after failure, abort, reset, duplicate callbacks, or delivery throw", async () => {
  const failure = fixture();
  await failure.request({ model: "cheap/compact", resumeMessage: "no failure resume" });
  const failureSettled = failure.emit("agent_settled");
  globalThis.__nativeCompactionFailure = new Error("provider failure");
  const failureResult = await failure.emit("session_before_compact", compactEvent({ customInstructions: "" }));
  assert.equal(failureResult.cancel, true);
  failure.calls[0].onError(new Error("cancelled"));
  await failureSettled;
  delete globalThis.__nativeCompactionFailure;
  await waitTick();
  assert.equal(failure.sent.some(([message]) => message.content === "no failure resume"), false);

  for (const mode of ["abort", "reset"]) {
    const f = fixture();
    await f.request({ model: "cheap/compact", resumeMessage: "no stale resume" });
    const settled = f.emit("agent_settled");
    const controller = new AbortController();
    if (mode === "abort") controller.abort(); else await f.emit("session_tree");
    const result = await f.emit("session_before_compact", compactEvent({ customInstructions: "", signal: controller.signal }));
    assert.equal(result.cancel, true);
    f.calls[0].onError(new Error("cancelled"));
    await settled;
    await waitTick();
    assert.equal(f.sent.some(([message]) => message.content === "no stale resume"), false);
  }

  const duplicate = fixture();
  await duplicate.request({ model: "cheap/compact", resumeMessage: "once only" });
  const duplicateSettled = duplicate.emit("agent_settled");
  const duplicateResult = await duplicate.emit("session_before_compact", compactEvent({ customInstructions: "" }));
  duplicate.calls[0].onComplete(duplicateResult.compaction);
  duplicate.calls[0].onError(new Error("late error"));
  duplicate.calls[0].onComplete(duplicateResult.compaction);
  await duplicateSettled;
  await waitTick();
  assert.equal(duplicate.sent.length, 1);

  const throwing = fixture({ sendThrows: true });
  await throwing.request({ model: "cheap/compact", resumeMessage: "delivery throw" });
  const throwingSettled = throwing.emit("agent_settled");
  const throwingResult = await throwing.emit("session_before_compact", compactEvent({ customInstructions: "" }));
  throwing.calls[0].onComplete(throwingResult.compaction);
  await throwingSettled;
  await waitTick();
  assert.deepEqual(throwing.sent, []);
});

test("completion notification reentrancy cannot rebind or duplicate continuation", async () => {
  for (const mode of ["reset", "session_id", "duplicate", "notify_throw"]) {
    const f = fixture();
    await f.request({ resumeMessage: "continue safely" });
    const settled = f.emit("agent_settled");
    const result = await f.emit("session_before_compact", compactEvent());
    f.ctx.hasUI = true;
    f.ctx.ui = { notify(message) {
      if (!message.includes("completed")) return;
      if (mode === "reset") f.emit("session_shutdown");
      if (mode === "session_id") f.ctx.sessionManager.getSessionId = () => "replacement";
      if (mode === "duplicate") {
        f.calls[0].onComplete(result.compaction);
        f.calls[0].onError(new Error("reentrant error"));
      }
      if (mode === "notify_throw") throw new Error("UI unavailable");
    } };
    f.calls[0].onComplete(result.compaction);
    await settled;
    await waitTick();
    assert.equal(f.sent.length, ["duplicate", "notify_throw"].includes(mode) ? 1 : 0);
    assert.equal(f.sent.some(([message]) => message.details?.status === "failed"), false);
  }
});

test("post-success lifecycle changes cancel scheduled continuation and deferral is visible", async () => {
  for (const event of ["session_start", "session_tree", "session_shutdown"]) {
    const f = fixture();
    await f.request({ resumeMessage: "never stale" });
    const settled = f.emit("agent_settled");
    const result = await f.emit("session_before_compact", compactEvent());
    f.calls[0].onComplete(result.compaction);
    await settled;
    await f.emit(event);
    await waitTick();
    assert.deepEqual(f.sent, []);
  }
  const f = fixture();
  const notices = [];
  f.ctx.hasUI = true;
  f.ctx.ui = { notify: (message) => notices.push(message) };
  await f.request({ resumeMessage: "keep this next action" });
  const settled = f.emit("agent_settled");
  const result = await f.emit("session_before_compact", compactEvent());
  f.calls[0].onComplete(result.compaction);
  f.ctx.hasPendingMessages = () => true;
  await settled;
  await waitTick();
  assert.equal(f.sent.length, 1);
  assert.deepEqual(f.sent[0][1], { deliverAs: "nextTurn", triggerTurn: false });
  assert.ok(notices.some((message) => message.includes("deferred until the next user prompt")));
});

test("fails closed on unavailable authentication and does not fall back", async () => {
  const nativeCount = globalThis.__nativeCompactions.length;
  const f = fixture({ auth: { ok: false, error: "credentials unavailable" } });
  await f.request({ model: "cheap/compact" });
  const settled = f.emit("agent_settled");
  const result = await f.emit("session_before_compact", compactEvent());
  assert.equal(result.cancel, true);
  f.calls[0].onError(new Error("Compaction cancelled"));
  await settled;
  assert.equal(globalThis.__nativeCompactions.length, nativeCount);
  assert.match(f.sent[0][0].content, /credentials unavailable/);
  assert.deepEqual(f.sent[0][1], { deliverAs: "nextTurn" });
});

test("fails closed on native provider errors and aborts", async () => {
  const f = fixture();
  await f.request({ model: "cheap/compact" });
  const settled = f.emit("agent_settled");
  globalThis.__nativeCompactionFailure = new Error("provider context limit");
  const result = await f.emit("session_before_compact", compactEvent());
  assert.equal(result.cancel, true);
  f.calls[0].onError(new Error("Compaction cancelled"));
  await settled;
  assert.match(f.sent.at(-1)[0].content, /provider context limit/);

  delete globalThis.__nativeCompactionFailure;
  const next = fixture();
  await next.request({ model: "cheap/compact" });
  const nextSettled = next.emit("agent_settled");
  const controller = new AbortController();
  controller.abort();
  const aborted = await next.emit("session_before_compact", compactEvent({ signal: controller.signal }));
  assert.equal(aborted.cancel, true);
  next.calls[0].onError(new Error("Compaction cancelled"));
  await nextSettled;
  assert.match(next.sent[0][0].content, /cancelled/);
});

test("fails closed for unknown or too-small selected-model budgets", async () => {
  for (const runtimeModel of [
    { ...model, contextWindow: undefined },
    { ...model, maxTokens: undefined },
    { ...model, contextWindow: NaN },
    { ...model, maxTokens: Infinity },
    { ...model, input: ["image"] },
    { ...model, contextWindow: 2048 },
  ]) {
    const nativeCount = globalThis.__nativeCompactions.length;
    const f = fixture({ runtimeModel });
    await f.request({ model: "cheap/compact" });
    const settled = f.emit("agent_settled");
    const result = await f.emit("session_before_compact", compactEvent());
    assert.equal(result.cancel, true);
    assert.equal(globalThis.__nativeCompactions.length, nativeCount);
    f.calls[0].onError(new Error("Compaction cancelled"));
    await settled;
    assert.match(f.sent.at(-1)[0].content, /no fallback was attempted/);
  }
});

test("preflight accounts for previous summaries and custom guidance", async () => {
  const baseline = fixture({ runtimeModel: { ...model, contextWindow: 3000 } });
  await baseline.request({ model: "cheap/compact" });
  const baselineSettled = baseline.emit("agent_settled");
  const baselineResult = await baseline.emit(
    "session_before_compact",
    compactEvent({
      customInstructions: "",
      preparation: { ...preparation(), previousSummary: undefined },
    }),
  );
  assert.equal(baselineResult.cancel, undefined);
  baseline.calls[0].onComplete(baselineResult.compaction);
  await baselineSettled;

  for (const preparationOverride of [
    { previousSummary: "previous ".repeat(500) },
    { previousSummary: undefined },
  ]) {
    const f = fixture({ runtimeModel: { ...model, contextWindow: 3000 } });
    await f.request({ model: "cheap/compact" });
    const settled = f.emit("agent_settled");
    const result = await f.emit(
      "session_before_compact",
      compactEvent({
        customInstructions: preparationOverride.previousSummary ? "" : "custom ".repeat(500),
        preparation: { ...preparation(), ...preparationOverride },
      }),
    );
    assert.equal(result.cancel, true);
    f.calls[0].onError(new Error("Compaction cancelled"));
    await settled;
    assert.match(f.sent.at(-1)[0].content, /best-effort .* estimate/);
  }
});

test("preserves whitespace guidance and omits empty guidance", async () => {
  const f = fixture();
  await f.request({ model: "cheap/compact", customInstructions: "   " });
  const settled = f.emit("agent_settled");
  assert.equal(f.calls[0].customInstructions, "   ");
  await completeNative(f, { customInstructions: "   " });
  await settled;
  assert.equal(globalThis.__providerCalls.at(-1).context.messages.at(-1).content.at(-1).text, "\n\n[Compaction handoff guidance]\n   ");

  const empty = fixture();
  await empty.request({ model: "cheap/compact", customInstructions: "" });
  const emptySettled = empty.emit("agent_settled");
  assert.equal(empty.calls[0].customInstructions, "");
  await completeNative(empty, { customInstructions: "" });
  await emptySettled;
  assert.equal(guidanceBlocks(globalThis.__providerCalls.at(-1).context).length, 0);
});

test("supports string user content and fails closed on unexpected final shapes", async () => {
  globalThis.__nativeContextOverride = {
    systemPrompt: "shape-system",
    messages: [{ role: "user", content: "original prompt", timestamp: 1 }],
  };
  const stringFixture = fixture();
  await stringFixture.request({ model: "cheap/compact", customInstructions: "string guide" });
  const stringSettled = stringFixture.emit("agent_settled");
  const stringResult = await stringFixture.emit(
    "session_before_compact",
    compactEvent({ customInstructions: "string guide" }),
  );
  assert.equal(stringResult.cancel, undefined);
  assert.equal(guidanceBlocks(globalThis.__providerCalls.at(-1).context).length, 1);
  stringFixture.calls[0].onComplete(stringResult.compaction);
  await stringSettled;
  delete globalThis.__nativeContextOverride;

  for (const invalidContext of [
    { systemPrompt: "bad", messages: [{ role: "assistant", content: [] }] },
    { systemPrompt: "bad", messages: [{ role: "user", content: {} }] },
  ]) {
    globalThis.__nativeContextOverride = invalidContext;
    const f = fixture();
    await f.request({ model: "cheap/compact", customInstructions: "shape guide" });
    const settled = f.emit("agent_settled");
    const result = await f.emit(
      "session_before_compact",
      compactEvent({ customInstructions: "shape guide" }),
    );
    assert.equal(result.cancel, true);
    f.calls[0].onError(new Error("Compaction cancelled"));
    await settled;
  }
  delete globalThis.__nativeContextOverride;
});

test("injects guidance exactly once into history and split summary requests", async () => {
  const f = fixture();
  await f.request({ model: "cheap/compact", customInstructions: "guide Ω" });
  const settled = f.emit("agent_settled");
  const result = await f.emit(
    "session_before_compact",
    compactEvent({ customInstructions: "guide Ω", preparation: splitPreparation() }),
  );
  assert.equal(result.cancel, undefined);
  assert.equal(f.calls[0].onComplete !== undefined, true);
  const nativeCall = globalThis.__nativeCompactions.at(-1);
  assert.equal(nativeCall.customInstructions, undefined);
  assert.equal(nativeCall.streamCalls.length, 2);
  const providerCalls = globalThis.__providerCalls.slice(-2);
  for (const providerCall of providerCalls) {
    assert.equal(guidanceBlocks(providerCall.context).length, 1);
    assert.equal(guidanceBlocks(providerCall.context)[0].text, "\n\n[Compaction handoff guidance]\nguide Ω");
    assert.equal(providerCall.context.systemPrompt.endsWith("system"), true);
  }
  f.calls[0].onComplete(result.compaction);
  await settled;
});

test("injects guidance once for a prefix-only split request", async () => {
  const f = fixture();
  await f.request({ model: "cheap/compact", customInstructions: "prefix guide" });
  const settled = f.emit("agent_settled");
  const result = await f.emit(
    "session_before_compact",
    compactEvent({ customInstructions: "prefix guide", preparation: splitPreparation({ prefixOnly: true }) }),
  );
  assert.equal(result.cancel, undefined);
  const nativeCall = globalThis.__nativeCompactions.at(-1);
  assert.equal(nativeCall.streamCalls.length, 1);
  assert.equal(guidanceBlocks(globalThis.__providerCalls.at(-1).context).length, 1);
  f.calls[0].onComplete(result.compaction);
  await settled;
});

test("does not mutate a reused native context and cancels first or second request errors", async () => {
  globalThis.__reuseNativeContext = true;
  globalThis.__freezeNativeContext = deepFreeze;
  const f = fixture();
  await f.request({ model: "cheap/compact", customInstructions: "stable guide" });
  const settled = f.emit("agent_settled");
  const result = await f.emit(
    "session_before_compact",
    compactEvent({ customInstructions: "stable guide", preparation: deepFreeze(splitPreparation()) }),
  );
  assert.equal(result.cancel, undefined);
  const nativeCall = globalThis.__nativeCompactions.at(-1);
  assert.strictEqual(nativeCall.streamCalls[0].context, nativeCall.streamCalls[1].context);
  assert.equal(guidanceBlocks(nativeCall.streamCalls[0].context).length, 0);
  assert.equal(guidanceBlocks(globalThis.__providerCalls.at(-2).context).length, 1);
  assert.equal(guidanceBlocks(globalThis.__providerCalls.at(-1).context).length, 1);
  f.calls[0].onComplete(result.compaction);
  await settled;
  delete globalThis.__reuseNativeContext;
  delete globalThis.__freezeNativeContext;

  const stale = fixture();
  await stale.request({ model: "cheap/compact", customInstructions: "stale guide" });
  const staleSettled = stale.emit("agent_settled");
  const providerCount = globalThis.__providerCalls.length;
  globalThis.__triggerBetweenCalls = () => stale.emit("session_tree");
  const staleResult = await stale.emit(
    "session_before_compact",
    compactEvent({ customInstructions: "stale guide", preparation: splitPreparation() }),
  );
  assert.equal(staleResult.cancel, true);
  assert.equal(globalThis.__providerCalls.length - providerCount, 1);
  stale.calls[0].onError(new Error("Compaction cancelled"));
  await staleSettled;

  for (const failOffset of [1, 2]) {
    const errorFixture = fixture();
    await errorFixture.request({ model: "cheap/compact", customInstructions: "error guide" });
    const errorSettled = errorFixture.emit("agent_settled");
    globalThis.__providerFailAtCall = globalThis.__providerCalls.length + failOffset;
    const errorResult = await errorFixture.emit(
      "session_before_compact",
      compactEvent({ customInstructions: "error guide", preparation: splitPreparation() }),
    );
    assert.equal(errorResult.cancel, true);
    errorFixture.calls[0].onError(new Error("Compaction cancelled"));
    await errorSettled;
    assert.match(errorFixture.sent.at(-1)[0].content, /offline provider failure/);
    delete globalThis.__providerFailAtCall;
  }
});

test("checks the split-turn prefix budget independently", async () => {
  const nativeCount = globalThis.__nativeCompactions.length;
  const f = fixture({ runtimeModel: { ...model, contextWindow: 2900 } });
  await f.request({ model: "cheap/compact" });
  const settled = f.emit("agent_settled");
  const result = await f.emit(
    "session_before_compact",
    compactEvent({
      customInstructions: "",
      preparation: {
        ...preparation(),
        isSplitTurn: true,
        turnPrefixMessages: [{ role: "user", content: [{ type: "text", text: "prefix ".repeat(400) }] }],
      },
    }),
  );
  assert.equal(result.cancel, true);
  assert.equal(globalThis.__nativeCompactions.length, nativeCount);
  f.calls[0].onError(new Error("Compaction cancelled"));
  await settled;
  assert.match(f.sent.at(-1)[0].content, /split-turn prefix/);
});

test("guidance alone can tip the split-prefix budget after history fits", async () => {
  const sharedPreparation = {
    ...preparation(),
    isSplitTurn: true,
    turnPrefixMessages: [{ role: "user", content: [{ type: "text", text: "prefix ".repeat(230) }] }],
  };
  const baseline = fixture({ runtimeModel: { ...model, contextWindow: 3000 } });
  await baseline.request({ model: "cheap/compact" });
  const baselineSettled = baseline.emit("agent_settled");
  const baselineResult = await baseline.emit(
    "session_before_compact",
    compactEvent({ customInstructions: undefined, preparation: sharedPreparation }),
  );
  assert.equal(baselineResult.cancel, undefined);
  baseline.calls[0].onComplete(baselineResult.compaction);
  await baselineSettled;

  const guided = fixture({ runtimeModel: { ...model, contextWindow: 3000 } });
  const nativeCount = globalThis.__nativeCompactions.length;
  const guidance = "g".repeat(320);
  await guided.request({ model: "cheap/compact", customInstructions: guidance });
  const guidedSettled = guided.emit("agent_settled");
  const guidedResult = await guided.emit(
    "session_before_compact",
    compactEvent({ customInstructions: guidance, preparation: sharedPreparation }),
  );
  assert.equal(guidedResult.cancel, true);
  assert.equal(globalThis.__nativeCompactions.length, nativeCount);
  guided.calls[0].onError(new Error("Compaction cancelled"));
  await guidedSettled;
  assert.match(guided.sent.at(-1)[0].content, /split-turn prefix/);
});

test("routes through the effective provider stream with auth endpoint and header normalization", async () => {
  const f = fixture({
    auth: {
      ok: true,
      apiKey: "override-key",
      baseUrl: "https://offline.example/v1",
      headers: { "x-auth": "yes", "x-delete": null },
      env: { ROUTE: "override" },
    },
  });
  await f.request({ model: "cheap/compact" });
  const settled = f.emit("agent_settled");
  await completeNative(f);
  await settled;

  const call = globalThis.__providerCalls.at(-1);
  assert.equal(call.effectiveModel.baseUrl, "https://offline.example/v1");
  assert.equal(call.options.apiKey, "override-key");
  assert.equal(call.options.headers["x-auth"], "yes");
  assert.equal(call.options.headers["x-delete"], undefined);
  assert.equal(call.options.env.ROUTE, "override");
  assert.deepEqual(globalThis.__nativeStreamResult.content, [
    { type: "text", text: "offline summary" },
  ]);
});

test("session identity mismatch cancels the owned stale request", async () => {
  const nativeCount = globalThis.__nativeCompactions.length;
  const f = fixture();
  await f.request({ model: "cheap/compact" });
  const settled = f.emit("agent_settled");
  await f.emit("session_shutdown");
  f.sessionManager.setSessionId("session-2");
  const result = await f.emit("session_before_compact", compactEvent());
  assert.equal(result.cancel, true);
  assert.equal(globalThis.__nativeCompactions.length, nativeCount);
  f.calls[0].onError(new Error("Compaction cancelled"));
  await settled;
  assert.deepEqual(f.sent, []);
});

test("throwing session identity getter cancels instead of falling through", async () => {
  const nativeCount = globalThis.__nativeCompactions.length;
  const f = fixture();
  await f.request({ model: "cheap/compact" });
  const settled = f.emit("agent_settled");
  f.sessionManager.throwOnGet(true);
  const result = await f.emit("session_before_compact", compactEvent());
  assert.equal(result.cancel, true);
  assert.equal(globalThis.__nativeCompactions.length, nativeCount);
  f.calls[0].onError(new Error("Compaction cancelled"));
  await settled;
  assert.deepEqual(f.sent, []);
});

test("reset before the hook cancels ownership instead of falling back", async () => {
  const nativeCount = globalThis.__nativeCompactions.length;
  const f = fixture();
  await f.request({ model: "cheap/compact" });
  const settled = f.emit("agent_settled");
  await f.emit("session_tree");
  const result = await f.emit("session_before_compact", compactEvent());
  assert.equal(result.cancel, true);
  assert.equal(globalThis.__nativeCompactions.length, nativeCount);
  f.calls[0].onError(new Error("Compaction cancelled"));
  await settled;
  assert.deepEqual(f.sent, []);
});

test("reset during auth cancels before selecting a provider request", async () => {
  let release;
  const authReady = new Promise((resolve) => { release = resolve; });
  const nativeCount = globalThis.__nativeCompactions.length;
  const f = fixture({ auth: () => authReady });
  await f.request({ model: "cheap/compact" });
  const settled = f.emit("agent_settled");
  const hook = f.emit("session_before_compact", compactEvent());
  await Promise.resolve();
  await f.emit("session_tree");
  release({ ok: true, apiKey: "late-key", env: {} });
  const result = await hook;
  assert.equal(result.cancel, true);
  assert.equal(globalThis.__nativeCompactions.length, nativeCount);
  f.calls[0].onError(new Error("Compaction cancelled"));
  await settled;
  assert.deepEqual(f.sent, []);
});

test("reset during summary prevents a stale compaction commit", async () => {
  let release;
  globalThis.__nativeCompactionGate = new Promise((resolve) => { release = resolve; });
  const f = fixture();
  await f.request({ model: "cheap/compact" });
  const settled = f.emit("agent_settled");
  const hook = f.emit("session_before_compact", compactEvent());
  await Promise.resolve();
  await f.emit("session_tree");
  release();
  const result = await hook;
  assert.equal(result.cancel, true);
  f.calls[0].onError(new Error("Compaction cancelled"));
  await settled;
  delete globalThis.__nativeCompactionGate;
  assert.deepEqual(f.sent, []);
});

test("rejects malformed and unavailable explicit choices without falling back", async () => {
  for (const [params, status] of [
    [{ model: "" }, "model_unavailable"],
    [{ model: "bad" }, "model_unavailable"],
    [{ model: "missing/model" }, "model_unavailable"],

  ]) {
    const f = fixture();
    const result = await f.request(params);
    assert.equal(result.terminate, true);
    assert.equal(result.details.status, status);
    assert.equal(f.calls.length, 0);
  }
});


test("omitted and explicit current model compact without changing working settings", async () => {
  for (const params of [{}, { model: "expensive/bigger" }]) {
    const f = fixture();
    const result = await f.request(params);
    assert.equal(result.details.status, "queued");
    assert.equal(result.details.model, "expensive/bigger");
    const settled = f.emit("agent_settled");
    globalThis.__providerCalls = [];
    await completeNative(f);
    await settled;
    assert.equal(globalThis.__providerCalls[0].effectiveModel.id, "bigger");
    assert.equal(f.ctx.model, activeModel);
    assert.equal(f.ctx.thinkingLevel, "high");
  }
});

test("default selection is pinned at queue time and missing current model fails closed", async () => {
  const f = fixture();
  await f.request();
  f.ctx.model = model;
  const settled = f.emit("agent_settled");
  globalThis.__providerCalls = [];
  await completeNative(f);
  await settled;
  assert.equal(globalThis.__providerCalls[0].effectiveModel.id, "bigger");
  assert.equal(f.ctx.model, model);
  const missing = fixture();
  missing.ctx.model = undefined;
  assert.equal((await missing.request()).details.status, "model_unavailable");
  assert.equal(missing.calls.length, 0);
});

test("default model authentication failure cancels without another selection", async () => {
  const f = fixture({ auth: { ok: false, error: "offline auth failure" } });
  await f.request();
  const settled = f.emit("agent_settled");
  globalThis.__providerCalls = [];
  assert.deepEqual(await f.emit("session_before_compact", compactEvent()), { cancel: true });
  f.calls[0].onError(new Error("cancelled"));
  await settled;
  assert.equal(globalThis.__providerCalls.length, 0);
  assert.equal(f.sent.length, 1);
});
