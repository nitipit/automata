/** Shared bounded JSON; v1 delivery helpers are application adapter utilities. */
const MAX_FRAME_BYTES = 64 * 1024;
const MAX_PAYLOAD_BYTES = 32 * 1024;
const MAX_JSON_DEPTH = 32;
const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER;

export function validateDelivery(value) {
  if (!isRecord(value) || Object.keys(value).some(key => !["role", "deliverAs", "slot", "triggerTurn"].includes(key))) throw new Error("Invalid delivery options");
  const role = Object.hasOwn(value, "role") ? value.role : "user";
  const deliverAs = Object.hasOwn(value, "deliverAs") ? value.deliverAs : "immediate";
  if (!["user", "context"].includes(role) || !["immediate", "steer", "followUp", "nextTurn"].includes(deliverAs)) throw new Error("Invalid role or deliverAs");
  if (role === "user" && (deliverAs === "nextTurn" || Object.hasOwn(value, "triggerTurn"))) throw new Error("User messages always trigger a turn and cannot use nextTurn");
  if (Object.hasOwn(value, "triggerTurn") && typeof value.triggerTurn !== "boolean") throw new Error("triggerTurn must be boolean");
  if (deliverAs === "nextTurn" && value.triggerTurn) throw new Error("nextTurn cannot trigger a turn");
  if (Object.hasOwn(value, "slot")) {
    requireId(value.slot, "context slot");
    if (role !== "context" || deliverAs !== "nextTurn") throw new Error("Slots require context nextTurn delivery");
  }
  return { ...value, role, deliverAs };
}

export function serializePayload(value) {
  assertJsonValue(value);
  const encoded = JSON.stringify(value);
  if (encoded === undefined) throw new Error("Payload is not JSON serializable");
  if (new TextEncoder().encode(encoded).byteLength > MAX_PAYLOAD_BYTES) {
    throw new Error("Payload exceeds 32 KiB");
  }
  return encoded;
}

export function serializeMetadata(value) {
  const encoded = serializePayload(value);
  if (new TextEncoder().encode(encoded).byteLength > 16 * 1024) throw new Error('Metadata exceeds 16 KiB');
  return encoded;
}

export function validateReplyEnvelope(value) {
  if (!isRecord(value) || value.v !== 1 || value.kind !== "reply") {
    throw new Error("Expected a version 1 reply envelope");
  }
  requireId(value.id, "reply id");
  requireId(value.correlationId, "reply correlation id");
  if (!Object.hasOwn(value, "payload")) throw new Error("Reply envelope requires payload");
  serializePayload(value.payload);
  return value;
}

export function parseFrame(raw) {
  if (typeof raw !== "string") throw new Error("WebSocket frame must be text");
  if (new TextEncoder().encode(raw).byteLength > MAX_FRAME_BYTES) throw new Error("WebSocket frame exceeds 64 KiB");
  const value = JSON.parse(raw);
  if (!isRecord(value)) throw new Error("WebSocket message must be an object");
  return value;
}

function assertJsonValue(value, depth = 0, seen = new Set()) {
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
        if (!descriptor || !descriptor.enumerable || !("value" in descriptor)) {
          throw new Error("Payload array entries must be enumerable data properties");
        }
        assertJsonValue(descriptor.value, depth + 1, seen);
      }
      for (let index = 0; index < value.length; index++) {
        if (!Object.hasOwn(value, index)) throw new Error("Payload arrays cannot be sparse");
      }
      return;
    }
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) {
      throw new Error("Payload objects must be plain JSON objects");
    }
    for (const key of Object.getOwnPropertyNames(value)) {
      const descriptor = Object.getOwnPropertyDescriptor(value, key);
      if (!descriptor || !descriptor.enumerable || !("value" in descriptor)) {
        throw new Error("Payload objects must contain enumerable data properties");
      }
      assertJsonValue(descriptor.value, depth + 1, seen);
    }
    if (Object.getOwnPropertySymbols(value).length > 0) {
      throw new Error("Payload objects may not contain symbol properties");
    }
  } finally {
    seen.delete(value);
  }
}

function isArrayIndexKey(key) {
  const index = Number(key);
  return Number.isInteger(index) && index >= 0 && index < 2 ** 32 - 1 && String(index) === key;
}

export function requireId(value, name) {
  if (typeof value !== "string" || value.length === 0 || value.length > 128) {
    throw new Error(`${name} must be a bounded non-empty string`);
  }
  return value;
}

export function sessionFromLocation(location = globalThis.location) {
  return /^\/sessions\/([A-Za-z0-9_-]{1,128})\/?$/.exec(location?.pathname ?? "")?.[1];
}

export function pairFromLocation(location = globalThis.location) {
  return new URLSearchParams((location?.hash ?? "").replace(/^#/, "")).get("pair") ?? undefined;
}

export function endpointFromLocation(location = globalThis.location) {
  if (!location?.host) return undefined;
  return `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws`;
}

export function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
