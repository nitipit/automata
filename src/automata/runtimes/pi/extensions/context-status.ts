import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

export const COMPACTION_PLAN_TYPE = "automata-compaction-plan";
const REQUEST_OWNER = "automata-context-status:request-local";

/** Used-context thresholds, before the separately configured native Pi guardrails. */
export const COMPACTION_PLANNING_TOKENS: Readonly<Record<string, number>> = {
  "openai/gpt-6-astra": 230_000,
  "openai/gpt-6.1-sol": 400_000,
  "openai/gpt-6.2-astra": 230_000,
  "openai/gpt-6.2-sol": 400_000,
  "openai/gpt-6.1-terra": 400_000,
  "openai/gpt-6-luna": 800_000,
};
type ContextSource = Pick<ExtensionContext, "getContextUsage" | "model">;

export interface ContextStatus {
  tokens: number | null;
  contextWindow: number | null;
  planningThresholdTokens: number | null;
  planningRequired: boolean;
  provider: string | null;
  model: string | null;
}

function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** Pi projects current usage; it is not the exact final serialized request size. */
export function readContextStatus(source: ContextSource): ContextStatus {
  const usage = source.getContextUsage();
  const reportedWindow = finite(usage?.contextWindow);
  const modelWindow = finite(source.model?.contextWindow);
  const contextWindow = reportedWindow !== null && reportedWindow > 0 ? reportedWindow
    : modelWindow !== null && modelWindow > 0 ? modelWindow : null;
  const rawTokens = finite(usage?.tokens);
  const tokens = rawTokens !== null && rawTokens >= 0 ? rawTokens : null;
  const provider = source.model?.provider ?? null;
  const model = source.model?.id ?? null;
  const planningThresholdTokens = provider && model
    ? COMPACTION_PLANNING_TOKENS[`${provider}/${model}`] ?? null : null;
  return {
    tokens, contextWindow, planningThresholdTokens,
    planningRequired: tokens !== null && planningThresholdTokens !== null && tokens >= planningThresholdTokens,
    provider, model,
  };
}

function count(value: number | null): string {
  return value === null ? "unknown" : Math.round(value).toLocaleString("en-US");
}
function modelText(status: ContextStatus): string {
  return status.provider && status.model ? `${status.provider}/${status.model}` : "unknown";
}

export function formatContextStatus(status: ContextStatus): string {
  return [
    "Context status",
    `Usage: ${count(status.tokens)} / ${count(status.contextWindow)} tokens`,
    `Compaction planning threshold: ${status.planningThresholdTokens === null ? "not configured" : `${count(status.planningThresholdTokens)} tokens used`}`,
    `Compaction planning required: ${status.planningRequired ? "yes" : status.tokens === null ? "unknown" : "no"}`,
    `Working model: ${modelText(status)}`,
    "Usage is a projection, not an exact final request size.",
  ].join("\n");
}

export default function (pi: ExtensionAPI) {
  pi.on("context", (event, ctx) => {
    const status = readContextStatus(ctx);
    // One current request-local notice, never persisted or queued. Also strip our
    // legacy pressure notice if a caller reuses an already transformed message list.
    const messages = event.messages.filter(
      (message) => message.role !== "custom" ||
        ![COMPACTION_PLAN_TYPE, "automata-context-pressure"].includes(message.customType) ||
        !message.details || typeof message.details !== "object" ||
        !("owner" in message.details) || message.details.owner !== REQUEST_OWNER,
    );
    if (status.planningRequired) messages.push({
      role: "custom", customType: COMPACTION_PLAN_TYPE,
      content: [
        `Compaction planning required: ${modelText(status)} is using ${count(status.tokens)} tokens (planning threshold ${count(status.planningThresholdTokens)}).`,
        "Plan a compaction break now: name the nearest suitable task boundary in the coming turns, preserve continuity, then call context_compact before starting another substantial work unit or large input.",
        "Finish only the small in-flight step needed to reach that boundary; do not defer indefinitely. This is a requirement to plan now, not to compact mid-operation. Keep native Pi auto-compaction as the fallback.",
      ].join("\n"),
      display: false, timestamp: Date.now(),
      details: { owner: REQUEST_OWNER, status },
    });
    return { messages };
  });

  pi.registerCommand("context-status", {
    description: "Show projected context usage, compaction planning threshold, and working model.",
    handler: async (_args, ctx) => {
      const formatted = formatContextStatus(readContextStatus(ctx));
      if (ctx.hasUI) ctx.ui.notify(formatted, "info");
      else if (ctx.mode === "print") console.log(formatted);
    },
  });
  pi.registerTool({
    name: "context_status", label: "Context Status",
    description: "Read projected current context tokens, model window, compaction planning threshold and working provider/model. The projection is not the exact final request size.",
    promptSnippet: "Read projected context usage and compaction planning threshold",
    promptGuidelines: ["Use context_status only when a manual diagnostic would inform the next step. When a compaction planning notice arrives, immediately plan a compaction break at the nearest suitable boundary in the coming turns; do not wait for native Pi auto-compaction."],
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
      const status = readContextStatus(ctx);
      return { content: [{ type: "text", text: formatContextStatus(status) }], details: status };
    },
  });
}
