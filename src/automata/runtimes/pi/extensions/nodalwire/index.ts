import { parseArgs } from "node:util";
import { randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { encodeMessage, decodeMessage, type PeerMessage, type MessageOptions, type ContentBlock } from "./protocol.ts";
import { ReplyReferences } from "./reply-references.ts";
import { validName, validateNativeMessage, safeTransportError, withJoinCredential, type NativeMessage } from "./safety.ts";
export { encodeMessage, decodeMessage } from "./protocol.ts";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const DEFAULT_ENDPOINT = "tcp://127.0.0.1:5555";
const COMMAND_USAGE = "Usage: /nodalwire connect --name <name> [endpoint] | disconnect | status";
const MESSAGE_TYPE = "automata-pi-nodalwire";
const MAX_PENDING_MESSAGES = 32;
const MAX_REQUESTS = 4;
const DEFAULT_REQUEST_SECONDS = 30;
const MAX_REQUEST_SECONDS = 120;
const MAX_REPLY_OUTPUT_BYTES = 50 * 1024;

type OperationOptions = { signal?: AbortSignal };
type MembershipReceipt = { readonly network: string; readonly joined: boolean; readonly changed: boolean };
type Client = {
  send(destination: string, payload: Uint8Array, options?: OperationOptions & { network?: string }): Promise<string>;
  receive(options?: OperationOptions): Promise<NativeMessage>;
  join(network: string, credential?: string, options?: OperationOptions): Promise<MembershipReceipt>;
  leave(network: string, options?: OperationOptions): Promise<MembershipReceipt>;
  request(destination: string, payload: Uint8Array, options?: OperationOptions & { network?: string; timeout?: number }): Promise<NativeMessage>;
  reply(incoming: NativeMessage, payload: Uint8Array, options?: OperationOptions): Promise<string>;
  close(options?: { timeout?: number }): Promise<void>;
};
export type Connect = (name: string, endpoint: string, options: { signal: AbortSignal }) => Promise<Client>;
type Connection = {
  node: Client; name: string; endpoint: string; generation: number;
  abort: AbortController; done: Promise<void>;
};

const connectClient: Connect = async (name, endpoint, options) => {
  // Native transport is lazy; factory registration opens no resources.
  const dependency = "@devcapsule/nodalwire-client";
  const { Node } = await import(dependency);
  return Node.connect(name, endpoint, options);
};

const messageSchema = Type.Object({
  content: Type.Union([Type.String(), Type.Array(Type.Union([
    Type.Object({ type: Type.Literal("text"), text: Type.String(), textSignature: Type.Optional(Type.String()) }, { additionalProperties: false }),
    Type.Object({ type: Type.Literal("image"), data: Type.String(), mimeType: Type.String() }, { additionalProperties: false }),
  ]))]),
  display: Type.Boolean(),
  details: Type.Optional(Type.Unknown()),
}, { additionalProperties: false });
const optionsSchema = Type.Object({
  deliverAs: Type.Optional(Type.Union([Type.Literal("steer"), Type.Literal("followUp"), Type.Literal("nextTurn")])),
  triggerTurn: Type.Optional(Type.Boolean()),
}, { additionalProperties: false });
const networkSchema = Type.Optional(Type.String({ description: "Explicit network; omitted means literal default, not another joined network." }));
const messageFields = { message: messageSchema, options: Type.Optional(optionsSchema) };
const annotations = { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true };

function argumentFields(value: unknown, allowed: readonly string[]): void {
  if (value === null || typeof value !== "object" || Array.isArray(value) ||
      Object.getPrototypeOf(value) !== Object.prototype || Object.keys(value).some(key => !allowed.includes(key))) {
    throw new Error("Unexpected NodalWire argument fields; no operation dispatched.");
  }
}
function networkName(value: unknown): string {
  if (value === undefined) return "default";
  if (!validName(value)) throw new Error("Invalid network name (ASCII letters/digits, _, ., -; max 128)");
  return value;
}
function cancelled(signal?: AbortSignal): void {
  if (signal?.aborted) throw new Error("NodalWire operation cancelled; effects may be uncertain. No automatic retry.");
}
function result(details: Record<string, unknown>, text: string) {
  return { content: [{ type: "text" as const, text }], details };
}
function metadata(message: NativeMessage) {
  return { id: message.id, network: message.network, ...(message.reply_to === undefined ? {} : { reply_to: message.reply_to }) };
}
function prefix(message: NativeMessage, recipient: string, replyRef?: string) {
  return `[NodalWire: ${message.sender} → ${recipient}; network=${message.network}; id=${message.id}` +
    (message.reply_to === undefined ? "" : `; reply_to=${message.reply_to}`) +
    (replyRef === undefined ? "" : `; replyRef=${replyRef}`) + "]\n";
}
function prefixedContent(message: PeerMessage, header: string) {
  return typeof message.content === "string" ? header + message.content
    : [{ type: "text" as const, text: header }, ...message.content];
}
function outbound(message: PeerMessage, options?: MessageOptions): Uint8Array {
  try { return encodeMessage(message, options); }
  catch { throw new Error("Invalid or oversized Pi v2 message/options; no message dispatched."); }
}

/** Bound serialized tool content, not only individual fields. Original reply stays
 * in result details. Never cut image bytes; partial text omits its signature. */
function boundedReplyContent(message: PeerMessage, header: string) {
  const content: ContentBlock[] = [{ type: "text", text: header }, ...(typeof message.content === "string"
    ? [{ type: "text" as const, text: message.content }] : message.content)];
  const size = (blocks: ContentBlock[]) => Buffer.byteLength(JSON.stringify(blocks), "utf8");
  if (size(content) <= MAX_REPLY_OUTPUT_BYTES) return { content, truncated: false };
  const note: ContentBlock = { type: "text", text: "[Reply truncated at the 50 KiB tool-output limit; original reply retained in tool result details.]" };
  const limited: ContentBlock[] = [];
  for (const block of content) {
    if (size([...limited, block, note]) <= MAX_REPLY_OUTPUT_BYTES) { limited.push(block); continue; }
    if (block.type === "text") {
      let low = 0, high = block.text.length;
      while (low < high) {
        const mid = Math.ceil((low + high) / 2);
        if (size([...limited, { type: "text", text: block.text.slice(0, mid) }, note]) <= MAX_REPLY_OUTPUT_BYTES) low = mid;
        else high = mid - 1;
      }
      // Do not leave half a surrogate pair at the text boundary.
      if (low > 0 && /[\uD800-\uDBFF]/.test(block.text[low - 1])) low--;
      if (low > 0) limited.push({ type: "text", text: block.text.slice(0, low) });
    }
    break;
  }
  return { content: [...limited, note], truncated: true };
}

export default function nodalwire(pi: ExtensionAPI) {
  registerNodalWire(pi, connectClient);
}

/**
 * Native SDK correlation owns reply matching. Ordinary receive stays independent.
 * Local delivery tickets and native message IDs are deliberately different.
 * References are session/connection-bound and never store peer message content.
 */
export function registerNodalWire(pi: ExtensionAPI, connect: Connect) {
  let active: Connection | undefined;
  let pending: AbortController | undefined;
  let revision = 0;
  let requests = 0;
  const replies = new ReplyReferences();
  // Neither reconnect nor reply matching resets unobserved Pi submissions.
  const pendingMessages = new Set<string>();
  let lastWarning = -Infinity;

  const notify = (ctx: ExtensionContext, text: string, level: "info" | "warning" = "info") => {
    if (ctx.hasUI) ctx.ui.notify(text, level);
    else console.error(`[nodalwire] ${text}`);
  };
  const warn = (ctx: ExtensionContext) => {
    if (performance.now() - lastWarning < 1000) return;
    lastWarning = performance.now();
    notify(ctx, "Rejected an invalid, oversized or over-capacity incoming message.", "warning");
  };
  const status = (ctx: ExtensionContext) => {
    if (ctx.hasUI) ctx.ui.setStatus("nodalwire", active ? `NW: ${active.name}` : undefined);
  };
  function connection(signal?: AbortSignal): Connection {
    cancelled(signal);
    if (!active) throw new Error("NodalWire is disconnected; use nodalwire_connection with an approved name and endpoint.");
    return active;
  }
  function assertCurrent(current: Connection, signal?: AbortSignal) {
    cancelled(signal);
    if (active !== current || current.abort.signal.aborted) {
      throw new Error("Connection changed; effects may be uncertain. No automatic retry.");
    }
  }
  async function transport<T>(operation: string, current: Connection, signal: AbortSignal | undefined,
    invoke: (signal: AbortSignal) => Promise<T>): Promise<T> {
    try {
      assertCurrent(current, signal);
      const combined = signal ? AbortSignal.any([signal, current.abort.signal]) : current.abort.signal;
      const value = await invoke(combined);
      assertCurrent(current, signal);
      return value;
    } catch (error) {
      throw safeTransportError(error, operation);
    }
  }

  async function closeClient(node: Client, ctx: ExtensionContext) {
    try { await node.close({ timeout: 1 }); }
    catch { notify(ctx, "Connection closed locally; relay release was not confirmed (lease may remain).", "warning"); }
  }

  async function disconnect(ctx: ExtensionContext) {
    revision++;
    pending?.abort();
    pending = undefined;
    replies.clear();
    const previous = active;
    active = undefined;
    status(ctx);
    if (previous) {
      previous.abort.abort();
      await closeClient(previous.node, ctx);
      await previous.done;
    }
  }

  async function receive(current: Connection, ctx: ExtensionContext) {
    try {
      while (active === current) {
        const incoming = await current.node.receive({ signal: current.abort.signal });
        if (active !== current) break;
        try {
          validateNativeMessage(incoming);
          const packet = decodeMessage(incoming.payload);
          if (pendingMessages.size >= MAX_PENDING_MESSAGES) throw new Error("Delivery capacity reached");
          const deliveryId = randomUUID();
          const replyRef = replies.add(current.generation, incoming);
          pendingMessages.add(deliveryId);
          try {
            pi.sendMessage({
              customType: MESSAGE_TYPE,
              content: prefixedContent(packet.message, prefix(incoming, current.name, replyRef)),
              display: packet.message.display,
              details: {
                sender: incoming.sender, recipient: current.name, deliveryId,
                ...metadata(incoming), ...(replyRef === undefined ? {} : { replyRef }),
                ...(Object.hasOwn(packet.message, "details") ? { peerDetails: packet.message.details } : {}),
              },
            }, packet.options);
          } catch (error) {
            pendingMessages.delete(deliveryId);
            if (replyRef !== undefined) replies.delete(replyRef);
            throw error;
          }
        } catch { warn(ctx); }
      }
    } catch {
      if (active === current) {
        active = undefined;
        replies.clear();
        current.abort.abort();
        status(ctx);
        notify(ctx, "Receive connection failed; disconnected. No automatic reconnect or replay.", "warning");
        await closeClient(current.node, ctx);
      }
    }
  }

  async function start(name: string, endpoint: string, ctx: ExtensionContext, signal?: AbortSignal) {
    if (!validName(name)) throw new Error("Invalid node name (ASCII letters/digits, _, ., -; max 128)");
    cancelled(signal);
    const closing = disconnect(ctx);
    const generation = ++revision;
    const abort = new AbortController();
    pending = abort;
    const cancel = () => abort.abort();
    signal?.addEventListener("abort", cancel, { once: true });
    try {
      await closing;
      if (signal?.aborted) cancel();
      if (generation !== revision || abort.signal.aborted) return;
      const node = await connect(name, endpoint, { signal: abort.signal });
      if (generation !== revision || abort.signal.aborted) {
        await closeClient(node, ctx);
        return;
      }
      const current: Connection = { node, name, endpoint, generation, abort, done: Promise.resolve() };
      active = current;
      current.done = receive(current, ctx);
      status(ctx);
      return current;
    } catch (error) {
      if (generation === revision) throw error;
    } finally {
      signal?.removeEventListener("abort", cancel);
      if (pending === abort) pending = undefined;
    }
  }

  function connectionResult() {
    const details = active
      ? { status: "connected", name: active.name, endpoint: active.endpoint }
      : { status: pending ? "connecting" : "disconnected" };
    const text = active ? `Connected as ${active.name} at ${active.endpoint}. Network membership is not confirmed by connection status.`
      : pending ? "NodalWire connection attempt is pending." : "NodalWire is disconnected locally.";
    return result(details, text);
  }

  pi.registerFlag("nodalwire-name", {
    description: "Opt in to NodalWire at session start using this unique logical node name", type: "string",
  });
  pi.registerFlag("nodalwire-endpoint", {
    description: `Trusted-loopback NodalWire relay endpoint (default ${DEFAULT_ENDPOINT})`,
    type: "string", default: DEFAULT_ENDPOINT,
  });
  pi.registerFlag("nodalwire-credentials", {
    description: "Operator-selected credential-alias JSON file; endpoint/network-bound environment references, not secret values",
    type: "string",
  });

  pi.on("session_start", async (_event, ctx) => {
    const name = pi.getFlag("nodalwire-name");
    if (typeof name !== "string" || !name) return;
    try { await start(name, String(pi.getFlag("nodalwire-endpoint") || DEFAULT_ENDPOINT), ctx); }
    catch { notify(ctx, "Could not connect. Check relay, unique node name and installed @devcapsule/nodalwire-client; use /nodalwire connect to retry.", "warning"); }
  });
  pi.on("session_shutdown", async (_event, ctx) => { await disconnect(ctx); });
  pi.on("message_end", event => {
    const message = event.message;
    if (message.role !== "custom" || message.customType !== MESSAGE_TYPE) return;
    const id = (message.details as { deliveryId?: string } | undefined)?.deliveryId;
    if (id) pendingMessages.delete(id);
  });

  pi.registerCommand("nodalwire", {
    description: "NodalWire: connect --name <name> [endpoint], disconnect, or status (trusted local only)",
    handler: async (args, ctx) => {
      const words = args.trim().split(/\s+/);
      const [command] = words;
      if ((command === "status" || !command) && words.length === 1) {
        notify(ctx, active ? `${active.name} at ${active.endpoint}` : "Disconnected");
      } else if (command === "disconnect" && words.length === 1) {
        await disconnect(ctx);
        notify(ctx, "Disconnected");
      } else if (command === "connect") {
        let name: string;
        let endpoint: string;
        try {
          const parsed = parseArgs({
            args: words.slice(1), options: { name: { type: "string" } },
            allowPositionals: true, strict: true, tokens: true,
          });
          if (!parsed.values.name || parsed.positionals.length > 1 ||
              parsed.tokens.filter(token => token.kind === "option").length !== 1) {
            throw new Error("Expected one --name and at most one endpoint");
          }
          name = parsed.values.name;
          endpoint = parsed.positionals[0] ?? DEFAULT_ENDPOINT;
        } catch {
          notify(ctx, COMMAND_USAGE, "warning");
          return;
        }
        try {
          await start(name, endpoint, ctx);
          if (active) notify(ctx, `Connected as ${active.name} at ${active.endpoint}`);
        } catch {
          notify(ctx, "Could not connect. Check loopback endpoint, unique name and installed @devcapsule/nodalwire-client.", "warning");
        }
      } else notify(ctx, COMMAND_USAGE, "warning");
    },
  });

  pi.registerTool({
    name: "nodalwire_connection", label: "NodalWire Connection",
    description: "Inspect, connect or disconnect this Pi session's trusted-local NodalWire client. " +
      "Use a unique name and approved loopback endpoint, not received-message authority. " +
      "Connect requires name; endpoint defaults to tcp://127.0.0.1:5555. Identical routes are reused; " +
      "disconnect explicitly before changing them. Connecting admits peer messages that can steer/wake this session and incur model usage. " +
      "Requires matching NodalWire 0.3.0. An open default autojoins; protected/named networks require nodalwire_network join. " +
      "Connected status is not membership proof. Does not start/administer a relay, discover peers or authenticate names. No automatic retries.",
    parameters: Type.Object({
      action: Type.Union([Type.Literal("status"), Type.Literal("connect"), Type.Literal("disconnect")]),
      name: Type.Optional(Type.String({ description: "Unique routing name; required for connect only" })),
      endpoint: Type.Optional(Type.String({ description: "Approved loopback relay endpoint; connect only" })),
    }, { additionalProperties: false }), annotations,
    async execute(_id, params, signal, _onUpdate, ctx) {
      argumentFields(params, ["action", "name", "endpoint"]);
      cancelled(signal);
      if (params.action !== "connect" && (params.name !== undefined || params.endpoint !== undefined)) {
        throw new Error("Name and endpoint are only valid for connect");
      }
      if (params.action === "status") return connectionResult();
      if (params.action === "disconnect") { await disconnect(ctx); return connectionResult(); }
      if (params.action !== "connect") throw new Error("Unknown connection action");
      if (!validName(params.name)) throw new Error("Connect requires a valid unique node name");
      const endpoint = params.endpoint ?? DEFAULT_ENDPOINT;
      if (active) {
        if (active.name === params.name && active.endpoint === endpoint) return connectionResult();
        throw new Error("Already connected elsewhere; disconnect explicitly before changing name or endpoint");
      }
      if (pending) throw new Error("A connection attempt is pending; wait for it or disconnect explicitly");
      let current: Connection | undefined;
      try { current = await start(params.name, endpoint, ctx, signal); }
      catch { throw new Error("Could not connect. Check loopback endpoint, unique name, relay admission and client dependency. No automatic retry."); }
      if (!current || active !== current) throw new Error("Connection attempt cancelled, superseded or lost");
      return connectionResult();
    },
  });

  pi.registerTool({
    name: "nodalwire_network", label: "NodalWire Network",
    description: "Explicitly join or leave an approved network on this connected NodalWire 0.3.0 relay. " +
      "Every named network needs a join, including open networks; protected default also needs a join. " +
      "For protected joins use only an operator-configured credentialRef alias from --nodalwire-credentials; never put secrets in arguments. " +
      "Joining does not select a send network. Leaving invalidates local reply references for that network, but cannot recall accepted messages. " +
      "Receipt describes that instant, not future membership. No relay administration, retries or authenticated-identity claim.",
    parameters: Type.Object({
      action: Type.Union([Type.Literal("join"), Type.Literal("leave")]),
      network: Type.String({ description: "Exact approved network name" }),
      credentialRef: Type.Optional(Type.String({ description: "Operator-configured alias; join only, never the credential value" })),
    }, { additionalProperties: false }), annotations,
    async execute(_id, params, signal, _onUpdate, ctx) {
      argumentFields(params, ["action", "network", "credentialRef"]);
      if (params.action !== "join" && params.action !== "leave") throw new Error("Unknown network action");
      if (!validName(params.network)) throw new Error("A valid network name is required");
      if (params.credentialRef !== undefined && !validName(params.credentialRef)) throw new Error("Invalid credential alias");
      if (params.action === "leave" && params.credentialRef !== undefined) throw new Error("Credential alias is valid for join only");
      const current = connection(signal);
      const receipt = await transport(params.action, current, signal, async operationSignal => {
        if (params.action === "leave") {
          replies.invalidateNetwork(current.generation, params.network);
          return current.node.leave(params.network, { signal: operationSignal });
        }
        const flag = pi.getFlag("nodalwire-credentials");
        const path = typeof flag === "string" && flag ? resolve(ctx.cwd, flag) : undefined;
        return withJoinCredential(path, params.credentialRef, { endpoint: current.endpoint, network: params.network }, async credential => {
          assertCurrent(current, operationSignal);
          return current.node.join(params.network, credential, { signal: operationSignal });
        });
      });
      assertCurrent(current, signal);
      if (receipt.network !== params.network || typeof receipt.joined !== "boolean" || typeof receipt.changed !== "boolean") {
        throw new Error("Invalid membership receipt; outcome uncertain. No automatic retry.");
      }
      return result({ network: receipt.network, joined: receipt.joined, changed: receipt.changed },
        `Network ${receipt.network}: joined=${receipt.joined}, changed=${receipt.changed}. Receipt is momentary, not future membership proof.`);
    },
  });

  pi.registerTool({
    name: "nodalwire_send", label: "NodalWire Send",
    description: "Send a Pi custom message to an explicitly known trusted-local peer on an approved network. " +
      "Requires a connection and both peers' membership; omitted network means literal default. " +
      "message mirrors pi.sendMessage: required content (text or text/image blocks), display; optional bounded JSON details. " +
      "Omitted options steer busy receivers without waking idle ones; triggerTurn:true may wake and consume quota; nextTurn never wakes. " +
      "v2 envelope maximum64KiB; content48KiB, details8KiB. Returns native id after relay acceptance, not receipt/action. " +
      "Names are not authenticated. No user messages, RPC, retries or replay; check uncertain effects before repeating.",
    parameters: Type.Object({ to: Type.String({ description: "Exact approved peer name" }), network: networkSchema, ...messageFields }, { additionalProperties: false }), annotations,
    async execute(_id, params, signal) {
      argumentFields(params, ["to", "network", "message", "options"]);
      if (!validName(params.to)) throw new Error("Invalid recipient name");
      const network = networkName(params.network);
      const payload = outbound(params.message as PeerMessage, params.options as MessageOptions | undefined);
      const current = connection(signal);
      const id = await transport("send", current, signal, operationSignal => current.node.send(params.to, payload, { network, signal: operationSignal }));
      assertCurrent(current, signal);
      return result({ to: params.to, network, id, status: "relay_accepted" },
        `Relay accepted message ${id} to ${params.to} on ${network}. Receipt and action are not confirmed.`);
    },
  });

  pi.registerTool({
    name: "nodalwire_request", label: "NodalWire Request",
    description: "Send one bounded native request and await a correlated Pi v2 reply from the exact peer/network. " +
      "Use for short queries, not long assignments; request content should explicitly ask for a reply using the receiver's replyRef. " +
      "Requires connection and membership; omitted network means default. timeoutSeconds defaults30, integer1..120; max4 in flight. " +
      "Options retain native Pi behavior: idle peers need an explicitly authorized wake; nextTurn never wakes. " +
      "Matched reply returns here only, not as a second Pi message. Unmatched/late replies remain ordinary messages and may wake this session. " +
      "SDK correlation is not identity authentication. Timeout/cancellation can follow delivery or action; no retries/replay. " +
      "Same v2 content48KiB/details8KiB/packet64KiB bounds as send. Tool content is limited to50KiB aggregate with explicit truncation; original reply remains in result details.",
    parameters: Type.Object({
      to: Type.String({ description: "Exact approved peer name" }), network: networkSchema, ...messageFields,
      timeoutSeconds: Type.Optional(Type.Integer({ minimum: 1, maximum: MAX_REQUEST_SECONDS, description: "One overall SDK deadline in seconds; default30" })),
    }, { additionalProperties: false }), annotations,
    async execute(_id, params, signal) {
      argumentFields(params, ["to", "network", "message", "options", "timeoutSeconds"]);
      if (!validName(params.to)) throw new Error("Invalid recipient name");
      const network = networkName(params.network);
      const timeout = params.timeoutSeconds ?? DEFAULT_REQUEST_SECONDS;
      if (!Number.isInteger(timeout) || timeout < 1 || timeout > MAX_REQUEST_SECONDS) throw new Error("Request timeout must be an integer between1 and120 seconds");
      const payload = outbound(params.message as PeerMessage, params.options as MessageOptions | undefined);
      const current = connection(signal);
      if (requests >= MAX_REQUESTS) throw new Error("NodalWire request capacity reached; maximum4 in flight. No request dispatched.");
      requests++;
      try {
        const incoming = await transport("request", current, signal, operationSignal => current.node.request(params.to, payload, { network, timeout, signal: operationSignal }));
        // transport's final check precedes this continuation by one microtask.
        assertCurrent(current, signal);
        let packet;
        try {
          validateNativeMessage(incoming);
          if (incoming.sender !== params.to || incoming.network !== network || incoming.reply_to === undefined) throw new Error("Mismatched native reply");
          packet = decodeMessage(incoming.payload);
        } catch { throw new Error("Invalid matched Pi reply; request finished. Do not automatically repeat a possibly completed operation."); }
        const replyRef = replies.add(current.generation, incoming);
        const output = boundedReplyContent(packet.message, prefix(incoming, current.name, replyRef));
        return {
          content: output.content,
          details: { status: "reply_received", truncated: output.truncated, sender: incoming.sender, ...metadata(incoming),
            ...(replyRef === undefined ? {} : { replyRef }), message: packet.message,
            ...(packet.options === undefined ? {} : { options: packet.options }) },
        };
      } finally { requests--; }
    },
  });

  pi.registerTool({
    name: "nodalwire_reply", label: "NodalWire Reply",
    description: "Reply once using a receiver-issued replyRef from this connection. No recipient/network/id overrides. " +
      "References expire after5minutes, clear on disconnect and invalidate when leaving their network; at most128 are retained. " +
      "Validate message/options before consuming the reference; one dispatch consumes it even if effect is uncertain. " +
      "Use native Pi message options explicitly; wake-ups may consume quota and nextTurn never wakes. " +
      "Returns accepted native id/reply_to/network, not receipt/action. Never retry an uncertain reply or treat a reference/name as authenticated identity. " +
      "Same v2 content48KiB/details8KiB/packet64KiB bounds as send.",
    parameters: Type.Object({ replyRef: Type.String({ description: "Opaque, single-use reference issued by this connection" }), ...messageFields }, { additionalProperties: false }), annotations,
    async execute(_id, params, signal) {
      argumentFields(params, ["replyRef", "message", "options"]);
      if (typeof params.replyRef !== "string" || !params.replyRef) throw new Error("A reply reference is required");
      const payload = outbound(params.message as PeerMessage, params.options as MessageOptions | undefined);
      const current = connection(signal);
      let incoming: NativeMessage;
      try { incoming = replies.take(current.generation, params.replyRef); }
      catch { throw new Error("Reply reference unavailable or expired; no reply dispatched."); }
      const id = await transport("reply", current, signal, operationSignal => current.node.reply(incoming, payload, { signal: operationSignal }));
      assertCurrent(current, signal);
      return result({ id, to: incoming.sender, network: incoming.network, reply_to: incoming.id, status: "relay_accepted" },
        `Relay accepted reply ${id} to ${incoming.sender} on ${incoming.network}, reply_to=${incoming.id}. Receipt and action are not confirmed.`);
    },
  });
}
