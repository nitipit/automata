/** Pi-side wire adapter. Owns sockets and bounded reply records, never Pi context. */
import { access, readFile, stat } from "node:fs/promises";
import { isAbsolute, resolve } from "node:path";
import type { BrowserEnvelope, Endpoint, JsonRecord, PendingRequest, Sender } from "./protocol.ts";
import { MAX_ENDPOINT_BYTES, MAX_FRAME_BYTES, parseRecord, isBrowserEnvelope,
         isRecord, isBoundedId, serializePayload, serializeMetadata, isDelivery } from "./protocol.ts";

type Outbound = { id: string; to: string; routeId?: string; status: string; final: boolean;
                  payload?: unknown; metadata?: unknown; from?: Sender };

export class ControlClient {
  private readonly pending = new Map<string, PendingRequest>();
  private readonly outbound = new Map<string, Outbound>();
  private readonly inbound = new Set<string>();
  private closed = false;
  private active = false;
  private readonly early: BrowserEnvelope[] = [];
  private readonly socket: WebSocket;
  private readonly endpoint: Endpoint;
  private readonly onEvent: (message: BrowserEnvelope) => void;

  private constructor(socket: WebSocket, endpoint: Endpoint,
                      onEvent: (message: BrowserEnvelope) => void) {
    this.socket = socket; this.endpoint = endpoint; this.onEvent = onEvent;
    socket.onmessage = event => this.receive(event.data);
    socket.onerror = () => this.close();
    socket.onclose = () => this.close();
  }

  static async connect(endpoint: Endpoint, sessionId: string,
                       onEvent: (message: BrowserEnvelope) => void): Promise<ControlClient> {
    if (typeof WebSocket === "undefined") throw new Error("This Pi runtime has no WebSocket support");
    const socket = new WebSocket(endpoint.wsUrl);
    const client = new ControlClient(socket, endpoint, onEvent);
    await new Promise<void>((resolvePromise, reject) => {
      const finish = (error?: Error) => {
        clearTimeout(timeout);
        socket.removeEventListener("message", onMessage);
        socket.removeEventListener("error", failed);
        socket.removeEventListener("close", failed);
        if (error) { client.close(); reject(error); } else resolvePromise();
      };
      const timeout = setTimeout(() => finish(new Error("Router authentication timed out")), 5000);
      const failed = () => finish(new Error("Router authentication failed"));
      const onMessage = (event: MessageEvent) => {
        try {
          const value = parseRecord(event.data);
          if (value.type === "error") return failed();
          if (value.type !== "hello_ack") return;
          if (endpoint.v === 2 ? value.v !== 2 || value.participant !== endpoint.participant || value.kind !== "agent" : value.role !== "control") return failed();
          finish();
        } catch { failed(); }
      };
      socket.addEventListener("message", onMessage);
      socket.addEventListener("error", failed, {once:true});
      socket.addEventListener("close", failed, {once:true});
      socket.addEventListener("open", () => {
        try {
          socket.send(JSON.stringify(endpoint.v === 2
            ? {v:2,type:"hello",participant:endpoint.participant,token:endpoint.token,sessionId}
            : {type:"hello",role:"control",token:endpoint.controlToken,sessionId,deliveryOptions:1}));
        } catch { failed(); }
      }, {once:true});
    });
    return client;
  }

  activate(): void {
    if (this.closed) throw new Error("Connection closed during activation");
    this.active = true;
    for (const message of this.early.splice(0)) this.onEvent(message);
  }

  private deliver(message: BrowserEnvelope): void {
    if (this.active) this.onEvent(message);
    else if (this.early.length < 64) this.early.push(message);
    else throw new Error("Pre-activation capacity reached");
  }

