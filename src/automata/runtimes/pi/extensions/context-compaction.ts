import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import {
  compact as nativeCompact,
  convertToLlm,
  serializeConversation,
  type SessionBeforeCompactEvent,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

export const CONTEXT_COMPACTION_MESSAGE_TYPE = "automata-context-compaction";

interface PendingCompaction {
  id: number;
  customInstructions?: string;
  resumeMessage?: string;
  model: string;
  thinking?: ExtensionContext["thinkingLevel"];
  sessionId: string;
  generation: number;
}

interface ActiveCompaction {
  request: PendingCompaction;
  context: ExtensionContext;
  agentEpoch: number;
  failure?: Error;
  invalidated?: boolean;
  terminal?: boolean;
}

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

function notify(
  ctx: ExtensionContext,
  message: string,
  level: "info" | "error",
): void {
  if (ctx.hasUI) ctx.ui.notify(message, level);
}

function optionalText(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0 ? value : undefined;
}

function describeModel(model: { provider: string; id: string }): string {
  return `${model.provider}/${model.id}`;
}

function parseModelChoice(
  ctx: ExtensionContext,
  choice: string,
) {
  const value = choice.trim();
  const separator = value.indexOf("/");
  if (separator <= 0 || separator === value.length - 1) {
    throw new Error(
      `Invalid compaction model "${choice}". Choose a model as provider/model (for example, openai-codex/gpt-5.6-luna).`,
    );
  }

  const provider = value.slice(0, separator);
  const id = value.slice(separator + 1);
  const model = ctx.modelRegistry.find(provider, id);
  if (!model) {
    throw new Error(
      `Compaction model "${value}" is unavailable in the current runtime. ` +
        "Choose an authenticated model explicitly; no fallback was attempted.",
    );
  }

  return { provider, id, model };
}

function mergeRuntimeHeaders(...sources: unknown[]): Record<string, string> | undefined {
  const merged: Record<string, string> = {};
  for (const source of sources) {
    if (!source || typeof source !== "object") continue;
    for (const [name, value] of Object.entries(source)) {
      const existing = Object.keys(merged).find(
        (candidate) => candidate.toLowerCase() === name.toLowerCase(),
      );
      if (existing) delete merged[existing];
      if (typeof value === "string") merged[name] = value;
    }
  }
  return Object.keys(merged).length > 0 ? merged : undefined;
}

function mergeRuntimeEnv(...sources: unknown[]): Record<string, string> | undefined {
  const merged: Record<string, string> = {};
  for (const source of sources) {
    if (!source || typeof source !== "object") continue;
    for (const [name, value] of Object.entries(source)) {
      if (typeof value === "string") merged[name] = value;
    }
  }
  return Object.keys(merged).length > 0 ? merged : undefined;
}

// Best-effort prompt overhead; provider tokenization can still differ.
const COMPACTION_PROMPT_OVERHEAD_TOKENS = 2048;

function estimateCompactionInputTokens(
  messages: unknown[],
  previousSummary?: string,
  customInstructions?: string,
): number {
  let serialized: string;
  try {
    serialized = serializeConversation(convertToLlm(messages as any));
  } catch (error) {
    throw new Error(`Unable to estimate compaction context safely: ${asError(error).message}`);
  }
  const extraCharacters = (previousSummary?.length ?? 0) + (customInstructions?.length ?? 0);
  return Math.ceil((serialized.length + extraCharacters) / 4) + COMPACTION_PROMPT_OVERHEAD_TOKENS;
}

function validateCompactionBudget(event: SessionBeforeCompactEvent, model: any): void {
  const preparation = event.preparation;
  const contextWindow = model?.contextWindow;
  const maxTokens = model?.maxTokens;
  const reserveTokens = preparation.settings?.reserveTokens;
  if (!Number.isFinite(contextWindow) || contextWindow <= 0) {
    throw new Error("The selected compaction model has no usable context window; no fallback was attempted.");
  }
  if (!Number.isFinite(maxTokens) || maxTokens <= 0) {
    throw new Error("The selected compaction model has no usable output-token limit; no fallback was attempted.");
  }
  if (!Number.isFinite(reserveTokens) || reserveTokens <= 0) {
    throw new Error("The compaction reserve-token budget is unavailable; no fallback was attempted.");
  }
  if (!Array.isArray(model.input) || !model.input.includes("text")) {
    throw new Error("The selected compaction model does not support text input; no fallback was attempted.");
  }
  if (!Array.isArray(preparation.messagesToSummarize) || !Array.isArray(preparation.turnPrefixMessages)) {
    throw new Error("The compaction preparation has unknown message segments; no fallback was attempted.");
  }
  if (preparation.previousSummary !== undefined && typeof preparation.previousSummary !== "string") {
    throw new Error("The previous compaction summary is not valid text; no fallback was attempted.");
  }
  if (event.customInstructions !== undefined && typeof event.customInstructions !== "string") {
    throw new Error("Compaction instructions are not valid text; no fallback was attempted.");
  }
  const split = preparation.isSplitTurn && preparation.turnPrefixMessages.length > 0;

  const historyOutputTokens = Math.min(Math.floor(0.8 * reserveTokens), maxTokens);
  const prefixOutputTokens = Math.min(Math.floor(0.5 * reserveTokens), maxTokens);
  if (historyOutputTokens <= 0 || (split && prefixOutputTokens <= 0)) {
    throw new Error("The compaction output budget is too small for the selected model; no fallback was attempted.");
  }

  if (!split || preparation.messagesToSummarize.length > 0) {
    const historyInputTokens = estimateCompactionInputTokens(
      preparation.messagesToSummarize,
      preparation.previousSummary,
      event.customInstructions,
    );
    if (historyInputTokens + historyOutputTokens >= contextWindow) {
      throw new Error(
        `The best-effort history summary estimate (${historyInputTokens} input + ${historyOutputTokens} output) exceeds the selected model context window (${contextWindow}); no fallback was attempted.`,
      );
    }
  }
  if (split) {
    const prefixInputTokens = estimateCompactionInputTokens(
      preparation.turnPrefixMessages,
      undefined,
      event.customInstructions,
    );
    if (prefixInputTokens + prefixOutputTokens >= contextWindow) {
      throw new Error(
        `The best-effort split-turn prefix estimate (${prefixInputTokens} input + ${prefixOutputTokens} output) exceeds the selected model context window (${contextWindow}); no fallback was attempted.`,
      );
    }
  }
}

const COMPACTION_GUIDANCE_LABEL = "\n\n[Compaction handoff guidance]\n";

function addCompactionGuidance(context: any, guidance: string | undefined): any {
  if (!guidance) return context;
  if (!context || typeof context !== "object" || !Array.isArray(context.messages) || context.messages.length === 0) {
    throw new Error("The native summary request had no usable message context for handoff guidance.");
  }

  const messages = context.messages.slice();
  const finalMessage = messages[messages.length - 1];
  if (!finalMessage || typeof finalMessage !== "object" || finalMessage.role !== "user") {
    throw new Error("The native summary request did not end with a user message for handoff guidance.");
  }
  if (typeof finalMessage.content === "string") {
    messages[messages.length - 1] = {
      ...finalMessage,
      content: [
        { type: "text", text: finalMessage.content },
        { type: "text", text: `${COMPACTION_GUIDANCE_LABEL}${guidance}` },
      ],
    };
  } else if (Array.isArray(finalMessage.content)) {
    messages[messages.length - 1] = {
      ...finalMessage,
      content: [
        ...finalMessage.content,
        { type: "text", text: `${COMPACTION_GUIDANCE_LABEL}${guidance}` },
      ],
    };
  } else {
    throw new Error("The native summary request had unusable user content for handoff guidance.");
  }

  return { ...context, messages };
}

function createRuntimeStream(
  ctx: ExtensionContext,
  model: any,
  auth: any,
  guidance: string | undefined,
  isCurrentRequest: () => boolean,
  signal: AbortSignal,
) {
  const provider = ctx.modelRegistry.getProvider(model.provider);
  if (!provider?.streamSimple) {
    throw new Error(
      `Provider "${model.provider}" has no simple streaming adapter for compaction; no fallback was attempted.`,
    );
  }

  return (requestModel: any, context: any, options: any) => {
    if (signal.aborted) {
      throw new Error("Compaction was cancelled before the summary request started.");
    }
    if (!isCurrentRequest()) {
      throw new Error("Compaction was cancelled because its session is no longer current.");
    }
    const effectiveModel = auth.baseUrl
      ? { ...requestModel, baseUrl: auth.baseUrl }
      : requestModel;
    return provider.streamSimple(effectiveModel, addCompactionGuidance(context, guidance), {
      ...options,
      apiKey: options?.apiKey ?? auth.apiKey,
      headers: mergeRuntimeHeaders(auth.headers, options?.headers),
      env: mergeRuntimeEnv(auth.env, options?.env),
    });
  };
}

function failClosed(
  active: ActiveCompaction,
  error: unknown,
): { cancel: true } {
  const failure = asError(error);
  active.failure = failure;
  return { cancel: true };
}

export default function (pi: ExtensionAPI) {
  let nextRequestId = 1;
  let lifecycleGeneration = 0;
  let pending: PendingCompaction | undefined;
  let active: ActiveCompaction | undefined;
  let compactionInProgress = false;
  let agentEpoch = 0;
  let scheduledContinuation: {
    request: PendingCompaction;
    context: ExtensionContext;
    sessionId: string;
    generation: number;
    agentEpoch: number;
    timer?: ReturnType<typeof setTimeout>;
    cancelled?: boolean;
    dispatched?: boolean;
  } | undefined;

  const reportContinuationError = (ctx: ExtensionContext, error: unknown): void => {
    try {
      notify(ctx, `Context compaction continuation guidance was suppressed: ${asError(error).message}`, "error");
    } catch {
      // A notification failure must not escape or change compaction outcome.
    }
  };

  const cancelScheduledContinuation = (): void => {
    if (!scheduledContinuation) return;
    scheduledContinuation.cancelled = true;
    if (scheduledContinuation.timer !== undefined) clearTimeout(scheduledContinuation.timer);
    scheduledContinuation = undefined;
  };

  const isContinuationCurrent = (candidate: NonNullable<typeof scheduledContinuation>): boolean => {
    if (scheduledContinuation !== candidate || candidate.cancelled || candidate.dispatched) return false;
    try {
      return candidate.generation === lifecycleGeneration &&
        candidate.context.sessionManager.getSessionId() === candidate.sessionId;
    } catch {
      return false;
    }
  };

  const dispatchContinuation = (candidate: NonNullable<typeof scheduledContinuation>): void => {
    if (!isContinuationCurrent(candidate)) return;
    candidate.dispatched = true;
    scheduledContinuation = undefined;

    let deferred: boolean;
    try {
      deferred = candidate.agentEpoch !== agentEpoch ||
        !candidate.context.isIdle() ||
        candidate.context.hasPendingMessages();
    } catch (error) {
      candidate.cancelled = true;
      reportContinuationError(candidate.context, error);
      return;
    }

    try {
      pi.sendMessage(
        {
          customType: CONTEXT_COMPACTION_MESSAGE_TYPE,
          content: candidate.request.resumeMessage!,
          display: false,
          details: {
            status: deferred ? "resume_deferred" : "resume",
            requestId: candidate.request.id,
          },
        },
        deferred ? { deliverAs: "nextTurn", triggerTurn: false } : { triggerTurn: true },
      );
      if (deferred) {
        notify(candidate.context, "Compaction continuation guidance deferred until the next user prompt; no extra turn was started.", "info");
      }
    } catch (error) {
      reportContinuationError(candidate.context, error);
    }
  };

  const scheduleContinuation = (ctx: ExtensionContext, run: ActiveCompaction): void => {
    const resumeMessage = run.request.resumeMessage;
    if (!resumeMessage || run.request.generation !== lifecycleGeneration) return;
    let sessionId: string;
    try {
      sessionId = ctx.sessionManager.getSessionId();
      if (sessionId !== run.request.sessionId) return;
    } catch (error) {
      reportContinuationError(ctx, error);
      return;
    }
    const candidate: NonNullable<typeof scheduledContinuation> = {
      request: run.request,
      context: ctx,
      sessionId: run.request.sessionId,
      generation: run.request.generation,
      agentEpoch: run.agentEpoch,
    };
    scheduledContinuation = candidate;
    candidate.timer = setTimeout(() => {
      candidate.timer = undefined;
      dispatchContinuation(candidate);
    }, 0);
  };

  const reset = (): void => {
    cancelScheduledContinuation();
    lifecycleGeneration += 1;
    pending = undefined;
    if (active) {
      // Keep ownership until the old ctx.compact callback settles. This lets the
      // session_before_compact hook cancel instead of falling through to Pi's
      // expensive native summary after a session change.
      active.invalidated = true;
    } else {
      compactionInProgress = false;
    }
  };

  const isCurrent = (candidate: ActiveCompaction): boolean => {
    if (
      active !== candidate ||
      candidate.invalidated ||
      candidate.request.generation !== lifecycleGeneration
    ) {
      return false;
    }
    try {
      return candidate.context.sessionManager.getSessionId() === candidate.request.sessionId;
    } catch {
      return false;
    }
  };

  pi.on("session_start", reset);
  pi.on("session_tree", reset);
  pi.on("session_shutdown", reset);
  pi.on("agent_start", () => {
    agentEpoch += 1;
  });

  pi.on("session_compact", (_event, ctx) => {
    if (!pending || compactionInProgress) return;

    const requestId = pending.id;
    pending = undefined;
    notify(
      ctx,
      `Context compaction request ${requestId} was satisfied by another compaction.`,
      "info",
    );
  });

  pi.on("session_before_compact", async (event, ctx) => {
    const request = active;
    // No owned deferred request means this is ordinary Pi compaction; leave it
    // untouched. Once owned work is in progress, every identity check below is
    // fail-closed so stale sessions cannot fall through to Pi's default model.
    if (!request || !compactionInProgress) return;

    try {
      if (request.invalidated || request.request.generation !== lifecycleGeneration) {
        throw new Error("Compaction was cancelled because the session changed.");
      }
      if (ctx.sessionManager.getSessionId() !== request.request.sessionId) {
        throw new Error("Compaction was cancelled because its session identity changed.");
      }
      if (event.signal.aborted) {
        throw new Error("Compaction was cancelled before the selected model started.");
      }

      const selected = parseModelChoice(ctx, request.request.model);
      const auth = await ctx.modelRegistry.getApiKeyAndHeaders(selected.model);
      if (!auth.ok) throw new Error(auth.error);
      validateCompactionBudget(event, selected.model);
      const guidance = event.customInstructions === "" ? undefined : event.customInstructions;
      if (!isCurrent(request) || event.signal.aborted) {
        throw new Error("Compaction was cancelled because its session is no longer current.");
      }

      // The public compact() helper preserves Pi's preparation, split-turn, file-op,
      // usage, and session-entry behavior. ExtensionContext does not expose the
      // AgentSession stream/retry callback, so this adapter uses the effective
      // provider's streamSimple with ModelRuntime-resolved auth/baseUrl and one
      // request. Do not describe this as operationally identical to host retries.
      const streamFn = createRuntimeStream(
        ctx,
        selected.model,
        auth,
        guidance,
        () => isCurrent(request),
        event.signal,
      );
      const effectiveModel = auth.baseUrl
        ? { ...selected.model, baseUrl: auth.baseUrl }
        : selected.model;
      const result = await nativeCompact(
        event.preparation,
        effectiveModel,
        auth.apiKey,
        mergeRuntimeHeaders(auth.headers),
        undefined,
        event.signal,
        request.request.thinking ?? ctx.thinkingLevel,
        streamFn,
        auth.env,
      );

      if (!isCurrent(request)) {
        throw new Error("Compaction was cancelled because its session changed during summarization.");
      }
      if (event.signal.aborted) {
        throw new Error("Compaction was cancelled while generating the summary.");
      }

      return { compaction: result };
    } catch (error) {
      return failClosed(request, error);
    }
  });

  pi.on("agent_settled", async (_event, ctx) => {
    if (!pending || compactionInProgress) return;
    if (!ctx.isIdle() || ctx.hasPendingMessages()) return;

    const request = pending;
    pending = undefined;
    compactionInProgress = true;
    const run: ActiveCompaction = { request, context: ctx, agentEpoch };
    active = run;
    notify(
      ctx,
      `Context compaction ${request.id} started using ${request.model}.`,
      "info",
    );

    await new Promise<void>((resolve) => {
      let finished = false;
      const finish = (): void => {
        if (finished) return;
        finished = true;
        resolve();
      };

      const fail = (error: unknown): void => {
        if (run.terminal) {
          finish();
          return;
        }
        run.terminal = true;
        if (!isCurrent(run)) {
          if (active === run) {
            active = undefined;
            compactionInProgress = false;
          }
          finish();
          return;
        }

        const failure = run.failure ?? asError(error);
        compactionInProgress = false;
        active = undefined;
        try {
          notify(
            ctx,
            `Context compaction ${request.id} failed: ${failure.message}`,
            "error",
          );
        } catch (notifyError) {
          reportContinuationError(ctx, notifyError);
        }
        try {
          pi.sendMessage(
            {
              customType: CONTEXT_COMPACTION_MESSAGE_TYPE,
              content:
                `The requested context compaction failed after the agent settled: ${failure.message}. ` +
                "Do not retry automatically; reassess whether compaction is still useful and resolve the selected model failure.",
              display: false,
              details: {
                status: "failed",
                requestId: request.id,
                error: failure.message,
              },
            },
            { deliverAs: "nextTurn" },
          );
        } catch (sendError) {
          reportContinuationError(ctx, sendError);
        } finally {
          finish();
        }
      };

      const complete = (): void => {
        if (run.terminal) {
          finish();
          return;
        }
        run.terminal = true;
        if (!isCurrent(run)) {
          if (active === run) {
            active = undefined;
            compactionInProgress = false;
          }
          finish();
          return;
        }

        compactionInProgress = false;
        active = undefined;
        try {
          notify(ctx, `Context compaction ${request.id} completed.`, "info");
        } catch (notifyError) {
          reportContinuationError(ctx, notifyError);
        }
        finish();
        scheduleContinuation(ctx, run);
      };

      try {
        ctx.compact({
          customInstructions: request.customInstructions,
          onComplete: complete,
          onError: fail,
        });
      } catch (error) {
        fail(error);
      }
    });
  });

  pi.registerTool({
    name: "context_compact",
    label: "Compact Context",
    description:
      "Queue one intentional Pi context compaction after the current agent run fully settles, using a selected model or the current model when omitted.",
    promptSnippet:
      "Compact context at a stable boundary after preserving durable task state",
    promptGuidelines: [
      "Treat context signals as observations, not automatic compaction commands. Call context_compact only when compaction is materially useful at a stable boundary.",
      "Preserve durable decisions, constraints, ownership, validation state, and next steps before calling. Use context_compact as the only final tool action when practical.",
      "Pass an approved provider/model preference when present; otherwise omit model to use the current model without asking. A selected model failure never triggers fallback.",
      "Pass thinking when a compaction-specific thinking level is requested; omit it to inherit the session level. This does not change the working session's settings.",
      "Use resumeMessage only for brief post-compaction continuation guidance; empty or whitespace-only values are omitted and nonblank text is preserved verbatim.",
      "Do not call immediately after a successful compaction or merely because usage is unknown unless the user explicitly requests it.",
    ],
    parameters: Type.Object(
      {
        customInstructions: Type.Optional(
          Type.String({
            description:
              "Optional brief focus preserved verbatim in every native summary request. Prefer concise guidance; keep durable state outside this field.",
          }),
        ),
        model: Type.Optional(Type.String({
          description:
            "Optional provider/model. When omitted, captures the current model at queue time. Explicitly selecting the current model is allowed; unavailable selections never fall back.",
        })),
        thinking: Type.Optional(Type.String({
          enum: ["off", "minimal", "low", "medium", "high", "xhigh", "max"],
          description:
            "Optional compaction-only thinking level: off, minimal, low, medium, high, xhigh, or max. Omitted inherits the session level at execution. Does not change working settings; provider/model reasoning support still applies.",
        })),
        resumeMessage: Type.Optional(Type.String({
          description:
            "Optional brief continuation guidance dispatched at most once after successful compaction: wakes an idle unchanged session, or defers to nextTurn if other work intervenes. Whitespace-only values are omitted; nonblank text is preserved verbatim.",
        })),
      },
      { additionalProperties: false },
    ),
    async execute(_toolCallId, params, signal, _onUpdate, ctx) {
      signal?.throwIfAborted();

      if (compactionInProgress) {
        return {
          content: [{ type: "text", text: "Context compaction is already in progress." }],
          details: { status: "in_progress" },
          terminate: true,
        };
      }

      if (pending) {
        return {
          content: [
            {
              type: "text",
              text:
                `Context compaction request ${pending.id} is already queued; ` +
                "the existing request was kept unchanged.",
            },
          ],
          details: { status: "already_queued", requestId: pending.id },
          terminate: true,
        };
      }

      const thinkingLevels = ["off", "minimal", "low", "medium", "high", "xhigh", "max"];
      if (params.thinking !== undefined && !thinkingLevels.includes(params.thinking)) {
        return {
          content: [{ type: "text", text: "Invalid compaction thinking level; no request was queued." }],
          details: { status: "invalid_thinking", thinking: params.thinking },
          terminate: true,
        };
      }

      let model: ReturnType<typeof parseModelChoice>;
      try {
        const choice = params.model ?? (ctx.model ? describeModel(ctx.model) : undefined);
        if (choice === undefined) {
          throw new Error("No current model is available for compaction; no fallback was attempted.");
        }
        model = parseModelChoice(ctx, choice);
      } catch (error) {
        const failure = asError(error);
        return {
          content: [{ type: "text", text: failure.message }],
          details: {
            status: "model_unavailable",
            error: failure.message,
          },
          terminate: true,
        };
      }

      pending = {
        id: nextRequestId,
        customInstructions: params.customInstructions,
        resumeMessage: optionalText(params.resumeMessage),
        model: `${model.provider}/${model.id}`,
        thinking: params.thinking as PendingCompaction["thinking"],
        sessionId: ctx.sessionManager.getSessionId(),
        generation: lifecycleGeneration,
      };
      nextRequestId += 1;

      return {
        content: [
          {
            type: "text",
            text: `Queued context compaction request ${pending.id} using ${pending.model} ` +
              `(thinking: ${pending.thinking ?? "inherited"}). ` +
              "It will run after the agent fully settles.",
          },
        ],
        details: {
          status: "queued",
          requestId: pending.id,
          model: pending.model,
          thinking: pending.thinking ?? "inherited",
        },
        terminate: true,
      };
    },
  });
}
