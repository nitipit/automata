/** Bounded JSON and Pi adapter message types; no connection or session state. */
export type JsonPrimitive = null | string | number | boolean;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonRecord = Record<string, unknown>;
export type Endpoint = { wsUrl: string; publicUrl: string; controlToken?: string; v?: 2; participant?: string; token?: string; kind?: "agent" };
export type Sender = { id: string; kind: "page" | "agent"; sessionId?: string };
export type Delivery = { role: "user" | "context"; deliverAs: "immediate" | "steer" | "followUp" | "nextTurn"; slot?: string; triggerTurn?: boolean };
export type ContextEntry = { id: string; payload: JsonValue; slot?: string; canonical: string; owner: string };
export type BrowserEnvelope = {
  v: 1;
  id: string;
  kind: "message" | "reply" | "context_control";
  delivery?: Delivery;
  sender?: Sender;
  action?: "inspect" | "clear";
  slot?: string;
  correlationId?: string;
  payload: JsonValue;
};
export type Pending = {
  id: string;
  payload: JsonValue;
  canonical: string;
  admission: "awaiting" | "admitted" | "uncertain";
  delivery: "available" | "claimed" | "uncertain";
};
export type PendingRequest = {
  resolve: (value: JsonRecord) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
};

export const MAX_ENDPOINT_BYTES = 16 * 1024;
export const MAX_FRAME_BYTES = 64 * 1024;
export const MAX_PAYLOAD_BYTES = 32 * 1024;
export const MAX_JSON_DEPTH = 32;
export const MAX_ID_LENGTH = 128;

export function displayJson(value: unknown): string {
  let encoded: string;
  try {
    encoded = JSON.stringify(value);
  } catch {
    encoded = "[invalid JSON]";
  }
  if (encoded === undefined) return "[absent]";
  return escapeTerminalControls(encoded);
}

export function escapeTerminalControls(value: string): string {
  return value.replace(/[\u0000-\u001f\u007f-\u009f\u2028\u2029]/g, (character) =>
    `\\u${character.codePointAt(0)!.toString(16).padStart(4, "0")}`,
  );
}

export function serializePayload(value: unknown): string {
  assertJsonValue(value);
  const encoded = JSON.stringify(value);
  if (encoded === undefined) throw new Error("Payload is not JSON serializable");
  if (new TextEncoder().encode(encoded).byteLength > MAX_PAYLOAD_BYTES) throw new Error("Payload exceeds 32 KiB");
  return encoded;
}

export function serializeMetadata(value: unknown): string {
  const encoded = serializePayload(value);
  if (new TextEncoder().encode(encoded).byteLength > 16 * 1024) throw new Error("Metadata exceeds 16 KiB");
  return encoded;
}

export function assertJsonValue(value: unknown, depth = 0, seen = new Set<object>()): asserts value is JsonValue {
  if (depth > MAX_JSON_DEPTH) throw new Error("Payload nesting exceeds 32 levels");
  if (value === null || typeof value === "string" || typeof value === "boolean") return;
  if (typeof value === "number") {
    if (!Number.isFinite(value) || (Number.isInteger(value) && !Number.isSafeInteger(value))) {
      throw new Error("Payload numbers must be finite safe JavaScript numbers");
    }
    return;
  }
  if (typeof value !== "object") throw new Error("Payload contains a non-JSON value");
  if (seen.has(value)) throw new Error("Payload contains a cycle");
  seen.add(value);
  try {
    if (Array.isArray(value)) {
      if (Object.getOwnPropertySymbols(value).length > 0) throw new Error("Payload arrays may not contain symbol properties");
      for (const key of Object.getOwnPropertyNames(value)) {
        if (key === "length") continue;
        if (!isArrayIndexKey(key)) throw new Error("Payload arrays may not have extra properties");
        const descriptor = Object.getOwnPropertyDescriptor(value, key);
        if (!descriptor || !descriptor.enumerable || !("value" in descriptor)) throw new Error("Payload array entries must be enumerable data properties");
        assertJsonValue(descriptor.value, depth + 1, seen);
      }
      for (let index = 0; index < value.length; index++) {
        if (!Object.hasOwn(value, index)) throw new Error("Payload arrays cannot be sparse");
      }
      return;
    }
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) throw new Error("Payload objects must be plain JSON objects");
    for (const key of Object.getOwnPropertyNames(value)) {
      const descriptor = Object.getOwnPropertyDescriptor(value, key);
      if (!descriptor || !descriptor.enumerable || !("value" in descriptor)) throw new Error("Payload objects must contain enumerable data properties");
      assertJsonValue(descriptor.value, depth + 1, seen);
    }
    if (Object.getOwnPropertySymbols(value).length > 0) throw new Error("Payload objects may not contain symbol properties");
  } finally {
    seen.delete(value);
  }
}

export function isBrowserEnvelope(value: unknown): value is BrowserEnvelope {
  if (isRecord(value) && value.v === 1 && value.kind === "context_control") {
    return isBoundedId(value.id) && (value.action === "inspect" || value.action === "clear") &&
      (value.slot === undefined || isBoundedId(value.slot)) &&
      Object.keys(value).every(key => ["v", "id", "kind", "action", "slot"].includes(key));
  }
  if (isRecord(value) && hasOwn(value, "delivery") && !isDelivery(value.delivery)) return false;
  if (!isRecord(value) || value.v !== 1 || (value.kind !== "message" && value.kind !== "reply") || !hasOwn(value, "payload")) return false;
  if (!isBoundedId(value.id) || !isJsonValue(value.payload)) return false;
  return value.kind === "message" || isBoundedId(value.correlationId);
}

export function isDelivery(value: unknown): value is Delivery {
  if (!isRecord(value) || Object.keys(value).some(key => !["role", "deliverAs", "slot", "triggerTurn"].includes(key))) return false;
  if (!["user", "context"].includes(String(value.role)) || !["immediate", "steer", "followUp", "nextTurn"].includes(String(value.deliverAs))) return false;
  if (value.role === "user" && (value.deliverAs === "nextTurn" || hasOwn(value, "triggerTurn"))) return false;
  if (hasOwn(value, "triggerTurn") && typeof value.triggerTurn !== "boolean") return false;
  if (value.deliverAs === "nextTurn" && value.triggerTurn === true) return false;
  return !hasOwn(value, "slot") || (isBoundedId(value.slot) && value.role === "context" && value.deliverAs === "nextTurn");
}

export function isJsonValue(value: unknown): value is JsonValue {
  try {
    serializePayload(value);
    return true;
  } catch {
    return false;
  }
}

export function isArrayIndexKey(key: string): boolean {
  const index = Number(key);
  return Number.isInteger(index) && index >= 0 && index < 2 ** 32 - 1 && String(index) === key;
}

export function isBoundedId(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= MAX_ID_LENGTH;
}

export function parseRecord(value: unknown): JsonRecord {
  if (typeof value !== "string") throw new Error("WebSocket frame must be text");
  if (new TextEncoder().encode(value).byteLength > MAX_FRAME_BYTES) throw new Error("WebSocket frame exceeds 64 KiB");
  const parsed = JSON.parse(value);
  if (!isRecord(parsed)) throw new Error("Expected an object message");
  return parsed;
}

export function hasOwn(value: object, key: PropertyKey): boolean {
  return Object.prototype.hasOwnProperty.call(value, key);
}

export function isRecord(value: unknown): value is JsonRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