  request(action: string, fields: JsonRecord = {}): Promise<JsonRecord> {
    if (this.closed) return Promise.reject(new Error("Agent router is disconnected; delivery uncertain"));
    if (this.endpoint.v !== 2) return this.rpc({type:"control",action,...fields});
    if (action === "state") return Promise.resolve({busy:isRecord(fields.payload) && fields.payload.busy});
    if (action === "open") return Promise.resolve({status:"open",participant:this.endpoint.participant});
    if (action === "status") return this.rpc({type:"status"}).then(value => ({...value,outgoing:this.inspectOutgoing()}));
    if (action === "close") { this.close(); return Promise.resolve({status:"closed"}); }
    let id: unknown, payload: unknown = null, pi: JsonRecord, final = true;
    if (action === "send") {
      if (!isRecord(fields.envelope)) throw new Error("Missing reply envelope");
      id = fields.envelope.correlationId; payload = fields.envelope.payload; pi = {type:"reply"};
    } else if (action === "admit") {
      id = fields.id; pi = {type:"admitted"}; final = false;
    } else if (action === "reject") {
      id = fields.correlationId; pi = {type:"rejected",error:{code:fields.code,message:fields.message}};
    } else if (action === "context_result") {
      id = fields.id; pi = {type:"context_result",status:fields.status,details:fields.details ?? {}};
      final = !["buffered","queued"].includes(String(fields.status));
    } else throw new Error(`Unsupported Pi adapter action: ${action}`);
    if (!isBoundedId(id)) throw new Error("Invalid reply capability");
    if (!this.inbound.has(id)) return Promise.resolve({status:"uncertain",browserDelivered:false});
    serializePayload(payload); serializeMetadata({pi});
    const response = this.rpc({type:"respond",routeId:id,payload,metadata:{pi},final});
    if (final) this.inbound.delete(id);
    return response.then(value => ({...value,browserDelivered:value.status === "forwarded"}));
  }

  /** Submit explicitly; receive() consumes terminal replies without starting model turns. */
  async route(to: string, payload: unknown, metadata: unknown): Promise<JsonRecord> {
    if (this.endpoint.v !== 2) throw new Error("Targeted routing requires a v2 participant endpoint");
    if (!isBoundedId(to)) throw new Error("Invalid destination");
    serializePayload(payload); serializeMetadata(metadata);
    if (this.outbound.size >= 32) throw new Error("Outgoing capacity reached; receive or cancel requests first");
    const id = crypto.randomUUID();
    const entry: Outbound = {id,to,status:"sending",final:false};
    this.outbound.set(id, entry);
    try {
      const accepted = await this.rpc({type:"route",to,payload,metadata,expectReply:true}, id);
      if (typeof accepted.routeId !== "string") throw new Error("Missing route acknowledgment");
      if (entry.routeId && entry.routeId !== accepted.routeId) throw new Error("Mismatched route acknowledgment");
      entry.routeId = accepted.routeId;
      // An application response may precede the transport acknowledgment.
      if (entry.status === "sending") entry.status = String(accepted.status);
      if (accepted.status !== "forwarded") entry.final = true;
      return {status:accepted.status,id,routeId:accepted.routeId,to};
    } catch (error) {
      this.outbound.delete(id);
      throw error;
    }
  }

  inspectOutgoing() {
    return [...this.outbound.values()].map(({id,to,status,final}) => ({id,to,status,final}));
  }

  receiveReply(id: string): Outbound {
    const entry = this.outbound.get(id);
    if (!entry) throw new Error("No matching outgoing request");
    if (entry.final) this.outbound.delete(id);
    return {...entry};
  }

  async cancel(id: string): Promise<JsonRecord> {
    const entry = this.outbound.get(id);
    if (!entry?.routeId) throw new Error("No acknowledged outgoing route");
    this.outbound.delete(id);
    if (entry.final) return {status:"forgotten",id};
    return this.rpc({type:"cancel",routeId:entry.routeId});
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.failAll(new Error("Agent router closed; pending delivery uncertain"));
    for (const entry of this.outbound.values()) {
      if (!entry.final) { entry.status = "uncertain"; entry.final = true; }
    }
    this.inbound.clear();
    this.early.length = 0;
    this.socket.close();
  }

