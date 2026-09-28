import { createMessageRouterClient } from "../router/client.js";
import { validateContent } from "../components/registry.js";

/** Automatic page transport only; explicit agent launch, never history/request replay. */
export class AgentConnection {
  constructor(onChange = () => {}) {
    this.binding = null;
    this.onChange = onChange;
    this.phase = "disconnected";
    this.lastSession = null;
    this.attempted = false;
    this.available = false;
    this.lifecycle = { configured: false, phase: "offline", action: null };
    this.retries = 0;
    this.stopped = false;
    this.launching = false;
    this.detail = "";
    this.generation = 0;
    this.client = createMessageRouterClient({ onState: event => {
      if (event.status === "disconnected" && this.phase !== "connecting") this.lost();
    } });
    this.wake = () => {
      if (this.stopped) return;
      if (this.phase !== "connected") { this.retries = 0; void this.connect(); }
      else void this.check();
    };
    globalThis.addEventListener?.("online", this.wake);
  }
  publish(detail = this.detail) {
    this.detail = detail;
    this.onChange({ phase: this.phase, binding: this.binding, lastSession: this.lastSession,
      attempted: this.attempted, detail, available: this.available,
      lifecycle: this.lifecycle, launching: this.launching });
  }
  async initialize(api) {
    const { binding } = await api("/api/agent-binding");
    if (binding && (binding.agentId !== "agent-automata" || binding.displayName !== "Automata"
        || binding.conversationId !== "conversation-aster" || binding.to !== "workspace-agent")) {
      throw new Error("Unrecognized assigned-agent binding");
    }
    this.binding = binding;
    this.api = api;
    await this.refreshLifecycle();
    this.publish();
    if (binding) await this.connect();
  }
  async refreshLifecycle() {
    try { this.lifecycle = await this.api("/api/agent-lifecycle"); }
    catch { this.lifecycle = { configured: false, phase: "failed", action: null }; }
  }
  async launch() {
    const action = this.lifecycle.action;
    if (this.launching || this.available || this.phase !== "connected"
        || !["start", "resume"].includes(action)) return;
    this.launching = true;
    this.publish("");
    try {
      this.lifecycle = await this.api(`/api/agent-lifecycle/${action}`, {
        method: "POST", body: JSON.stringify({ agentId: this.binding.agentId }),
      });
    } catch (error) {
      // An HTTP error may follow a spawn. Never retry the POST automatically.
      await this.refreshLifecycle();
      this.detail = `${error.message}; launch outcome must be checked, no automatic retry`;
    } finally { this.launching = false; this.publish(); }
  }
  async check() {
    if (this.checking || this.phase !== "connected" || this.stopped) return;
    this.checking = true;
    clearTimeout(this.checkTimer);
    try {
      const status = await this.client.status();
      if (this.stopped || this.phase !== "connected") return;
      this.retries = 0;
      this.available = status.destinations?.some(peer => peer.id === this.binding.to
        && peer.kind === "agent" && peer.connected) === true;
      if (!this.available) this.lastSession = null;
      await this.refreshLifecycle();
      this.publish("");
    } catch { this.lost(); }
    finally {
      this.checking = false;
      if (this.phase === "connected" && !this.stopped) {
        this.checkTimer = setTimeout(() => void this.check(), document.hidden ? 30000 : 5000);
      }
    }
  }
  lost() {
    this.phase = "disconnected";
    this.available = false;
    this.lastSession = null;
    clearTimeout(this.checkTimer);
    this.publish();
    this.recover();
  }
  recover() {
    if (this.stopped || this.retryTimer || !this.binding) return;
    if (this.retries >= 6) {
      this.publish("Router unavailable; recovery paused until network returns or page reload");
      return;
    }
    const delay = Math.min(1000 * 2 ** this.retries++, 15000);
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      void this.connect();
    }, delay);
  }
  async connect() {
    if (!this.binding || this.phase === "connecting" || this.phase === "connected") return;
    this.stopped = false;
    clearTimeout(this.retryTimer);
    this.retryTimer = null;
    this.attempted = true;
    const generation = ++this.generation;
    this.phase = "connecting";
    this.lastSession = null;
    this.publish();
    try {
      await this.client.connect(this.binding.credentials);
      if (this.stopped || generation !== this.generation) return;
      this.phase = "connected";
      await this.check();
    } catch (error) {
      if (this.stopped || generation !== this.generation) return;
      this.phase = "disconnected";
      this.client.close();
      this.publish(error.message);
      this.recover();
    }
  }
  disconnect() {
    // Internal disposal/testing only, not a conversation control.
    this.stopped = true;
    this.generation++;
    clearTimeout(this.retryTimer);
    this.retryTimer = null;
    clearTimeout(this.checkTimer);
    this.phase = "disconnected";
    this.available = false;
    this.lastSession = null;
    this.client.close();
    this.publish();
  }
  isBound(conversationId) {
    return this.binding?.conversationId === conversationId && this.phase === "connected" && this.available
      && this.client.isConnected();
  }
  deliver(payload) {
    if (!this.isBound(payload.context?.conversationId)) {
      throw new Error("Saved locally; no connected assigned agent for this destination");
    }
    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (error, response) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (error) reject(error); else resolve(response);
      };
      const timer = setTimeout(() => finish(new Error("Admission uncertain; saved input is not replayed")), 120000);
      try {
        const request = this.client.send(this.binding.to, payload, {
          metadata: { pi: { delivery: { role: "user", deliverAs: "followUp" } } },
          onResponse: response => {
            if (response.type === "route_closed") {
              finish(new Error("Admission uncertain after disconnect; not resent"));
              return;
            }
            if (response.from?.kind !== "agent" || response.from.id !== this.binding.to
                || typeof response.from.sessionId !== "string" || !response.from.sessionId) {
              finish(new Error("Unrecognized admission identity"));
              return;
            }
            this.lastSession = response.from.sessionId;
            this.publish();
            const pi = response.metadata?.pi;
            if (!response.final && pi?.type === "admitted") {
              finish(null, { status: "attached", participant: response.from.id, sessionId: response.from.sessionId });
            } else if (response.final) {
              if (response.payload?.status === "accepted" && response.payload.operationId === payload.operationId) {
                finish(null, { status: "attached", participant: response.from.id, sessionId: response.from.sessionId });
              } else finish(new Error("Agent rejected or did not acknowledge input; no automatic replay"));
            }
          },
        });
        request.accepted.catch(error => finish(error));
      } catch (error) { finish(error); }
    });
  }
  requestBoard(payload) {
    if (!this.binding) throw new Error("No assigned agent; board event not sent");
    if (payload.kind !== "workspace.webboard-event"
        || payload.projectId !== "project-northstar" || payload.webboardId !== "main"
        || "conversationId" in payload) throw new Error("Invalid board origin");
    return this.request({ ...payload, agentId: this.binding.agentId,
      target: { agentId: this.binding.agentId, participant: this.binding.to } }, null, true);
  }
  request(payload, onReceipt, board = false) {
    const bound = board ? this.binding && this.phase === "connected" && this.available
      && this.client.isConnected() : this.isBound(payload.conversationId);
    if (!bound || payload.agentId !== this.binding.agentId) {
      throw new Error(`No connected assigned agent for this ${board ? "webboard" : "conversation"}`);
    }
    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (error, value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (error) reject(error); else resolve(value);
      };
      const timer = setTimeout(() => finish(new Error("Agent response timed out; outcome uncertain, no resend")), 120000);
      try {
        const request = this.client.send(this.binding.to, payload, {
          metadata: { pi: { delivery: { role: "user", deliverAs: "followUp" } } },
          onResponse: response => {
            if (settled) return;
            if (response.type === "route_closed") {
              this.available = false;
              this.lastSession = null;
              this.publish("Agent route closed; outcome uncertain, no resend");
              void this.check();
              finish(new Error("Agent route closed; outcome uncertain, no resend"));
              return;
            }
            if (response.from?.kind !== "agent" || response.from.id !== this.binding.to
                || typeof response.from.sessionId !== "string" || !response.from.sessionId) {
              this.disconnect();
              finish(new Error("Unrecognized responder identity; response rejected"));
              return;
            }
            // Router-authenticated provenance identifies this response, not future
            // routes or context continuity. Credential custody remains trusted.
            this.lastSession = response.from.sessionId;
            this.publish();
            if (!response.final) {
              onReceipt?.(response.metadata?.pi);
              return;
            }
            try {
              if (board) {
                const reply = response.payload;
                if (!reply || typeof reply !== "object" || Array.isArray(reply)
                    || Object.keys(reply).sort().join() !== "kind,operationId,text,version"
                    || reply.kind !== "workspace.webboard-result" || reply.version !== 1
                    || reply.operationId !== payload.operationId
                    || typeof reply.text !== "string" || reply.text.length > 4000) {
                  throw new Error("Invalid correlated text-only board response");
                }
                finish(null, { text: reply.text, participant: response.from.id,
                  sessionId: response.from.sessionId, agentId: this.binding.agentId });
                return;
              }
              if (!response.payload || !Array.isArray(response.payload.content)) {
                throw new Error("Agent did not return the Workspace content contract");
              }
              finish(null, { content: validateContent(response.payload.content),
                participant: response.from.id, sessionId: response.from.sessionId,
                agentId: this.binding.agentId });
            } catch (error) { finish(error); }
          },
        });
        request.accepted.then(() => {
          if (!settled) onReceipt?.({ status: "forwarded" });
        }).catch(error => { void this.check(); finish(error); });
      } catch (error) { finish(error); }
    });
  }
}
