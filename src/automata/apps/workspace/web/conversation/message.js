import { Base } from "/lib/adaptive-ui.js";
import { createComponent, validateContent } from "../components/registry.js";

export class Message extends Base {
  static { this.css = "display:block; min-width:0; .delivery {font-size:.8rem;}"; }
  present(message, agentName, conversationId, historicalEvidence) {
    this.className = `message ${message.role}`;
    this.components ??= new Map();
    const speaker = this.speaker ??= document.createElement("span");
    speaker.className = "speaker";
    const simulated = message.provenance === "historical-simulation" || !message.content
      || message.text.startsWith("[Simulation]");
    const author = message.author ?? historicalEvidence;
    const assigned = author?.participant === "workspace-agent" && author?.sessionId;
    const historicalName = conversationId === "conversation-aster" ? "Aster" : "Mira";
    speaker.textContent = message.role === "user" ? "You" : simulated
      ? `${historicalName} · historical simulation`
      : assigned ? `Automata · recorded runtime ${author.sessionId}`
      : "Historical agent · identity unverified";
    if (!speaker.isConnected) this.append(speaker);
    const content = message.content ?? [{ id: "legacy-text", type: "text", version: 1, data: { text: message.text } }];
    for (const description of content) {
      try {
        let component = this.components.get(description.id);
        if (!component) {
          component = createComponent(description, message.interactions?.[description.id]);
          for (const type of ["component-draft", "component-submit"]) {
            component.addEventListener(type, event => {
              event.stopPropagation();
              this.dispatchEvent(new CustomEvent(type, { bubbles: true, composed: true,
                detail: { ...event.detail, conversationId, messageId: message.id, componentId: description.id } }));
            });
          }
          this.components.set(description.id, component);
          this.append(component);
        } else {
          const validated = validateContent([description])[0];
          component.applyData(validated.data, message.interactions?.[description.id]);
        }
      } catch (error) {
        if (this.components.has(description.id)) continue;
        const fallback = document.createElement("p");
        fallback.textContent = `Cannot display component: ${error.message}`;
        fallback.setAttribute("role", "alert");
        this.components.set(description.id, fallback);
        this.append(fallback);
      }
    }
    if (message.delivery) {
      const status = this.deliveryStatus ??= document.createElement("p");
      status.className = "delivery";
      status.textContent = `${message.delivery.status} · ${message.delivery.detail ?? "Local record saved; this is not agent acknowledgement"}`;
      if (!status.isConnected) this.append(status);
    }
  }
}
Message.define("wsp-message");