  private rpc(fields: JsonRecord, requestId = crypto.randomUUID()): Promise<JsonRecord> {
    if (this.closed) throw new Error("Agent router is disconnected; delivery uncertain");
    if (this.pending.size >= 64) throw new Error("Transport request capacity reached");
    const encoded = JSON.stringify({...(this.endpoint.v === 2 ? {v:2} : {}),...fields,requestId});
    if (new TextEncoder().encode(encoded).byteLength > MAX_FRAME_BYTES) throw new Error("Control frame exceeds 64 KiB");
    return new Promise((resolvePromise, reject) => {
      const timer = setTimeout(() => this.close(), 5000);
      this.pending.set(requestId, {resolve:resolvePromise,reject,timer});
      try { this.socket.send(encoded); }
      catch { this.close(); }
    });
  }

  private receive(raw: unknown): void {
    if (this.closed) return;
    try {
      const value = parseRecord(raw);
      if (this.endpoint.v === 2) {
        if (value.type === "error") throw new Error("Router protocol error");
        if (value.v !== 2) throw new Error("Invalid router version");
        if (value.type === "message") { this.receiveMessage(value); return; }
        if (value.type === "response") { this.receiveResponse(value); return; }
        if (value.type === "route_closed") {
          if (isBoundedId(value.id)) this.inbound.delete(value.id);
          const entry = typeof value.requestId === "string" ? this.outbound.get(value.requestId) : undefined;
          if (entry && (!entry.routeId || entry.routeId === value.id)) { entry.status = "uncertain"; entry.final = true; }
          return;
        }
      } else if (value.type === "event") {
        if (!isBrowserEnvelope(value.envelope) || value.envelope.kind === "reply") throw new Error("Invalid Pi message envelope");
        this.deliver(value.envelope);
        return;
      }
      if (typeof value.requestId !== "string") return;
      const pending = this.pending.get(value.requestId);
      if (!pending) return;
      this.pending.delete(value.requestId); clearTimeout(pending.timer);
      if (value.type === "error" || value.status === "rejected") pending.reject(new Error(String(value.error ?? value.message ?? "Router request rejected")));
      else pending.resolve(value);
    } catch { this.close(); }
  }

  private receiveMessage(value: JsonRecord): void {
    if (!isBoundedId(value.id) || !isRecord(value.from) || !isBoundedId(value.from.id) || !["page","agent"].includes(String(value.from.kind)) || value.to !== this.endpoint.participant) throw new Error("Invalid sender/destination");
    // Pi admission always needs a receipt channel. Fire-and-forget notifications
    // are for non-Pi handlers; they never implicitly launch a model turn.
    if (value.expectReply !== true) return;
    if (this.inbound.size >= 64 || this.inbound.has(value.id)) throw new Error("Inbound request capacity or duplicate");
    this.inbound.add(value.id);
    try {
      serializePayload(value.payload);
      const pi = isRecord(value.metadata) && Object.hasOwn(value.metadata,"pi") ? value.metadata.pi : {};
      if (!isRecord(pi)) throw new Error("Invalid Pi metadata");
      let envelope: BrowserEnvelope;
      if (pi.kind === "context_control") {
        if (Object.keys(pi).some(key => !["kind","action","slot"].includes(key))) throw new Error("Invalid context control");
        envelope = {v:1,kind:"context_control",id:value.id,action:pi.action as "inspect"|"clear",...(pi.slot === undefined ? {} : {slot:pi.slot as string}),payload:null};
        // v1 controls intentionally omit payload; use the existing validator.
        const {payload:_, ...control} = envelope;
        if (!isBrowserEnvelope(control)) throw new Error("Invalid context control");
      } else {
        if (Object.keys(pi).some(key => !["delivery"].includes(key))) throw new Error("Invalid Pi message metadata");
        let delivery;
        if (Object.hasOwn(pi,"delivery")) {
          if (!isRecord(pi.delivery)) throw new Error("Invalid delivery options");
          delivery = {role:"user",deliverAs:"immediate",...pi.delivery};
          if (!isDelivery(delivery)) throw new Error("Invalid delivery options");
        }
        envelope = {v:1,kind:"message",id:value.id,payload:value.payload as BrowserEnvelope["payload"],...(delivery ? {delivery} : {})};
      }
      envelope.sender = value.from as Sender;
      this.deliver(envelope);
    } catch {
      void this.request("reject",{correlationId:value.id,code:"invalid_delivery",message:"Unsupported Pi request or delivery options"}).catch(() => undefined);
    }
  }

