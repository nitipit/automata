import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { default: register } = await import(pathToFileURL(
  join(process.env.CONTEXT_TEST_ROOT, "context-compaction.ts"),
));

const model = {
  api: "openai-completions",
  provider: "cheap",
  id: "compact",
  name: "offline compact",
  reasoning: true,
  input: ["text"],
  contextWindow: 128000,
  maxTokens: 8192,
  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
};
const activeModel = { provider: "expensive", id: "bigger" };
const sessionManager = { getSessionId: () => "installed-session" };
let idle = true;
let pendingMessages = false;
const providerCalls = [];
let providerFailureAt;
let betweenCalls;
const calls = [];
const sent = [];
const handlers = new Map();
let tool;

const provider = {
  streamSimple(effectiveModel, context, options) {
    providerCalls.push({ effectiveModel, context, options });
    if (providerFailureAt === providerCalls.length) {
      throw new Error(`offline provider failure ${providerCalls.length}`);
    }
    return {
      result: async () => {
        const trigger = betweenCalls;
        betweenCalls = undefined;
        if (trigger) await trigger();
        return {
          role: "assistant",
          content: [{ type: "text", text: "installed offline summary" }],
          stopReason: "stop",
          usage: {
            input: 5,
            output: 7,
            cacheRead: 0,
            cacheWrite: 0,
            totalTokens: 12,
            cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
          },
        };
      },
    };
  },
};

const ctx = {
  hasUI: false,
  isIdle: () => idle,
  hasPendingMessages: () => pendingMessages,
  model: activeModel,
  thinkingLevel: "high",
  cwd: process.env.CONTEXT_TEST_ROOT,
  isProjectTrusted: () => false,
  sessionManager,
  modelRegistry: {
    find(providerName, modelId) {
      return providerName === model.provider && modelId === model.id ? model : undefined;
    },
    getProvider() { return provider; },
    async getApiKeyAndHeaders() {
      return {
        ok: true,
        apiKey: "offline-key",
        baseUrl: "https://offline.example/v1",
        headers: { "x-auth": "yes", "x-delete": null },
        env: { OFFLINE: "1" },
      };
    },
  },
  compact(options) { calls.push(options); },
};

register({
  on(name, handler) { handlers.set(name, handler); },
  registerTool(value) { tool = value; },
  sendMessage(...args) { sent.push(args); },
});

function prep({ split = false, prefixOnly = false } = {}) {
  return {
    firstKeptEntryId: "installed-kept",
    messagesToSummarize: prefixOnly ? [] : [{
      role: "user",
      content: [{ type: "text", text: "summarize this offline" }],
      timestamp: Date.now(),
    }],
    turnPrefixMessages: split ? [{
      role: "user",
      content: [{ type: "text", text: "prefix this offline" }],
      timestamp: Date.now(),
    }] : [],
    isSplitTurn: split,
    tokensBefore: 9876,
    previousSummary: undefined,
    fileOps: { read: new Set(), edited: new Set(), written: new Set() },
    settings: { enabled: true, reserveTokens: 1000, keepRecentTokens: 500 },
  };
}

function compactEvent(customInstructions = "preserve the original model's handoff guidance", prepOptions = {}, signal = new AbortController().signal) {
  return {
    customInstructions,
    preparation: prep(prepOptions),
    signal,
  };
}

function waitTick() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function guidanceBlocks(context) {
  return context.messages.at(-1).content.filter(
    (block) => block.type === "text" && block.text.includes("[Compaction handoff guidance]"),
  );
}

