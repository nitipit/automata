import { ContractError, isRecord } from "./contracts.js";
import type { ComponentDefinition, DefinitionSource } from "./types.js";

export function validateDefinition(value: unknown): ComponentDefinition {
  if (!isRecord(value) || ["validateProps", "validateState", "update", "create"].some(
      key => typeof value[key] !== "function") || !isRecord(value.events) ||
      Object.values(value.events).some(validator => typeof validator !== "function")) {
    throw new ContractError("Component definition", "Validators, event map, update reducer and create required");
  }
  return value as ComponentDefinition;
}

/**
 * Executes source. Call ONLY after the owner authorizes this exact source AND CSS.
 * Cache presence/JSON validation is not authority. This is not a sandbox and cannot
 * undo factory effects or custom-element registration. A factory receives the
 * public Adaptive UI namespace and authored CSS; no module loader is provided.
 */
export function evaluateTrustedDefinition(record: DefinitionSource, adaptiveUI: unknown): ComponentDefinition {
  try {
    const factory = new Function(`"use strict"; return (${record.source});`)();
    if (typeof factory !== "function") throw new Error("factory");
    return validateDefinition(factory(adaptiveUI, record.css));
  } catch {
    throw new ContractError("Trusted definition", "Factory evaluation failed; current draft retained");
  }
}
