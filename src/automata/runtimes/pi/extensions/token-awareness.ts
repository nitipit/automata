import type { ExtensionAPI, ExtensionContext, SessionEntry, SessionProjection } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

export const LANDMARK_TYPE = "automata-token-landmark";
export const THRESHOLD_TYPE = "automata-token-threshold";
export const DEFAULT_THRESHOLD = 100_000;
export const MAX_THRESHOLD = 1_000_000_000;
const CATEGORIES = ["input", "output", "cacheRead", "cacheWrite"] as const;
export type Usage = Record<(typeof CATEGORIES)[number], number>;
type Totals = Usage & { unknown: number; measured: number; zeroResponses: number };
type Message = SessionProjection["messages"][number];
interface Landmark {
  version: 1;
  sessionId: string;
  throughEntryId: string;
  timestamp: number;
  threshold: number;
  delta: Totals;
  cumulative: Totals;
}
const zero = (): Totals => ({ input: 0, output: 0, cacheRead: 0, cacheWrite: 0, unknown: 0, measured: 0, zeroResponses: 0 });
export const counted = (usage: Usage): number => usage.input + usage.output + usage.cacheWrite;
export const validThreshold = (value: unknown): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 1 && value <= MAX_THRESHOLD;

/** Pi normalizes input to exclude cache reads AND writes. Reasoning is in output,
 * cacheWrite1h is in cacheWrite; neither subset nor totalTokens is added again.
 * Valid zeros are retained, not classified as unavailable. Pi can also initialize
 * absent provider telemetry to zero; zeroResponses exposes that ambiguity.
 */
export function measuredUsage(value: unknown): Usage | undefined {
  if (!value || typeof value !== "object") return;
  const usage = value as Usage;
  if (!CATEGORIES.every(key => Number.isSafeInteger(usage[key]) && usage[key] >= 0)) return;
  if (!Number.isSafeInteger(CATEGORIES.reduce((sum, key) => sum + usage[key], 0))) return;
  return Object.fromEntries(CATEGORIES.map(key => [key, usage[key]])) as Usage;
}

function difference(total: Totals, baseline: Totals): Totals {
  return Object.fromEntries(Object.keys(total).map(key =>
    [key, total[key as keyof Totals] - baseline[key as keyof Totals]])) as Totals;
}

function equalTotals(value: unknown, expected: Totals): boolean {
  if (!value || typeof value !== "object") return false;
  return Object.keys(expected).every(key => {
    const number = (value as Record<string, unknown>)[key];
    return typeof number === "number" && Number.isSafeInteger(number) && number >= 0 &&
      number === expected[key as keyof Totals];
  });
}

/** Metadata is not trusted merely because its version matches. Compare snapshots
 * against ancestry as it existed at this entry; reject corrupt/stale baselines.
 */
function validLandmark(value: unknown, entry: SessionEntry, cumulative: Totals, baseline: Totals): value is Landmark {
  if (!value || typeof value !== "object") return false;
  const data = value as Landmark;
  return data.version === 1 && typeof data.sessionId === "string" && data.sessionId.trim().length > 0 &&
    typeof data.throughEntryId === "string" && data.throughEntryId === entry.parentId &&
    Number.isSafeInteger(data.timestamp) && Number.isFinite(new Date(data.timestamp).getTime()) &&
    validThreshold(data.threshold) && equalTotals(data.cumulative, cumulative) &&
    equalTotals(data.delta, difference(cumulative, baseline)) && counted(data.delta) >= data.threshold;
}

/** Raw active ancestry, never getEntries() (other branches) or compacted context.
 * Main assistant usage only: excludes nested tools, summaries and cache warming.
 */
export function scanBranch(entries: readonly SessionEntry[]) {
  const cumulative = zero();
  const landmarks: { entry: SessionEntry; data: Landmark }[] = [];
  let threshold = DEFAULT_THRESHOLD;
  for (const entry of entries) {
    if (entry.type === "message" && entry.message.role === "assistant") {
      const usage = measuredUsage(entry.message.usage);
      const safeTotal = usage && CATEGORIES.reduce((sum, key) => sum + cumulative[key] + usage[key], 0);
      if (usage && Number.isSafeInteger(safeTotal)) {
        for (const key of CATEGORIES) cumulative[key] += usage[key];
        cumulative.measured++;
        if (CATEGORIES.every(key => usage[key] === 0)) cumulative.zeroResponses++;
      } else cumulative.unknown++;
    } else if (entry.type === "custom" && entry.customType === THRESHOLD_TYPE) {
      const data = entry.data as { version?: number; threshold?: unknown } | undefined;
      if (data?.version === 1 && validThreshold(data.threshold)) threshold = data.threshold;
    } else if (entry.type === "custom" && entry.customType === LANDMARK_TYPE) {
      const data = entry.data;
      if (validLandmark(data, entry, cumulative, landmarks.at(-1)?.data.cumulative ?? zero())) {
        landmarks.push({ entry, data });
      }
    }
  }
  const last = landmarks.at(-1)?.data;
  return { threshold, cumulative, delta: difference(cumulative, last?.cumulative ?? zero()), landmarks };
}

function formatUsage(usage: Totals): string {
  return `input=${usage.input} output=${usage.output} cacheRead=${usage.cacheRead} cacheWrite=${usage.cacheWrite}` +
    ` counted=${counted(usage)} measuredResponses=${usage.measured} unknownResponses=${usage.unknown}` +
    ` zeroResponses=${usage.zeroResponses}`;
}

