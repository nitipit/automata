import type { JSONValue } from "./types.js";

/** Safe diagnostics contain contract hints, never rejected values or secrets. */
export class ContractError extends Error {
  constructor(public contract: string, public hint: string) {
    super(`${contract}: ${hint}`);
    this.name = "ContractError";
  }
}
export function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value) &&
    [Object.prototype, null].includes(Object.getPrototypeOf(value));
}
export function requireRecord(value: unknown, keys: string[], contract: string): Record<string, unknown> {
  if (!isRecord(value) || Object.keys(value).length !== keys.length ||
      keys.some(key => !Object.hasOwn(value, key))) {
    throw new ContractError(contract, `Expected fields: ${keys.join(", ")}`);
  }
  return value;
}
export function requireId(value: unknown): string {
  if (typeof value !== "string" || !/^[a-zA-Z][a-zA-Z0-9_-]{0,127}$/.test(value) ||
      ["constructor", "prototype", "__proto__"].includes(value)) {
    throw new ContractError("Draft ID", "Expected a safe stable identifier");
  }
  return value;
}
export function cloneJSON(value: unknown): JSONValue {
  const seen = new Set<object>();
  function check(item: unknown, depth: number): void {
    if (depth > 64) throw new Error("depth");
    if (item === null || typeof item === "string" || typeof item === "boolean") return;
    if (typeof item === "number" && Number.isFinite(item)) return;
    if (!item || typeof item !== "object" || seen.has(item) ||
        (!Array.isArray(item) && !isRecord(item))) throw new Error("json");
    seen.add(item);
    for (const child of Array.isArray(item) ? item : Object.values(item)) check(child, depth + 1);
    seen.delete(item);
  }
  try {
    check(value, 0);
    return JSON.parse(JSON.stringify(value));
  } catch {
    throw new ContractError("Serializable JSON", "Finite JSON without cycles or live objects required (depth <=64)");
  }
}
