import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

interface ModelUsageTotals { input: number; output: number; cacheRead: number; cacheWrite: number; totalTokens: number }
interface Checkpoint {
  inputAnchorTimestamp: number | null;
  usage: ModelUsageTotals;
  seenAssistantMessages: WeakSet<object>;
}
function finite(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}
function nonnegative(value: unknown): number | undefined {
  const number = finite(value);
  return number !== undefined && number >= 0 ? number : undefined;
}
function zeroUsage(): ModelUsageTotals {
  return { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0 };
}
function addUsage(totals: ModelUsageTotals, value: unknown): ModelUsageTotals {
  if (!value || typeof value !== "object" || Array.isArray(value)) return { ...totals };
  const usage = value as Record<string, unknown>;
  const input = nonnegative(usage.input) ?? 0;
  const output = nonnegative(usage.output) ?? 0;
  const cacheRead = nonnegative(usage.cacheRead) ?? 0;
  const cacheWrite = nonnegative(usage.cacheWrite) ?? 0;
  return { input: totals.input + input, output: totals.output + output,
    cacheRead: totals.cacheRead + cacheRead, cacheWrite: totals.cacheWrite + cacheWrite,
    totalTokens: totals.totalTokens + (nonnegative(usage.totalTokens) ?? input + output + cacheRead + cacheWrite) };
}
function formatElapsed(ms: number | null): string {
  if (ms === null) return "unknown";
  let seconds = Math.floor(Math.max(0, ms) / 1000);
  const hours = Math.floor(seconds / 3600); seconds %= 3600;
  const minutes = Math.floor(seconds / 60); seconds %= 60;
  return hours ? `${hours}h ${minutes}m ${seconds}s` : minutes ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

export default function (pi: ExtensionAPI) {
  let checkpoint: Checkpoint | undefined;
  const create = (timestamp: number | null): Checkpoint => ({
    inputAnchorTimestamp: timestamp, usage: zeroUsage(), seenAssistantMessages: new WeakSet<object>(),
  });
  const ensure = () => checkpoint ??= create(null);
  const snapshot = () => {
    const current = ensure();
    return {
      elapsedMs: current.inputAnchorTimestamp === null ? null : Math.max(0, Date.now() - current.inputAnchorTimestamp),
      inputAnchorTimestamp: current.inputAnchorTimestamp,
      modelUsage: { ...current.usage },
    };
  };
  const formatTimestamp = (timestamp: number | null) => {
    const date = timestamp === null ? null : new Date(timestamp);
    return date && Number.isFinite(date.getTime()) ? date.toISOString() : "unknown";
  };
  const format = (status: ReturnType<typeof snapshot>) => {
    const u = status.modelUsage;
    return `Activity usage\nElapsed: ${formatElapsed(status.elapsedMs)} wall-clock since the input anchor\nAnchor: ${formatTimestamp(status.inputAnchorTimestamp)}\nModel usage: in ${u.input} | out ${u.output} | cache read ${u.cacheRead} | cache write ${u.cacheWrite} | total ${u.totalTokens}`;
  };
  const reset = () => { checkpoint = undefined; };
  pi.on("session_start", reset);
  pi.on("session_tree", reset);
  pi.on("agent_start", () => { ensure(); });
  pi.on("message_start", (event) => {
    if (event.message.role === "user") checkpoint = create(finite(event.message.timestamp) ?? Date.now());
  });
  pi.on("message_end", (event) => {
    const message = event.message;
    if (!checkpoint || checkpoint.inputAnchorTimestamp === null || message.role !== "assistant" ||
        checkpoint.seenAssistantMessages.has(message)) return;
    const timestamp = finite(message.timestamp);
    if (timestamp !== undefined && timestamp < checkpoint.inputAnchorTimestamp) return;
    checkpoint.seenAssistantMessages.add(message);
    checkpoint.usage = addUsage(checkpoint.usage, message.usage);
  });
  pi.registerCommand("activity-usage", {
    description: "Show wall-clock elapsed and model usage since the latest user input.",
    handler: async (_args, ctx) => {
      const text = format(snapshot());
      if (ctx.hasUI) ctx.ui.notify(text, "info");
      else if (ctx.mode === "print") console.log(text);
    },
  });
  pi.registerTool({
    name: "activity_usage", label: "Activity Usage",
    description: "Read an on-demand snapshot of wall-clock elapsed and provider-reported assistant model usage since the latest user-role input, including coordinator inputs. Elapsed is not active effort or whole-task duration; tool results and summaries are excluded. Session/tree changes reset the checkpoint, compaction preserves it. No automatic notifications.",
    parameters: Type.Object({}),
    async execute() {
      const status = snapshot();
      return { content: [{ type: "text", text: format(status) }], details: status };
    },
  });
}