export function formatLandmark(data: Landmark): string {
  return `[Token usage landmark: session=${data.sessionId} branch-through=${data.throughEntryId}]\n` +
    `Delta since preceding landmark (or branch origin): ${formatUsage(data.delta)}\n` +
    `Cumulative active-branch main-assistant usage: ${formatUsage(data.cumulative)}\n` +
    `Threshold=${data.threshold}; counted=input+output+cacheWrite (cacheRead excluded).` +
    (data.cumulative.unknown ? " Unknown responses are excluded; totals cover measured usage only." : "") +
    (data.cumulative.zeroResponses ? " Zero records may include provider telemetry unavailable in Pi." : "");
}

/** Stable metadata is separate from conversation text, with no chat renderer.
 * A landmark is created NOW, not backdated to a historical assistant timestamp.
 * A threshold jump produces one actual delta, with no synthetic intermediate marks.
 */
function checkpoint(pi: ExtensionAPI, ctx: ExtensionContext): void {
  const entries = ctx.sessionManager.getBranch();
  const state = scanBranch(entries);
  if (counted(state.delta) < state.threshold) return;
  const through = entries.at(-1);
  if (!through) return;
  const data: Landmark = {
    version: 1, sessionId: ctx.sessionManager.getSessionId(), throughEntryId: through.id,
    timestamp: Date.now(), threshold: state.threshold,
    delta: state.delta, cumulative: state.cumulative,
  };
  pi.appendEntry(LANDMARK_TYPE, data);
}

// Match projection messages through other extensions' content-only annotations.
// Timestamp collisions use ordered occurrence queues, not timestamp uniqueness.
function messageKey(message: Message): string {
  return JSON.stringify([message.role, message.timestamp,
    message.role === "toolResult" ? message.toolCallId :
      message.role === "custom" ? message.customType : null]);
}

/** Replay immutable annotations at their branch positions. Compacted/omitted
 * anchors move to the next surviving message (or the end), never disappear.
 * No tool-call/result pair is split: checkpoint entries follow turn_end results.
 */
function annotate(messages: Message[], ctx: ExtensionContext): Message[] {
  const branch = ctx.sessionManager.getBranch();
  const state = scanBranch(branch);
  const index = new Map(branch.map((entry, i) => [entry.id, i]));
  const projected = ctx.sessionManager.buildSessionProjection().entries.flatMap(entry =>
    entry.messages.filter(message => message.role !== "system").map(message => ({
      message, position: index.get(entry.sourceEntry.id) ?? -1,
    })));
  const byKey = new Map<string, { indices: number[]; next: number }>();
  projected.forEach((item, i) => {
    const key = messageKey(item.message);
    const queue = byKey.get(key) ?? { indices: [], next: 0 };
    queue.indices.push(i);
    byKey.set(key, queue);
  });
  const clean = messages.filter(message => message.role !== "custom" || message.customType !== LANDMARK_TYPE);
  const result: Message[] = [];
  let cursor = 0;
  let landmark = 0;
  const appendBefore = (position: number) => {
    while (landmark < state.landmarks.length &&
        (index.get(state.landmarks[landmark].entry.id) ?? -1) < position) {
      const { data } = state.landmarks[landmark++];
      result.push({ role: "custom", customType: LANDMARK_TYPE, display: false,
        content: formatLandmark(data), timestamp: data.timestamp });
    }
  };
  for (const message of clean) {
    const queue = byKey.get(messageKey(message));
    while (queue && queue.indices[queue.next] < cursor) queue.next++;
    const match = queue?.indices[queue.next++] ?? -1;
    if (match >= 0) {
      appendBefore(projected[match].position);
      cursor = match + 1;
    }
    result.push(message);
  }
  appendBefore(Infinity);
  return result;
}

export default function (pi: ExtensionAPI) {
  // message_end precedes native session persistence. Capture no speculative
  // metadata there: the durable authoritative usage becomes readable at turn_end,
  // including tool-call-only assistant rounds. Context catches reload/crash gaps.
  // Re-scanning ancestry avoids object-identity deduplication and lifecycle resets.
  pi.on("turn_end", (_event, ctx) => { checkpoint(pi, ctx); });
  pi.on("context", (event, ctx) => {
    checkpoint(pi, ctx);
    return { messages: annotate(event.messages, ctx) };
  });

  pi.registerTool({
    name: "token_awareness",
    label: "Token Awareness",
    description: "Inspect branch-scoped token landmarks or set this session branch's next threshold. " +
      "Counted usage is main-assistant input+output+cacheWrite, excluding cacheRead. " +
      "Changing the threshold retains accrued usage and old landmarks. Lowering below accrued usage " +
      "creates one landmark at the next turn-end or context boundary, without an extra model request.",
    parameters: Type.Object({
      action: Type.Union([Type.Literal("inspect"), Type.Literal("set")]),
      threshold: Type.Optional(Type.Integer({ minimum: 1, maximum: MAX_THRESHOLD })),
    }),
    async execute(_id, params, _signal, _onUpdate, ctx) {
      if (params.action === "set") {
        if (!validThreshold(params.threshold)) throw new Error(`threshold must be an integer from 1 to ${MAX_THRESHOLD}`);
        pi.appendEntry(THRESHOLD_TYPE, { version: 1, threshold: params.threshold });
      } else if (params.action !== "inspect" || params.threshold !== undefined) {
        throw new Error("Use inspect without threshold, or set with threshold");
      }
      const state = scanBranch(ctx.sessionManager.getBranch());
      const details = {
        sessionId: ctx.sessionManager.getSessionId(), branchLeafId: ctx.sessionManager.getLeafId(),
        threshold: state.threshold, delta: state.delta, cumulative: state.cumulative,
        landmarkCount: state.landmarks.length,
        pending: counted(state.delta) >= state.threshold,
        scope: "Active branch ancestry, including inherited fork history; main assistant responses only",
      };
      return { content: [{ type: "text", text: JSON.stringify(details) }], details };
    },
  });
}
