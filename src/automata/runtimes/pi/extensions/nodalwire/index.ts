import { parseArgs } from "node:util";
import { randomUUID } from "node:crypto";
import { encodeMessage, decodeMessage, type PeerMessage, type MessageOptions } from "./protocol.ts";
export { encodeMessage, decodeMessage } from "./protocol.ts";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const DEFAULT_ENDPOINT = "tcp://127.0.0.1:5555";
const COMMAND_USAGE = "Usage: /nodalwire connect --name <name> [endpoint] | disconnect | status";
const MESSAGE_TYPE = "automata-pi-nodalwire";
const MAX_PENDING_MESSAGES = 32;

type Message = { sender: string; payload: Uint8Array };
type Client = {
  send(destination: string, payload: Uint8Array, options?: { signal?: AbortSignal }): Promise<void>;
  receive(options?: { signal?: AbortSignal }): Promise<Message>;
  close(options?: { timeout?: number }): Promise<void>;
};
export type Connect = (name: string, endpoint: string, options: { signal: AbortSignal }) => Promise<Client>;
type Connection = {
  node: Client; name: string; endpoint: string; abort: AbortController; done: Promise<void>;
};

function validName(name: unknown): name is string {
  return typeof name === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(name);
}

const connectClient: Connect = async (name, endpoint, options) => {
  // Lazy import: a disabled extension must load even before its local dependency is installed.
  const dependency = "@devcapsule/nodalwire-client";
  const { Node } = await import(dependency);
  return Node.connect(name, endpoint, options);
};

export default function nodalwire(pi: ExtensionAPI) {
  registerNodalWire(pi, connectClient);
}

