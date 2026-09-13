import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

export const CONTEXT_SIGNAL_TYPE = "automata-context-awareness";
const RUNTIME_TIME_TYPE = "automata-runtime-time";
export const TIME_THRESHOLD_MS = 10 * 60 * 1000;

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
  pressureBands?: PressureBand[];
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

function formatContextChange(
  previous: ContextStatus | undefined,
  current: ContextStatus,
  observations: SignalObservations | undefined,
): string {
  const changes: string[] = [];
  if (observations?.pressureBands && observations.pressureBands.length > 0) {
    changes.push(`Context pressure changed: ${previous?.pressure ?? "unknown"} -> ${current.pressure}`);
  }
  if (observations?.timeThreshold !== undefined) {
    changes.push(`Context elapsed time crossed: ${observations.timeThreshold * 10}m`);
  }
  return changes.length > 0 ? changes.join("\n") : "Context status changed";
}

/** Format the factual message sent to the active agent on a meaningful change. */
export function formatContextSignal(
  _kind: SignalKind,
  status: ContextStatus,
  previous?: ContextStatus,
  observations?: SignalObservations,
): string {
  return `${formatContextChange(previous, status, observations)}\n\n${formatContextStatus(status)}`;
}

interface PendingObservations {
  timeThreshold: number | null;
  pressureBands: PressureBand[];
}

interface TaskCheckpoint {
  inputAnchorTimestamp: number | null;
  usage: ModelUsageTotals;
  lastTimeThreshold: number;
  lastPressure: PressureBand;
  reportedPressureBands: Set<PressureBand>;
  pending: PendingObservations;
  seenAssistantMessages: WeakSet<object>;
  previousStatus?: ContextStatus;
}

function emptyPendingObservations(): PendingObservations {
  return {
    timeThreshold: null,
    pressureBands: [],
  };
}

function pressureRank(pressure: PressureBand): number {
  switch (pressure) {
    case "low":
      return 0;
    case "moderate":
      return 1;
    case "high":
      return 2;
    case "critical":
      return 3;
    default:
      return -1;
  }
}

function isSignalPressure(pressure: PressureBand): boolean {
  return pressure === "moderate" || pressure === "high" || pressure === "critical";
}

const SIGNAL_PRESSURE_BANDS = ["moderate", "high", "critical"] as const;

/** Return upward pressure thresholds crossed but not already queued or reported. */
export function newlyCrossedPressureBands(
  previous: PressureBand,
  current: PressureBand,
  reported: ReadonlySet<PressureBand>,
  pending: readonly PressureBand[],
): PressureBand[] {
  const previousRank = pressureRank(previous);
  const currentRank = pressureRank(current);
  if (currentRank <= previousRank) return [];

  return SIGNAL_PRESSURE_BANDS.filter((pressure) => {
    const rank = pressureRank(pressure);
    return (
      rank > previousRank &&
      rank <= currentRank &&
      !reported.has(pressure) &&
      !pending.includes(pressure)
    );
  });
}

function signalKindForObservations(observations: SignalObservations): SignalKind {
  const kinds = [
    observations.timeThreshold !== undefined,
    (observations.pressureBands?.length ?? 0) > 0,
  ].filter(Boolean).length;

  if (kinds > 1) return "state-change";
  if ((observations.pressureBands?.length ?? 0) > 0) return "pressure-transition";
  if (observations.timeThreshold !== undefined) return "time-threshold";
  return "state-change";
}

