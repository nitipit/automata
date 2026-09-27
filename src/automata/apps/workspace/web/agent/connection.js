import { createMessageRouterClient } from "../router/client.js";
import { validateContent } from "../components/registry.js";

/** One explicit binding, no reconnect/replay or transport-to-business promotion. */
export class AgentConnection {
  constructor() {
    this.client = createMessageRouterClient();
    this.binding = null;
  }
  async initialize(api) {
    const { binding } = await api("/api/agent-binding");
    this.binding = binding;
    if (binding) await this.client.connect(binding.credentials);
  }
  isBound(conversationId) {
    return this.binding?.conversationId === conversationId && this.client.isConnected();
  }
  request(payload, onReceipt) {
    if (!this.isBound(payload.conversationId)) throw new Error("No connected real agent is bound to this conversation");
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
              finish(new Error("Agent route closed; outcome uncertain, no resend"));
              return;
            }
            if (!response.final) {
              onReceipt?.(response.metadata?.pi);
              return;
            }
            try {
              if (!response.payload || !Array.isArray(response.payload.content)) {
                throw new Error("Agent did not return the Workspace content contract");
              }
              finish(null, { content: validateContent(response.payload.content),
                participant: response.from.id, sessionId: response.from.sessionId });
            } catch (error) { finish(error); }
          },
        });
        request.accepted.then(() => {
          if (!settled) onReceipt?.({ status: "forwarded" });
        }).catch(error => finish(error));
      } catch (error) { finish(error); }
    });
  }
}
