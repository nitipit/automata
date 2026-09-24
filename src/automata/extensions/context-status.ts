import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

export const CONTEXT_SIGNAL_TYPE = "automata-context-awareness";
const RUNTIME_TIME_TYPE = "automata-runtime-time";
export const RUNTIME_PRESSURE_TYPE = "automata-context-pressure";
export const TIME_THRESHOLD_MS = 10 * 60 * 1000;
export const PRESSURE_SIGNAL_THRESHOLDS = [50, 75, 80, 85, 90, 95] as const;

export const PRESSURE_THRESHOLDS = {
  moderate: 50,
  high: 75,
  critical: 90,
} as const;

export type PressureBand = "unknown" | "low" | "moderate" | "high" | "critical";

type ContextSource = Pick<ExtensionContext, "getContextUsage" | "model">;
export type SignalKind = "pressure-transition" | "time-threshold" | "state-change";

export interface ModelUsageTotals {
  input: number;
  output: number;
  cacheRead: number;
  cacheWrite: number;
  totalTokens: number;
}

export interface ContextStatus {
  tokens: number | null;
  contextWindow: number | null;
  percent: number | null;
  pressure: PressureBand;
  /** Runtime telemetry is present only for an active task checkpoint. */
  elapsedMs?: number | null;
  inputAnchorTimestamp?: number | null;
  modelUsage?: ModelUsageTotals;
}

export interface RuntimeTelemetry {
  elapsedMs?: number | null;
  inputAnchorTimestamp?: number | null;
  modelUsage?: ModelUsageTotals;
}

export interface SignalObservations {
  timeThreshold?: number;
  pressureThreshold?: number;
}

const ZERO_USAGE: ModelUsageTotals = {
  input: 0,
  output: 0,
  cacheRead: 0,
  cacheWrite: 0,
  totalTokens: 0,
};

function finiteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function positiveNumber(value: unknown): number | undefined {
  const number = finiteNumber(value);
  return number !== undefined && number > 0 ? number : undefined;
}