  private receiveResponse(value: JsonRecord): void {
    const entry = typeof value.requestId === "string" ? this.outbound.get(value.requestId) : undefined;
    if (!entry || entry.final) return;
    if (!isBoundedId(value.id) || !isRecord(value.from) || value.from.id !== entry.to || (entry.routeId && entry.routeId !== value.id) || typeof value.final !== "boolean") throw new Error("Invalid peer reply correlation");
    serializePayload(value.payload); serializeMetadata(value.metadata);
    // Retain only the latest bounded receipt, never an unbounded event history.
    const pi = isRecord(value.metadata) && isRecord(value.metadata.pi) ? value.metadata.pi : undefined;
    const status = pi?.type === "rejected" ? "rejected" : pi?.type === "admitted" ? "admitted"
      : pi?.type === "context_result" && typeof pi.status === "string" &&
        ["buffered","queued","attached","replaced","cleared","rejected","inspected","uncertain"].includes(pi.status) ? pi.status
      : value.final ? "replied" : "pending";
    Object.assign(entry,{routeId:value.id,status,final:value.final,
                         payload:value.payload,metadata:value.metadata,from:value.from});
  }

  private failAll(error: Error): void {
    for (const request of this.pending.values()) { clearTimeout(request.timer); request.reject(error); }
    this.pending.clear();
  }
}

export async function assertInstalledTool(cwd: string): Promise<void> {
  // Only the v1 compatibility path uses this historical preflight.
  for (const root of [".agents/tools/agent-router", ".agents/tools/agent-browser-bridge"]) {
    try {
      for (const file of ["agent_browser_bridge.py","browser/client.js","browser/page.js"])
        if (!(await stat(resolve(cwd,root,file))).isFile()) throw new Error("Missing artifact");
      return;
    } catch { /* Check the explicitly supported legacy installation next. */ }
  }
  throw new Error("Installed agent router/bridge artifacts are missing; install before opening a legacy binding");
}

export async function readEndpoint(cwd: string, configuredPath?: string, legacy = false): Promise<Endpoint> {
  const configured = configuredPath ?? (legacy ? process.env.AUTOMATA_AGENT_BROWSER_BRIDGE_ENDPOINT : process.env.AUTOMATA_AGENT_ROUTER_ENDPOINT);
  const relative = legacy ? ".agents/var/tools/agent-browser-bridge/endpoint.json" : ".agents/var/tools/agent-router/endpoints/participants/agent.json";
  const path = configured ? (isAbsolute(configured) ? configured : resolve(cwd,configured)) : resolve(cwd,relative);
  try {
    await access(path);
    const info = await stat(path);
    if (!info.isFile() || info.size > MAX_ENDPOINT_BYTES) throw new Error("Invalid endpoint file");
    const value = JSON.parse(await readFile(path,"utf8")) as JsonRecord;
    if (typeof value.wsUrl !== "string" || typeof value.publicUrl !== "string") throw new Error("Invalid endpoint URLs");
    const url = new URL(value.wsUrl);
    if (!["ws:","wss:"].includes(url.protocol) || url.username || url.password) throw new Error("Invalid endpoint URL");
    if (value.v === 2) {
      if (!isBoundedId(value.participant) || typeof value.token !== "string" || !value.token || value.token.length > 256 || value.kind !== "agent") throw new Error("An agent participant credential is required");
      return {v:2,wsUrl:value.wsUrl,publicUrl:value.publicUrl,participant:value.participant,token:value.token,kind:"agent"};
    }
    if (typeof value.controlToken !== "string") throw new Error("Missing legacy credential");
    return {wsUrl:value.wsUrl,publicUrl:value.publicUrl.replace(/\/$/,""),controlToken:value.controlToken};
  } catch {
    throw new Error(`Agent router endpoint unavailable at ${path}; start the intended server explicitly`);
  }
}
