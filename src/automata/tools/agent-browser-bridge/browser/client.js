/** Browser transport for the generic JSON agent-browser-bridge protocol. */

const MAX_FRAME_BYTES = 64 * 1024;
const MAX_PAYLOAD_BYTES = 32 * 1024;
const MAX_JSON_DEPTH = 32;
const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER;

export function createAgentBrowserBridgeClient({
  WebSocketImpl = globalThis.WebSocket,
  location = globalThis.location,
  onMessage = () => {},
  onState = () => {},
  onDelivery = () => {},
} = {}) {
  let socket;
  let generation = 0;
  let connected = false;
  let pendingId;
  let deliveryOptions = false;
  const contextRequests = new Set();
  const sessionId = sessionFromLocation(location);
  const pairToken = pairFromLocation(location);

  function connect(endpoint = endpointFromLocation(location)) {
    if (!endpoint || !WebSocketImpl) throw new Error("A WebSocket endpoint is required");
    if (!sessionId || !pairToken) throw new Error("Pairing URL is missing a session id or pair token");
    socket?.close?.();
    const localGeneration = ++generation;
    const localSocket = new WebSocketImpl(endpoint);
    socket = localSocket;
    connected = false;
    deliveryOptions = false;
    onState({ status: "connecting", sessionId });
    const current = () => socket === localSocket && generation === localGeneration;
    localSocket.onmessage = (event) => {
      if (!current()) return;
      try {
        const value = parseFrame(event.data);
        if (value.type === "hello_ack") {
          connected = true;
          deliveryOptions = value.deliveryOptions === 1;
          pendingId = typeof value.pendingId === "string" ? value.pendingId : undefined;
          onState({
            status: "connected",
            sessionId,
            channelId: value.channelId,
            agentBusy: value.agentBusy === true,
            pendingId,
          });
          return;
        }
        if (value.type === "context_result") {
          if (!contextRequests.has(value.id)) return;
          if (!["buffered", "queued", "uncertain"].includes(value.status)) contextRequests.delete(value.id);
          onDelivery({ id: value.id, status: value.status, details: value.details });
          return;
        }
        if (value.type === "receipt") {
          if (value.id !== pendingId) return;
          onState({ status: "accepted", id: value.id, transport: "accepted" });
          return;
        }
        if (value.type === "admitted") {
          if (value.id !== pendingId) return;
          onState({ status: "admitted", id: value.id });
          return;
        }
        if (value.type === "reply") {
          const envelope = validateReplyEnvelope(value.envelope);
          if (pendingId !== envelope.correlationId) {
            throw new Error("Reply does not correlate to the pending browser message");
          }
          pendingId = undefined;
          onState({
            status: "replied",
            id: envelope.correlationId,
            replyId: envelope.id,
          });
          onMessage(envelope);
          return;
        }
        if (value.type === "rejected") {
          if (pendingId !== value.id) return;
          pendingId = undefined;
          const error = isRecord(value.error)
            ? value.error
            : { code: "rejected", message: "Message rejected" };
          onState({ status: "rejected", id: value.id, error });
          return;
        }
        if (value.type === "agent_state") {
          if (!connected) return;
          onState({ status: "connected", sessionId, agentBusy: value.busy === true, pendingId });
          return;
        }
        if (value.type === "disconnected") {
          connected = false;
          onState({ status: "disconnected", pendingId: value.pendingId, message: value.message });
          return;
        }
        if (value.type === "duplicate") {
          if (contextRequests.has(value.id)) {
            onDelivery({ id: value.id, status: "uncertain", details: { reason: "Duplicate context request; not replayed" } });
            return;
          }
          if (value.id !== pendingId) return;
          onState({
            status: "error",
            uncertain: true,
            id: value.id,
            error: {
              code: "duplicate",
              message: `Message was already observed (${value.status ?? "unknown"})`,
            },
          });
          return;
        }
        if (value.type === "error") {
          onState({
            status: "error",
            error: { code: value.code ?? "protocol", message: value.message ?? "Bridge error" },
          });
        }
      } catch (error) {
        onState({ status: "error", error: { code: "malformed", message: error.message ?? String(error) } });
      }
    };
    localSocket.onerror = () => {
      if (current()) onState({ status: "error", error: { code: "transport", message: "WebSocket error" } });
    };
    localSocket.onclose = () => {
      if (current()) {
        connected = false;
        onState({ status: "disconnected", pendingId });
      }
    };
    localSocket.addEventListener?.("open", () => {
      if (!current()) return;
      localSocket.send(JSON.stringify({ type: "hello", role: "browser", token: pairToken, sessionId }));
    }, { once: true });
    return localSocket;
  }

  function sendMessage(payload, options) {
    const delivery = options === undefined ? undefined : validateDelivery(options);
    if (delivery && !deliveryOptions) throw new Error("Server does not advertise delivery options");
    if (delivery?.role === "context") {
      serializePayload(payload);
      return sendContext({ kind: "message", payload, delivery });
    }
    if (pendingId) throw new Error(`A browser message is already pending: ${pendingId}`);
    if (!connected || !socket || socket.readyState !== 1) throw new Error("Bridge is disconnected");
    const encodedPayload = serializePayload(payload);
    const message = {
      v: 1,
      id: crypto.randomUUID(),
      kind: "message",
      payload,
      ...(delivery ? { delivery } : {}),
    };
    const encoded = JSON.stringify(message);
    if (encoded === undefined || new TextEncoder().encode(encoded).byteLength > MAX_FRAME_BYTES) {
      throw new Error("Message exceeds 64 KiB");
    }
    if (new TextEncoder().encode(encodedPayload).byteLength > MAX_PAYLOAD_BYTES) {
      throw new Error("Payload exceeds 32 KiB");
    }
    // Claim the identity before transport: a thrown send may still have reached the server.
    pendingId = message.id;
    try {
      socket.send(encoded);
    } catch (error) {
      onState({
        status: "error",
        id: message.id,
        uncertain: true,
        error: { code: "transport", message: error.message ?? String(error) },
      });
      throw error;
    }
    onState({ status: "sending", id: message.id });
    return { id: message.id, message };
  }

  // Context acknowledgments are separate from the single outstanding Chat reply.
  function sendContext(fields) {
    if (!deliveryOptions) throw new Error("Server does not advertise delivery options");
    if (!connected || !socket || socket.readyState !== 1) throw new Error("Bridge is disconnected");
    if (contextRequests.size >= 32) throw new Error("Context request capacity reached; inspect/clear or reconnect explicitly");
    const message = { v: 1, id: crypto.randomUUID(), ...fields };
    const encoded = JSON.stringify(message);
    if (new TextEncoder().encode(encoded).byteLength > MAX_FRAME_BYTES) throw new Error("Message exceeds 64 KiB");
    contextRequests.add(message.id);
    try { socket.send(encoded); }
    catch (error) {
      onDelivery({ id: message.id, status: "uncertain", details: { reason: "Transport failure; do not retry automatically" } });
      throw error;
    }
    return { id: message.id, message };
  }

  function contextControl(action, slot) {
    if (slot !== undefined) requireId(slot, "context slot");
    return sendContext({ kind: "context_control", action, ...(slot === undefined ? {} : { slot }) });
  }

  function close() {
    generation++;
    const localSocket = socket;
    socket = undefined;
    connected = false;
    pendingId = undefined;
    contextRequests.clear();
    deliveryOptions = false;
    localSocket?.close?.();
    onState({ status: "disconnected" });
  }

  return {
    connect,
    sendMessage,
    inspectContext: (slot) => contextControl("inspect", slot),
    clearContext: (slot) => contextControl("clear", slot),
    close,
    isConnected: () => connected,
    getPendingId: () => pendingId,
    getSessionId: () => sessionId,
  };
}

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

function parseFrame(raw) {
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

function requireId(value, name) {
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

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