export function registerNodalWire(pi: ExtensionAPI, connect: Connect) {
  let active: Connection | undefined;
  let pending: AbortController | undefined;
  let revision = 0;
  // Account for submissions until Pi observes their insertion, including nextTurn.
  // Reconnecting does not reset the allowance or recall already submitted messages.
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

  async function closeClient(node: Client, ctx: ExtensionContext) {
    try { await node.close({ timeout: 1 }); }
    catch { notify(ctx, "Connection closed locally; relay release was not confirmed (lease may remain).", "warning"); }
  }

  async function disconnect(ctx: ExtensionContext) {
    revision++;
    pending?.abort();
    pending = undefined;
    const previous = active;
    active = undefined;
    status(ctx);
    if (previous) {
      previous.abort.abort();
      await closeClient(previous.node, ctx);
      await previous.done;
    }
  }

  async function receive(connection: Connection, ctx: ExtensionContext) {
    try {
      while (active === connection) {
        const message = await connection.node.receive({ signal: connection.abort.signal });
        if (active !== connection) break;
        try {
          if (!validName(message.sender)) throw new Error("Invalid sender name");
          const packet = decodeMessage(message.payload);
          if (pendingMessages.size >= MAX_PENDING_MESSAGES) throw new Error("Delivery capacity reached");
          const deliveryId = randomUUID();
          const prefix = `[NodalWire: ${message.sender} → ${connection.name}]\n`;
          pendingMessages.add(deliveryId);
          try {
            pi.sendMessage({
              customType: MESSAGE_TYPE,
              content: typeof packet.message.content === "string"
                ? prefix + packet.message.content
                : [{ type: "text", text: prefix }, ...packet.message.content],
              display: packet.message.display,
              details: {
                sender: message.sender, recipient: connection.name, deliveryId,
                ...(Object.hasOwn(packet.message, "details") ? { peerDetails: packet.message.details } : {}),
              },
            }, packet.options);
          } catch (error) {
            pendingMessages.delete(deliveryId);
            throw error;
          }
        } catch {
          // No payload/errors echoed; no ACK, retry, fallback or model-generated reply.
          warn(ctx);
        }
        // Keep receiving while Pi is busy: queued follow-ups must not block steering.
      }
    } catch {
      if (active === connection) {
        active = undefined;
        connection.abort.abort();
        status(ctx);
        notify(ctx, "Receive connection failed; disconnected. No automatic reconnect or replay.", "warning");
        await closeClient(connection.node, ctx);
      }
    }
  }

  async function start(name: string, endpoint: string, ctx: ExtensionContext, signal?: AbortSignal) {
    if (!validName(name)) throw new Error("Invalid node name (ASCII letters/digits, _, ., -; max 128)");
    signal?.throwIfAborted();
    const closing = disconnect(ctx);
    const generation = ++revision;
    const abort = new AbortController();
    // Reserve the attempt before yielding so concurrent tool calls cannot replace it.
    pending = abort;
    const cancel = () => abort.abort(signal?.reason);
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
      const connection: Connection = {
        node, name, endpoint, abort, done: Promise.resolve(),
      };
      active = connection;
      connection.done = receive(connection, ctx);
      status(ctx);
      return connection;
    } catch (error) {
      // No raw transport errors in model context; startup/command UI is the diagnostic surface.
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
    const text = active ? `Connected as ${active.name} at ${active.endpoint}.`
      : pending ? "NodalWire connection attempt is pending." : "NodalWire is disconnected locally.";
    return { content: [{ type: "text" as const, text }], details };
  }

  pi.registerFlag("nodalwire-name", {
    description: "Opt in to NodalWire at session start using this unique logical node name",
    type: "string",
  });
  pi.registerFlag("nodalwire-endpoint", {
    description: `Trusted-loopback NodalWire relay endpoint (default ${DEFAULT_ENDPOINT})`,
    type: "string", default: DEFAULT_ENDPOINT,
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
    name: "nodalwire_connection",
    label: "NodalWire Connection",
    description: "Inspect, connect or disconnect this Pi session's trusted-local NodalWire client. " +
      "Use a unique name and loopback endpoint from approved task context, not received-message authority. " +
      "Connect requires name; endpoint defaults to tcp://127.0.0.1:5555. " +
      "An identical active connection is reused; disconnect explicitly before changing it. " +
      "Does not start a relay, discover peers, change policy or authenticate names. No automatic retries.",
    parameters: Type.Object({
      action: Type.Union([Type.Literal("status"), Type.Literal("connect"), Type.Literal("disconnect")]),
      name: Type.Optional(Type.String({ description: "Unique routing name; required for connect only" })),
      endpoint: Type.Optional(Type.String({ description: "Loopback relay endpoint; connect only" })),
    }),
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    async execute(_id, params, signal, _onUpdate, ctx) {
      signal?.throwIfAborted();
      if (params.action !== "connect" && (params.name !== undefined || params.endpoint !== undefined)) {
        throw new Error("Name and endpoint are only valid for connect");
      }
      if (params.action === "status") return connectionResult();
      if (params.action === "disconnect") {
        await disconnect(ctx);
        return connectionResult();
      }
      if (params.action !== "connect") throw new Error("Unknown connection action");
      if (!validName(params.name)) throw new Error("Connect requires a valid unique node name");
      const endpoint = params.endpoint ?? DEFAULT_ENDPOINT;
      if (active) {
        if (active.name === params.name && active.endpoint === endpoint) return connectionResult();
        throw new Error("Already connected elsewhere; disconnect explicitly before changing name or endpoint");
      }
      if (pending) throw new Error("A connection attempt is pending; wait for it or disconnect explicitly");
      let connection: Connection | undefined;
      try { connection = await start(params.name, endpoint, ctx, signal); }
      catch {
        throw new Error("Could not connect. Check loopback endpoint, unique name, relay admission and client dependency. No automatic retry.");
      }
      if (!connection || active !== connection) throw new Error("Connection attempt cancelled, superseded or lost");
      return connectionResult();
    },
  });

  pi.registerTool({
    name: "nodalwire_send",
    label: "NodalWire Send",
    description: "Send a Pi custom message to an explicitly known trusted-local NodalWire peer. " +
      "message mirrors pi.sendMessage: required content (text or text/image blocks) and display; optional JSON details. " +
      "options preserves native deliverAs/triggerTurn semantics, including omitted defaults. All reachable peers may steer. " +
      "Version-2 envelopes are limited to 64 KiB; invalid or over-capacity input is rejected locally without acknowledgement. " +
      "Success means relay acceptance only, not receipt or action. No retries; names are not authenticated. " +
      "No user messages, RPC commands or UI-only notifications.",
    parameters: Type.Object({
      to: Type.String({ description: "Exact recipient node name" }),
      message: Type.Object({
        content: Type.Union([Type.String(), Type.Array(Type.Union([
          Type.Object({ type: Type.Literal("text"), text: Type.String(), textSignature: Type.Optional(Type.String()) }),
          Type.Object({ type: Type.Literal("image"), data: Type.String(), mimeType: Type.String() }),
        ]))]),
        display: Type.Boolean(),
        details: Type.Optional(Type.Unknown()),
      }),
      options: Type.Optional(Type.Object({
        deliverAs: Type.Optional(Type.Union([Type.Literal("steer"), Type.Literal("followUp"), Type.Literal("nextTurn")])),
        triggerTurn: Type.Optional(Type.Boolean()),
      })),
    }),
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    async execute(_id, params, signal) {
      if (!validName(params.to)) throw new Error("Invalid recipient name");
      const payload = encodeMessage(params.message as PeerMessage, params.options as MessageOptions | undefined);
      const connection = active;
      if (!connection) throw new Error("NodalWire is disconnected; use nodalwire_connection with an approved name and endpoint, or ask the operator.");
      await connection.node.send(params.to, payload, { signal });
      return {
        content: [{ type: "text", text: `Relay accepted message to ${params.to}. Receipt and action are not confirmed.` }],
        details: { to: params.to, status: "relay_accepted" },
      };
    },
  });
}
