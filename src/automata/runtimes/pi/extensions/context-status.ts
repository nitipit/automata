import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

export const RUNTIME_PRESSURE_TYPE = "automata-context-pressure";
export const CONTEXT_BUCKET_SIZE = 50_000;
export const PRESSURE_SIGNAL_THRESHOLDS = [50, 75, 80, 85, 90, 95] as const;
export type PressureBand = "unknown" | "low" | "moderate" | "high" | "critical";
type ContextSource = Pick<ExtensionContext, "getContextUsage" | "model">;

export interface ContextStatus {
  tokens: number | null;
  contextWindow: number | null;
  percent: number | null;
  pressure: PressureBand;
  provider: string | null;
  model: string | null;
}

function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function pressureBandForPercent(percent: number | null | undefined): PressureBand {
  if (percent == null || !Number.isFinite(percent)) return "unknown";
  if (percent < 50) return "low";
  if (percent < 75) return "moderate";
  if (percent < 90) return "high";
  return "critical";
}

export function pressureThresholdForPercent(percent: number | null | undefined): number | null {
  if (percent == null || !Number.isFinite(percent)) return null;
  return PRESSURE_SIGNAL_THRESHOLDS.findLast((threshold) => percent >= threshold) ?? null;
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
  const reportedPercent = finite(usage?.percent);
  const percent = tokens !== null && contextWindow !== null
    ? tokens / contextWindow * 100
    : reportedPercent !== null && reportedPercent >= 0 ? reportedPercent : null;
  return {
    tokens, contextWindow, percent,
    pressure: tokens === null || percent === null ? "unknown" : pressureBandForPercent(percent),
    provider: source.model?.provider ?? null,
    model: source.model?.id ?? null,
  };
}

function count(value: number | null): string {
  return value === null ? "unknown" : Math.round(value).toLocaleString("en-US");
}
function percentText(value: number | null): string {
  return value === null ? "unknown" : `${value.toFixed(1).replace(/\.0$/, "")}%`;
}
function modelText(status: ContextStatus): string {
  return status.provider && status.model ? `${status.provider}/${status.model}` : "unknown";
}

export function formatContextStatus(status: ContextStatus): string {
  return [
    "Context status",
    `Usage: ${count(status.tokens)} / ${count(status.contextWindow)} tokens (${percentText(status.percent)})`,
    `Pressure: ${status.pressure}`,
    `Working model: ${modelText(status)}`,
    "Usage is a projection, not an exact final request size.",
  ].join("\n");
}

export default function (pi: ExtensionAPI) {
  let highWaterBucket = 0;
  let provider: string | null = null;
  let model: string | null = null;
  let window: number | null = null;
  const reset = () => { highWaterBucket = 0; provider = model = null; window = null; };
  pi.on("session_start", reset);
  pi.on("session_tree", reset);
  // Only confirmed success re-arms; failed or aborted compaction is not a reset.
  pi.on("session_compact", reset);

  pi.on("context", (event, ctx) => {
    const status = readContextStatus(ctx);
    // Missing identity components are not transitions. Retain the last known
    // values independently so a real provider, model or window change still rearms.
    if (status.tokens !== null) {
      const nextProvider = status.provider || null;
      const nextModel = status.model || null;
      const nextWindow = status.contextWindow;
      if ((provider && nextProvider && provider !== nextProvider) ||
          (model && nextModel && model !== nextModel) ||
          (window !== null && nextWindow !== null && window !== nextWindow)) highWaterBucket = 0;
      provider = nextProvider ?? provider;
      model = nextModel ?? model;
      window = nextWindow ?? window;
    }
    const bucket = status.tokens === null ? 0 : Math.floor(status.tokens / CONTEXT_BUCKET_SIZE);
    const observeUsage = bucket > highWaterBucket;
    // At-most-once attempt: context events have no request ID or delivery ACK. An
    // error/abort after this transform does not re-arm the bucket. Session reset
    // or a higher bucket permits a later observation, without guessing correlation.
    if (observeUsage) highWaterBucket = bucket;
    const remind = status.pressure !== "unknown" && status.percent !== null && status.percent >= 80;
    const lines: string[] = [];
    if (observeUsage) {
      lines.push(`Context usage: ${count(status.tokens)} / ${count(status.contextWindow)} tokens`);
      lines.push(`Working model: ${modelText(status)}`);
    }
    if (remind) {
      lines.push(observeUsage
        ? `Context pressure: ${percentText(status.percent)}.`
        : `Context pressure: ${percentText(status.percent)} (${count(status.tokens)} / ${count(status.contextWindow)} tokens).`);
      lines.push((status.percent ?? 0) >= 90
        ? "Urgent compaction reminder: preserve the minimum durable checkpoint and use the earliest safe boundary before substantial new work."
        : "Compaction reminder: finish the current coherent unit, preserve durable state, and use the next stable boundary.");
      lines.push("Apply the existing compaction policy and preferences. Do not interrupt an unfinished operation; this observation does not itself authorize or run compaction.");
    }
    const messages = event.messages.filter(
      (message) => message.role !== "custom" || message.customType !== RUNTIME_PRESSURE_TYPE ||
        !message.details || typeof message.details !== "object" ||
        !("owner" in message.details) || message.details.owner !== "automata-context-status:request-local",
    );
    if (lines.length) messages.push({
      role: "custom", customType: RUNTIME_PRESSURE_TYPE, content: lines.join("\n"),
      display: false, timestamp: Date.now(),
      details: { owner: "automata-context-status:request-local", kind: remind ? "pressure-reminder" : "usage-observation", status,
        observations: remind ? { pressureThreshold: pressureThresholdForPercent(status.percent) } : {} },
    });
    return { messages };
  });

  pi.registerCommand("context-status", {
    description: "Show projected current context usage, pressure, and working model.",
    handler: async (_args, ctx) => {
      const formatted = formatContextStatus(readContextStatus(ctx));
      if (ctx.hasUI) ctx.ui.notify(formatted, "info");
      else if (ctx.mode === "print") console.log(formatted);
    },
  });
  pi.registerTool({
    name: "context_status", label: "Context Status",
    description: "Read projected current context tokens, model window, pressure and working provider/model. The projection is not the exact final request size.",
    promptSnippet: "Read projected context usage and working model",
    promptGuidelines: ["Use context_status only when a manual context diagnostic would inform the next step; pressure is observation, not an automatic action."],
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
      const status = readContextStatus(ctx);
      return { content: [{ type: "text", text: formatContextStatus(status) }], details: status };
    },
  });
}
