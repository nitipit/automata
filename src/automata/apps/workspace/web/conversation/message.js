import { Base } from "/lib/adaptive-ui.js";
import { createComponent } from "../components/registry.js";

export class Message extends Base {
  static { this.css = "display:block; min-width:0; .delivery {font-size:.8rem;}"; }
  present(message, agentName, conversationId, historicalEvidence) {
    this.replaceChildren();
    this.className = `message ${message.role}`;
    const speaker = document.createElement("span");
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
    this.append(speaker);
    const content = message.content ?? [{ id: "legacy-text", type: "text", version: 1, data: { text: message.text } }];
    for (const description of content) {
      try {
        const component = createComponent(description, message.interactions?.[description.id]);
        for (const type of ["component-draft", "component-submit"]) {
          component.addEventListener(type, event => {
            event.stopPropagation();
            this.dispatchEvent(new CustomEvent(type, { bubbles: true, composed: true,
              detail: { ...event.detail, conversationId, messageId: message.id, componentId: description.id } }));
          });
        }
        this.append(component);
      } catch (error) {
        const fallback = document.createElement("p");
        fallback.textContent = `Cannot display component: ${error.message}`;
        fallback.setAttribute("role", "alert");
        this.append(fallback);
      }
    }
    if (message.delivery) {
      const status = document.createElement("p");
      status.className = "delivery";
      status.textContent = `${message.delivery.status} · ${message.delivery.detail ?? "Local record saved; this is not agent acknowledgement"}`;
      this.append(status);
    }
  }
}
Message.define("wsp-message");