test("installed Pi compaction override preserves native result shape and runtime routing", { concurrency: false }, async () => {
  const result = await tool.execute(
    "installed",
    { model: "cheap/compact", customInstructions: "preserve the original model's handoff guidance" },
    undefined,
    undefined,
    ctx,
  );
  assert.equal(result.details.status, "queued");
  assert.equal(calls.length, 0);

  const settled = handlers.get("agent_settled")({}, ctx);
  assert.equal(calls.length, 1);
  assert.equal(providerCalls.length, 0);
  const firstEvent = compactEvent();
  const hookResult = await handlers.get("session_before_compact")(firstEvent, ctx);
  if (hookResult.cancel) {
    calls[0].onError(new Error("installed hook cancelled"));
    await settled;
    assert.fail(JSON.stringify(sent));
  }
  assert.equal(hookResult.cancel, undefined, JSON.stringify(hookResult));
  assert.ok(hookResult.compaction);
  calls[0].onComplete(hookResult.compaction);
  await settled;

  assert.equal(providerCalls.length, 1);
  const providerCall = providerCalls[0];
  assert.equal(guidanceBlocks(providerCall.context).length, 1);
  assert.equal(guidanceBlocks(providerCall.context)[0].text, "\n\n[Compaction handoff guidance]\npreserve the original model's handoff guidance");
  assert.equal(providerCall.effectiveModel.baseUrl, "https://offline.example/v1");
  assert.equal(providerCall.options.apiKey, "offline-key");
  assert.equal(providerCall.options.headers["x-auth"], "yes");
  assert.equal(providerCall.options.headers["x-delete"], undefined);
  assert.equal(providerCall.options.env.OFFLINE, "1");
  assert.strictEqual(providerCall.options.signal, firstEvent.signal);
  assert.equal(providerCall.options.cacheRetention, "none");
  assert.equal(typeof providerCall.options.sessionId, "string");
  assert.equal(providerCall.options.reasoning, "high");
  assert.equal(hookResult.compaction.firstKeptEntryId, "installed-kept");
  assert.equal(hookResult.compaction.tokensBefore, 9876);
  assert.deepEqual(hookResult.compaction.details, { readFiles: [], modifiedFiles: [] });
  assert.equal(hookResult.compaction.usage.output, 7);
  assert.strictEqual(ctx.model, activeModel);
  assert.equal(ctx.thinkingLevel, "high");
  assert.deepEqual(sent, []);
});

test("installed Pi custom-message API distinguishes wakeup from nextTurn", async () => {
  const { AgentSession } = await import(pathToFileURL(join(
    process.env.CONTEXT_TEST_ROOT,
    "node_modules/@earendil-works/pi-coding-agent/dist/core/agent-session.js",
  )));
  const prompts = [];
  const session = {
    isStreaming: false,
    _pendingNextTurnMessages: [],
    _runAgentPrompt: async (message) => { prompts.push(message); },
  };
  const message = { customType: "offline-continuation", content: "next action", display: false };
  await AgentSession.prototype.sendCustomMessage.call(session, message, { triggerTurn: true });
  assert.equal(prompts.length, 1);
  assert.equal(prompts[0].content, "next action");
  await AgentSession.prototype.sendCustomMessage.call(session, message, { deliverAs: "nextTurn", triggerTurn: false });
  assert.equal(prompts.length, 1);
  assert.equal(session._pendingNextTurnMessages.length, 1);
});

test("installed resume guidance triggers once or defers without a new run", { concurrency: false }, async () => {
  for (const resumeMessage of [undefined, "", "   ", "  installed continue Ω\n"]) {
    const before = sent.length;
    const params = resumeMessage === undefined ? { model: "cheap/compact" } : { model: "cheap/compact", resumeMessage };
    const result = await tool.execute(`installed-resume-${before}`, params, undefined, undefined, ctx);
    assert.equal(result.details.status, "queued");
    const settled = handlers.get("agent_settled")({}, ctx);
    const event = compactEvent("", {});
    const hookResult = await handlers.get("session_before_compact")(event, ctx);
    assert.equal(hookResult.cancel, undefined, JSON.stringify(hookResult));
    calls.at(-1).onComplete(hookResult.compaction);
    await settled;
    assert.equal(sent.length, before);
    await waitTick();
    if (resumeMessage?.trim()) {
      assert.equal(sent.at(-1)[0].content, resumeMessage);
      assert.deepEqual(sent.at(-1)[1], { triggerTurn: true });
    } else {
      assert.equal(sent.length, before);
    }
    await handlers.get("session_start")({}, ctx);
  }

  const before = sent.length;
  const deferred = await tool.execute("installed-deferred", { model: "cheap/compact", resumeMessage: "deferred installed" }, undefined, undefined, ctx);
  assert.equal(deferred.details.status, "queued");
  const settled = handlers.get("agent_settled")({}, ctx);
  const hookResult = await handlers.get("session_before_compact")(compactEvent("", {}), ctx);
  calls.at(-1).onComplete(hookResult.compaction);
  await settled;
  idle = false;
  await waitTick();
  assert.equal(sent.length, before + 1);
  assert.equal(sent.at(-1)[0].content, "deferred installed");
  assert.deepEqual(sent.at(-1)[1], { deliverAs: "nextTurn", triggerTurn: false });
  idle = true;
});