export default function (pi: ExtensionAPI) {
  let checkpoint: TaskCheckpoint | undefined;

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

  const createCheckpoint = (ctx: ExtensionContext, inputAnchorTimestamp: number | null): TaskCheckpoint => {
    const status = readContextStatus(ctx);
    const reportedPressureBands = new Set<PressureBand>();
    if (isSignalPressure(status.pressure)) reportedPressureBands.add(status.pressure);

    return {
      inputAnchorTimestamp,
      usage: createUsageTotals(),
      lastTimeThreshold: 0,
      lastPressure: status.pressure,
      reportedPressureBands,
      pending: emptyPendingObservations(),
      seenAssistantMessages: new WeakSet<object>(),
      previousStatus: status,
    };
  };

  const ensureCheckpoint = (ctx: ExtensionContext): TaskCheckpoint => {
    if (!checkpoint) checkpoint = createCheckpoint(ctx, null);
    return checkpoint;
  };

  const startInputAnchor = (ctx: ExtensionContext, timestamp: unknown): void => {
    const inputAnchorTimestamp = finiteNumber(timestamp) ?? Date.now();
    checkpoint = createCheckpoint(ctx, inputAnchorTimestamp);
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

  const observeThresholds = (ctx: ExtensionContext): void => {
    const current = ensureCheckpoint(ctx);
    const status = getStatus(ctx);
    const hadPending =
      current.pending.timeThreshold !== null || current.pending.pressureBands.length > 0;
    const threshold = elapsedTimeThreshold(status.elapsedMs);
    if (threshold !== null && threshold > current.lastTimeThreshold) {
      current.pending.timeThreshold = Math.max(current.pending.timeThreshold ?? 0, threshold);
      current.lastTimeThreshold = threshold;
    }

    current.pending.pressureBands.push(
      ...newlyCrossedPressureBands(
        current.lastPressure,
        status.pressure,
        current.reportedPressureBands,
        current.pending.pressureBands,
      ),
    );
    current.lastPressure = status.pressure;
    const hasPending =
      current.pending.timeThreshold !== null || current.pending.pressureBands.length > 0;
    if (!hadPending && !hasPending) current.previousStatus = status;
  };

  const pendingObservations = (current: TaskCheckpoint): SignalObservations => ({
    ...(current.pending.timeThreshold === null
      ? {}
      : { timeThreshold: current.pending.timeThreshold }),
    ...(current.pending.pressureBands.length === 0
      ? {}
      : { pressureBands: [...current.pending.pressureBands] }),
  });

  const hasPendingObservations = (observations: SignalObservations): boolean =>
    observations.timeThreshold !== undefined || (observations.pressureBands?.length ?? 0) > 0;

  const deliverPending = (
    ctx: ExtensionContext,
    deliverAs: "steer" | "nextTurn",
  ): void => {
    const current = ensureCheckpoint(ctx);
    const observations = pendingObservations(current);
    if (!hasPendingObservations(observations)) return;

    const status = getStatus(ctx);
    const kind = signalKindForObservations(observations);
    pi.sendMessage(
      {
        customType: CONTEXT_SIGNAL_TYPE,
        content: formatContextSignal(kind, status, current.previousStatus, observations),
        display: false,
        details: { kind, status, observations },
      },
      { deliverAs },
    );

    if (observations.pressureBands) {
      for (const pressure of observations.pressureBands) {
        current.reportedPressureBands.add(pressure);
      }
    }
    current.pending = emptyPendingObservations();
    current.previousStatus = status;
  };

  // Modify only the outgoing context copy, not the session or telemetry anchor.
  pi.on("context", (event) => {
    const timestamp = Date.now();
    return {
      messages: [
        ...event.messages.filter(
          (message) => message.role !== "custom" || message.customType !== RUNTIME_TIME_TYPE,
        ),
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

  pi.on("session_start", () => {
    checkpoint = undefined;
  });

  pi.on("session_tree", () => {
    checkpoint = undefined;
  });

  pi.on("agent_start", (_event, ctx) => {
    // This is an internal checkpoint only; no model-visible telemetry is emitted here.
    ensureCheckpoint(ctx);
  });

  pi.on("message_start", (event, ctx) => {
    if (event.message.role === "user") {
      // A generic user-role message is intentionally treated as the latest input,
      // including messages submitted by a coordinator or subagent.
      startInputAnchor(ctx, event.message.timestamp);
    }
  });

  pi.on("message_end", (event) => {
    if (event.message.role === "assistant") observeAssistantMessage(event.message);
  });

  pi.on("turn_end", (_event, ctx) => {
    observeThresholds(ctx);
  });

  pi.on("agent_end", (_event, ctx) => {
    observeThresholds(ctx);
  });

  pi.on("agent_settled", (_event, ctx) => {
    // A settled run is a safe, non-streaming boundary. nextTurn queues the
    // observation without starting an unsolicited model response.
    observeThresholds(ctx);
    deliverPending(ctx, "nextTurn");
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