function recordValue(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

export function createUsageTotals(): ModelUsageTotals {
  return { ...ZERO_USAGE };
}

/** Add provider-reported assistant usage without counting tool messages. */
export function addUsageTotals(totals: ModelUsageTotals, usage: unknown): ModelUsageTotals {
  const reported = recordValue(usage);
  if (!reported) return { ...totals };

  const input = finiteNumber(reported.input) ?? 0;
  const output = finiteNumber(reported.output) ?? 0;
  const cacheRead = finiteNumber(reported.cacheRead) ?? 0;
  const cacheWrite = finiteNumber(reported.cacheWrite) ?? 0;
  const reportedTotal = finiteNumber(reported.totalTokens);

  return {
    input: totals.input + input,
    output: totals.output + output,
    cacheRead: totals.cacheRead + cacheRead,
    cacheWrite: totals.cacheWrite + cacheWrite,
    totalTokens:
      totals.totalTokens +
      (reportedTotal ?? input + output + cacheRead + cacheWrite),
  };
}

/** Map runtime-reported percentage to an observational pressure band. */
export function pressureBandForPercent(percent: number | null | undefined): PressureBand {
  if (percent === null || percent === undefined || !Number.isFinite(percent)) {
    return "unknown";
  }
  if (percent < PRESSURE_THRESHOLDS.moderate) return "low";
  if (percent < PRESSURE_THRESHOLDS.high) return "moderate";
  if (percent < PRESSURE_THRESHOLDS.critical) return "high";
  return "critical";
}

/** Coalesce crossed thresholds to the highest current level, including usage above 100%. */
export function pressureThresholdForPercent(percent: number | null | undefined): number | null {
  if (percent === null || percent === undefined || !Number.isFinite(percent)) return null;
  return PRESSURE_SIGNAL_THRESHOLDS.findLast((threshold) => percent >= threshold) ?? null;
}

/** Build a status snapshot from Pi's supported context-usage API. */
export function readContextStatus(
  source: ContextSource,
  telemetry?: RuntimeTelemetry,
): ContextStatus {
  const usage = source.getContextUsage();
  const contextWindow =
    positiveNumber(usage?.contextWindow) ?? positiveNumber(source.model?.contextWindow) ?? null;
  const tokens = finiteNumber(usage?.tokens);
  const reportedPercent = finiteNumber(usage?.percent);
  const percent =
    reportedPercent ??
    (tokens !== undefined && contextWindow !== null ? (tokens / contextWindow) * 100 : null);
  const normalizedTokens = tokens === undefined ? null : Math.max(0, tokens);
  const hasUsage = normalizedTokens !== null && percent !== null;

  const status: ContextStatus = {
    tokens: normalizedTokens,
    contextWindow,
    percent,
    pressure: hasUsage ? pressureBandForPercent(percent) : "unknown",
  };

  if (telemetry) {
    status.elapsedMs = telemetry.elapsedMs ?? null;
    status.inputAnchorTimestamp = telemetry.inputAnchorTimestamp ?? null;
    status.modelUsage = telemetry.modelUsage ?? createUsageTotals();
  }

  return status;
}

/** Return the state key retained for callers that need pressure de-duplication. */
export function contextStatusKey(status: ContextStatus): string {
  return JSON.stringify([status.pressure, status.contextWindow]);
}

/** Return the highest ten-minute wall-clock threshold crossed by elapsed time. */
export function elapsedTimeThreshold(elapsedMs: number | null | undefined): number | null {
  if (elapsedMs === null || elapsedMs === undefined || !Number.isFinite(elapsedMs)) {
    return null;
  }
  const threshold = Math.floor(Math.max(0, elapsedMs) / TIME_THRESHOLD_MS);
  return threshold > 0 ? threshold : null;
}

export function formatLocalTimestamp(timestamp: number | null | undefined): string {
  if (timestamp === null || timestamp === undefined || !Number.isFinite(timestamp)) {
    return "unknown";
  }

  const date = new Date(timestamp);
  if (!Number.isFinite(date.getTime())) return "unknown";

  const pad = (value: number, width = 2): string => String(value).padStart(width, "0");
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes < 0 ? "-" : "+";
  const absoluteOffset = Math.abs(offsetMinutes);
  const offset = `${sign}${pad(Math.floor(absoluteOffset / 60))}:${pad(absoluteOffset % 60)}`;

  return [
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}.${pad(date.getMilliseconds(), 3)}${offset}`,
  ].join("");
}

export function formatElapsed(elapsedMs: number | null | undefined): string {
  if (elapsedMs === null || elapsedMs === undefined || !Number.isFinite(elapsedMs)) {
    return "unknown";
  }

  let seconds = Math.floor(Math.max(0, elapsedMs) / 1000);
  const hours = Math.floor(seconds / 3600);
  seconds %= 3600;
  const minutes = Math.floor(seconds / 60);
  seconds %= 60;

  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function formatTokenCount(tokens: number | null): string {
  return tokens === null ? "unknown" : Math.round(tokens).toLocaleString("en-US");
}

function formatPercent(percent: number | null): string {
  if (percent === null) return "unknown";
  return `${percent.toFixed(1).replace(/\.0$/, "")}%`;
}

function formatWindow(contextWindow: number | null): string {
  return contextWindow === null ? "unknown" : Math.round(contextWindow).toLocaleString("en-US");
}

function formatUsage(usage: ModelUsageTotals): string {
  return [
    `in ${formatTokenCount(usage.input)}`,
    `out ${formatTokenCount(usage.output)}`,
    `cache read ${formatTokenCount(usage.cacheRead)}`,
    `cache write ${formatTokenCount(usage.cacheWrite)}`,
    `total ${formatTokenCount(usage.totalTokens)}`,
  ].join(" | ");
}

function formatPressureRange(pressure: PressureBand): string | null {
  switch (pressure) {
    case "low":
      return "<50% band";
    case "moderate":
      return "50–75% band";
    case "high":
      return "75–90% band";
    case "critical":
      return "90%+ band";
    default:
      return null;
  }
}

/** Format the status shown by /context-status and returned by context_status. */
export function formatContextStatus(status: ContextStatus): string {
  const usage = `${formatTokenCount(status.tokens)} / ${formatWindow(status.contextWindow)} tokens`;
  const pressureRange = formatPressureRange(status.pressure);
  const lines = [
    "Context status",
    `Usage: ${usage} (${formatPercent(status.percent)})`,
    `Pressure: ${status.pressure}${pressureRange ? ` (${pressureRange})` : ""}`,
  ];

  if (status.elapsedMs !== undefined || status.inputAnchorTimestamp !== undefined || status.modelUsage) {
    lines.push(
      `Elapsed: ${formatElapsed(status.elapsedMs)} since input`,
      `Anchor: ${formatLocalTimestamp(status.inputAnchorTimestamp)}`,
      `Model: ${formatUsage(status.modelUsage ?? createUsageTotals())}`,
    );
  }

  return lines.join("\n");
}

/** Report measured pressure; reminders defer compaction decisions to the applicable policy. */
export function formatContextSignal(
  _kind: SignalKind,
  status: ContextStatus,
  _previous?: ContextStatus,
  observations?: SignalObservations,
): string {
  const changes: string[] = [];
  if (observations?.pressureThreshold !== undefined) {
    changes.push(`Context pressure reached the ${observations.pressureThreshold}% threshold.`);
  }
  if (observations?.timeThreshold !== undefined) {
    changes.push(`Context elapsed time crossed: ${observations.timeThreshold * 10}m`);
  }
  const parts = [changes.join("\n") || "Context status changed", formatContextStatus(status)];
  if ((observations?.pressureThreshold ?? 0) >= PRESSURE_THRESHOLDS.high) {
    parts.push(status.pressure === "critical"
      ? "Urgent compaction reminder: preserve the minimum durable checkpoint and use the earliest safe boundary before substantial new work."
      : "Compaction reminder: finish the current coherent unit, preserve durable state, and use the next stable boundary.");
    parts.push("Apply the existing compaction policy and preferences. Do not interrupt an unfinished operation; this observation does not itself authorize or run compaction.");
  }
  return parts.join("\n\n");
}

interface TaskCheckpoint {
  inputAnchorTimestamp: number | null;
  usage: ModelUsageTotals;
  lastTimeThreshold: number;
  pendingTimeThreshold: number | null;
  seenAssistantMessages: WeakSet<object>;
}

/** Pressure belongs to the context lifecycle, not to the latest user-input checkpoint. */
interface PressureCheckpoint {
  identity: string;
  highestThreshold: number;
}

export default function (pi: ExtensionAPI) {
  let checkpoint: TaskCheckpoint | undefined;
  let pressureCheckpoint: PressureCheckpoint | undefined;

  const getStatus = (ctx: ContextSource): ContextStatus => {
    if (!checkpoint) return readContextStatus(ctx);

    const elapsedMs =
      checkpoint.inputAnchorTimestamp === null
        ? null
        : Math.max(0, Date.now() - checkpoint.inputAnchorTimestamp);
    return readContextStatus(ctx, {
      elapsedMs,
      inputAnchorTimestamp: checkpoint.inputAnchorTimestamp,
      modelUsage: checkpoint.usage,
    });
  };

  const createCheckpoint = (inputAnchorTimestamp: number | null): TaskCheckpoint => ({
    inputAnchorTimestamp,
    usage: createUsageTotals(),
    lastTimeThreshold: 0,
    pendingTimeThreshold: null,
    seenAssistantMessages: new WeakSet<object>(),
  });

  const ensureCheckpoint = (): TaskCheckpoint => {
    if (!checkpoint) checkpoint = createCheckpoint(null);
    return checkpoint;
  };

  const startInputAnchor = (timestamp: unknown): void => {
    checkpoint = createCheckpoint(finiteNumber(timestamp) ?? Date.now());
  };

  const observeAssistantMessage = (message: { role: string; timestamp?: number; usage?: unknown }): void => {
    if (!checkpoint || checkpoint.inputAnchorTimestamp === null || message.role !== "assistant") {
      return;
    }
    if (typeof message !== "object" || checkpoint.seenAssistantMessages.has(message)) return;
    const timestamp = finiteNumber(message.timestamp);
    if (timestamp !== undefined && timestamp < checkpoint.inputAnchorTimestamp) return;

    checkpoint.seenAssistantMessages.add(message);
    checkpoint.usage = addUsageTotals(checkpoint.usage, message.usage);
  };

  const observeTimeThreshold = (ctx: ExtensionContext): void => {
    const current = ensureCheckpoint();
    const threshold = elapsedTimeThreshold(getStatus(ctx).elapsedMs);
    if (threshold !== null && threshold > current.lastTimeThreshold) {
      current.pendingTimeThreshold = threshold;
      current.lastTimeThreshold = threshold;
    }
  };

  const deliverPendingTime = (ctx: ExtensionContext): void => {
    const current = ensureCheckpoint();
    if (current.pendingTimeThreshold === null) return;
    const observations = { timeThreshold: current.pendingTimeThreshold };
    const status = getStatus(ctx);
    const kind = "time-threshold";
    pi.sendMessage(
      {
        customType: CONTEXT_SIGNAL_TYPE,
        content: formatContextSignal(kind, status, undefined, observations),
        display: false,
        details: { kind, status, observations },
      },
      { deliverAs: "nextTurn" },
    );
    current.pendingTimeThreshold = null;
  };

  const pressureSignal = (ctx: ExtensionContext, timestamp: number) => {
    const status = getStatus(ctx);
    const identity = JSON.stringify([ctx.model?.provider, ctx.model?.id, status.contextWindow]);
    if (pressureCheckpoint?.identity !== identity) {
      pressureCheckpoint = { identity, highestThreshold: 0 };
    }
    // Unknown post-compaction usage is not evidence of low pressure or another reset.
    const threshold = status.pressure === "unknown" ? null : pressureThresholdForPercent(status.percent);
    if (threshold === null || threshold <= pressureCheckpoint.highestThreshold) return [];
    pressureCheckpoint.highestThreshold = threshold;
    const observations = { pressureThreshold: threshold };
    return [{
      role: "custom" as const,
      customType: RUNTIME_PRESSURE_TYPE,
      content: formatContextSignal("pressure-transition", status, undefined, observations),
      display: false,
      timestamp,
      details: { kind: "pressure-transition", status, observations },
    }];
  };

  // Safe pre-request injection: no steering, wakeup, session entry or mid-stream event.
  pi.on("context", (event, ctx) => {
    const timestamp = Date.now();
    return {
      messages: [
        ...event.messages.filter(
          (message) => message.role !== "custom" ||
            (message.customType !== RUNTIME_TIME_TYPE && message.customType !== RUNTIME_PRESSURE_TYPE),
        ),
        ...pressureSignal(ctx, timestamp),
        {
          role: "custom" as const,
          customType: RUNTIME_TIME_TYPE,
          content: `Runtime local time: ${formatLocalTimestamp(timestamp)}`,
          display: false,
          timestamp,
        },
      ],
    };
  });

  const resetSession = () => {
    checkpoint = undefined;
    pressureCheckpoint = undefined;
  };
  pi.on("session_start", resetSession);
  pi.on("session_tree", resetSession);
  // Only success rearms reminders. Failed/cancelled compaction leaves deduplication intact.
  pi.on("session_compact", () => { pressureCheckpoint = undefined; });

  pi.on("agent_start", () => {
    // This is an internal checkpoint only; no model-visible telemetry is emitted here.
    ensureCheckpoint();
  });

  pi.on("message_start", (event) => {
    if (event.message.role === "user") {
      // A generic user-role message is intentionally treated as the latest input,
      // including messages submitted by a coordinator or subagent.
      startInputAnchor(event.message.timestamp);
    }
  });

  pi.on("message_end", (event) => {
    if (event.message.role === "assistant") observeAssistantMessage(event.message);
  });

  pi.on("turn_end", (_event, ctx) => {
    observeTimeThreshold(ctx);
  });

  pi.on("agent_end", (_event, ctx) => {
    observeTimeThreshold(ctx);
  });

  pi.on("agent_settled", (_event, ctx) => {
    // Preserve settled nextTurn delivery for time telemetry without waking the agent.
    observeTimeThreshold(ctx);
    deliverPendingTime(ctx);
  });

  pi.registerCommand("context-status", {
    description: "Show current context usage, pressure, and optional task telemetry.",
    handler: async (_args, ctx) => {
      const formatted = formatContextStatus(getStatus(ctx));
      if (ctx.hasUI) {
        ctx.ui.notify(formatted, "info");
      } else if (ctx.mode === "print") {
        console.log(formatted);
      }
    },
  });

  pi.registerTool({
    name: "context_status",
    label: "Context Status",
    description:
      "Optional manual diagnostic for current context usage, model window, pressure, and task telemetry.",
    promptSnippet: "Read context usage and optional task telemetry",
    promptGuidelines: [
      "Use context_status only when a manual diagnostic would inform the next step; the runtime tracks task checkpoints and emits observations itself.",
      "Time and model usage are supporting telemetry. Pressure bands are observations, not automatic delegation commands.",
    ],
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
      const status = getStatus(ctx);
      return {
        content: [{ type: "text", text: formatContextStatus(status) }],
        details: status,
      };
    },
  });
}