test("installed native split history and prefix each receive guidance once", { concurrency: false }, async () => {
  const before = providerCalls.length;
  const original = prep({ split: true });
  const result = await tool.execute("installed-split", { model: "cheap/compact", customInstructions: "split guide" }, undefined, undefined, ctx);
  assert.equal(result.details.status, "queued");
  const settled = handlers.get("agent_settled")({}, ctx);
  const hookResult = await handlers.get("session_before_compact")({ ...compactEvent("split guide", { split: true }), preparation: original }, ctx);
  assert.equal(hookResult.cancel, undefined, JSON.stringify(hookResult));
  const newCalls = providerCalls.slice(before);
  assert.equal(newCalls.length, 2);
  const originalPrompts = newCalls.map((call) => call.context.messages.at(-1).content[0].text);
  assert.equal(originalPrompts[0].includes("split guide"), false);
  assert.equal(originalPrompts[1].includes("split guide"), false);
  assert.equal(originalPrompts[0].split("summarize this offline").length - 1, 1);
  assert.equal(originalPrompts[1].split("prefix this offline").length - 1, 1);
  for (const call of newCalls) {
    assert.equal(guidanceBlocks(call.context).length, 1);
    assert.equal(guidanceBlocks(call.context)[0].text, "\n\n[Compaction handoff guidance]\nsplit guide");
  }
  assert.equal(original.messagesToSummarize[0].content[0].text, "summarize this offline");
  assert.equal(hookResult.compaction.summary.includes("Turn Context (split turn)"), true);
  calls.at(-1).onComplete(hookResult.compaction);
  await settled;
});

test("installed native prefix-only split performs one guided request", { concurrency: false }, async () => {
  const before = providerCalls.length;
  const result = await tool.execute("installed-prefix", { model: "cheap/compact", customInstructions: "prefix guide" }, undefined, undefined, ctx);
  assert.equal(result.details.status, "queued");
  const settled = handlers.get("agent_settled")({}, ctx);
  const hookResult = await handlers.get("session_before_compact")(compactEvent("prefix guide", { split: true, prefixOnly: true }), ctx);
  assert.equal(hookResult.cancel, undefined, JSON.stringify(hookResult));
  assert.equal(providerCalls.slice(before).length, 1);
  assert.equal(guidanceBlocks(providerCalls.at(-1).context).length, 1);
  calls.at(-1).onComplete(hookResult.compaction);
  await settled;
});

test("installed native first and second provider errors cancel without fallback", { concurrency: false }, async () => {
  for (const offset of [1, 2]) {
    const before = providerCalls.length;
    providerFailureAt = before + offset;
    const result = await tool.execute(`installed-error-${offset}`, { model: "cheap/compact", customInstructions: "error guide" }, undefined, undefined, ctx);
    assert.equal(result.details.status, "queued");
    const settled = handlers.get("agent_settled")({}, ctx);
    const hookResult = await handlers.get("session_before_compact")(compactEvent("error guide", { split: true }), ctx);
    assert.equal(hookResult.cancel, true);
    assert.equal(hookResult.compaction, undefined);
    assert.equal(providerCalls.length - before, offset);
    calls.at(-1).onError(new Error("Compaction cancelled"));
    await settled;
    assert.match(sent.at(-1)[0].content, /offline provider failure/);
    providerFailureAt = undefined;
  }
});

test("installed abort or session reset between split calls prevents the second launch", { concurrency: false }, async () => {
  for (const mode of ["abort", "reset"]) {
    const before = providerCalls.length;
    const controller = new AbortController();
    const result = await tool.execute(`installed-${mode}`, { model: "cheap/compact", customInstructions: "between guide" }, undefined, undefined, ctx);
    assert.equal(result.details.status, "queued");
    const settled = handlers.get("agent_settled")({}, ctx);
    betweenCalls = mode === "abort"
      ? () => controller.abort()
      : () => handlers.get("session_tree")({}, ctx);
    const hookResult = await handlers.get("session_before_compact")(
      compactEvent("between guide", { split: true }, controller.signal),
      ctx,
    );
    assert.equal(hookResult.cancel, true);
    assert.equal(providerCalls.length - before, 1);
    assert.equal(hookResult.compaction, undefined);
    calls.at(-1).onError(new Error("Compaction cancelled"));
    await settled;
  }
});
