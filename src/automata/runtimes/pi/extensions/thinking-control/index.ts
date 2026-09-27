import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { apply, operation, LEVELS } from "./local.ts";

/** Inspect or change only this session's native thinking effort. */
export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: "thinking_control",
    label: "Thinking Control",
    description: "Inspect/change this Pi session's thinking effort. Changes affect the next model request, never in-flight reasoning; no global settings or model changes.",
    promptGuidelines: [
      "Use thinking_control inspect for current effective effort and model-supported levels; unsupported levels fail rather than substitute.",
      "Respect the user's model/effort constraints. Thinking changes affect the next model request, not an already streaming request.",
      "A message asking an owned agent to change effort is not application: the target must check conversational authority, call its local tool, and report the effective result.",
    ],
    parameters: Type.Object({
      action: Type.Union([Type.Literal("inspect"), Type.Literal("set")]),
      level: Type.Optional(Type.Union(LEVELS.map(value => Type.Literal(value)))),
    }),
    async execute(_id, params, signal, _update, ctx) {
      signal?.throwIfAborted();
      const details = apply(pi, ctx, operation(params));
      return { content: [{ type: "text", text: JSON.stringify(details) }], details };
    },
  });
}
