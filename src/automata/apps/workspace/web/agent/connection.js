import { createMessageRouterClient } from "../router/client.js";
import { validateContent } from "../components/registry.js";

/** Explicit local assignment; participant-targeted transport, never history sync. */
export class AgentConnection {
  constructor(onChange = () => {}) {
    this.binding = null;
    this.onChange = onChange;
    this.phase = "disconnected";
    this.lastSession = null;
    this.attempted = false;
    this.client = createMessageRouterClient({ onState: event => {
      if (event.status === "disconnected" && this.phase !== "connecting") {
        this.phase = "disconnected";
        this.lastSession = null;
        this.publish();
      }
    } });
  }
  publish(detail = "") {
    this.onChange({ phase: this.phase, binding: this.binding, lastSession: this.lastSession,
      attempted: this.attempted, detail });
  }
  async initialize(api) {
    const { binding } = await api("/api/agent-binding");
    if (binding && (binding.agentId !== "agent-automata" || binding.displayName !== "Automata"
        || binding.conversationId !== "conversation-aster" || binding.to !== "workspace-agent")) {
      throw new Error("Unrecognized assigned-agent binding");
    }
    this.binding = binding;
    this.publish();
  }
  async connect() {
    if (!this.binding || this.phase === "connecting" || this.phase === "connected") return;
    this.attempted = true;
    this.phase = "connecting";
    this.lastSession = null;
    this.publish();
    try {
      await this.client.connect(this.binding.credentials);
      const status = await this.client.status();
      if (!status.destinations?.some(peer => peer.id === this.binding.to
          && peer.kind === "agent" && peer.connected)) {
        throw new Error("Assigned agent unavailable; it must join the router itself");
      }
      this.phase = "connected";
      this.publish();
    } catch (error) {
      this.phase = "disconnected";
      this.client.close();
      this.publish(error.message);
    }
  }
  disconnect() {
    this.phase = "disconnected";
    this.lastSession = null;
    this.client.close();
    this.publish();
  }
  isBound(conversationId) {
    return this.binding?.conversationId === conversationId && this.phase === "connected"
      && this.client.isConnected();
  }
  request(payload, onReceipt) {
    if (!this.isBound(payload.conversationId) || payload.agentId !== this.binding.agentId) {
      throw new Error("No connected assigned agent for this conversation");
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
              this.disconnect();
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
        }).catch(error => { this.disconnect(); finish(error); });
      } catch (error) { finish(error); }
    });
  }
}
