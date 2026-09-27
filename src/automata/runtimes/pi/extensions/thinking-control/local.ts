/** Native session-local thinking state. No transport, grants, model switches or persistence. */
import { getSupportedThinkingLevels } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

export const LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh", "max"] as const;
export type Level = typeof LEVELS[number];
export type Operation = { action: "inspect" | "set"; level?: Level };

export function operation(value: unknown): Operation {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid thinking operation");
  const input = value as Record<string, unknown>;
  if (Object.keys(input).some(key => !["action", "level"].includes(key))) throw new Error("Unknown thinking operation field");
  if (input.action === "inspect" && input.level === undefined) return { action: "inspect" };
  if (input.action !== "set" || !LEVELS.includes(input.level as Level)) throw new Error("set requires a supported thinking level name");
  return { action: "set", level: input.level as Level };
}

export function apply(pi: ExtensionAPI, ctx: ExtensionContext, request: Operation) {
  const model = ctx.model;
  if (!model) throw new Error("No active model; thinking capability is unknown");
  const supported = getSupportedThinkingLevels(model);
  const previous = pi.getThinkingLevel();
  if (request.action === "set") {
    if (!supported.includes(request.level!)) throw new Error(`Unsupported thinking level ${request.level}; supported: ${supported.join(", ")}`);
    // Synchronous validation + application; no await lets another model selection interleave.
    // Native Pi updates session state/transcript, not global defaults. Never abort a request.
    pi.setThinkingLevel(request.level!);
  }
  const effective = pi.getThinkingLevel();
  return {
    status: request.action === "set" ? "applied" : "inspected",
    sessionId: ctx.sessionManager.getSessionId(),
    model: { provider: model.provider, id: model.id },
    supported,
    requested: request.level ?? null,
    previous,
    effective,
    changed: effective !== previous,
    busy: !ctx.isIdle(),
    appliesTo: "next_model_request",
    inFlightChanged: false,
  };
}
