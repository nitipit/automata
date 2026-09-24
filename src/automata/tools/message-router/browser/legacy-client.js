/** Explicit version-one browser compatibility adapter. */
import {validateDelivery, serializePayload, validateReplyEnvelope, parseFrame, requireId,
        isRecord, sessionFromLocation, pairFromLocation, endpointFromLocation} from "./protocol.js";
const MAX_FRAME_BYTES = 64 * 1024;
const MAX_PAYLOAD_BYTES = 32 * 1024;

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
