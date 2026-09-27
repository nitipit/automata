import { Base, tokens } from "/lib/adaptive-ui.js";
import "./message-composer.js";

export class BottomControls extends Base {
  #statusTimer;

  static {
    this.css = `
      display:block;
      position:relative;
      flex:none;
      width:100%;
      border:1px solid ${tokens.border};
      border-top:0;
      border-radius:0 0 var(--workspace-radius-sm) var(--workspace-radius-sm);
      background:${tokens.surface};
      .bar {
        display:flex;
        align-items:flex-end;
        gap:var(--workspace-space-md);
        padding:var(--workspace-space-md);
      }
      select, #conversation-toggle {
        flex:none;
        min-width:0;
        height:42px;
        padding:0 var(--workspace-space-sm);
        border:1px solid ${tokens.border};
        border-radius:var(--workspace-radius-sm);
        background:${tokens.surface};
        color:${tokens.text};
        font:inherit;
        cursor:pointer;
      }
      select { max-width:30%; }
      #conversation-toggle { white-space:nowrap; }
      #conversation-toggle[aria-expanded="true"] {
        border-color:${tokens.action};
        background:${tokens.action};
        color:${tokens.actionText};
      }
      select:focus-visible, button:focus-visible { outline:2px solid ${tokens.focus}; outline-offset:2px; }
      [hidden] { display:none !important; }
      @media(max-width:600px) {
        .bar { gap:var(--workspace-space-sm); padding:var(--workspace-space-sm); }
        select { max-width:29%; padding:0 var(--workspace-space-xs); font-size:.85rem; }
        #conversation-toggle { padding:0 var(--workspace-space-xs); font-size:.85rem; }
      }
    `;
  }

  constructor() {
    super();
    this.innerHTML = `
      <div class="bar" role="group" aria-label="Workspace controls">
        <button id="conversation-toggle" type="button" aria-controls="conversation-panel"
          aria-expanded="false" aria-label="Open conversation">Conversation</button>
        <wsp-composer></wsp-composer>
        <select id="agent" aria-label="Agent">
          <option value="agent-a">Aster</option>
          <option value="agent-b">Mira</option>
        </select>
      </div>`;
    this.querySelector("#conversation-toggle").addEventListener("click", () => {
      this.dispatchEvent(new Event("conversation-toggle"));
    });
    this.querySelector("#agent").addEventListener("change", (event) => {
      this.#emit("agent-change", event.target.value);
    });
    const composer = this.querySelector("wsp-composer");
    composer.addEventListener("draft-change", (event) => this.#emit("draft-change", event.detail));
    composer.addEventListener("send-message", (event) => this.#emit("send-message", event.detail));
    composer.addEventListener("draft-blur", () => this.dispatchEvent(new Event("draft-blur")));
    composer.addEventListener("reconcile-delivery", () => this.dispatchEvent(new Event("reconcile-delivery")));
    composer.addEventListener("copy-recovery", () => this.dispatchEvent(new Event("copy-recovery")));
  }

  #emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }
  get draftText() { return this.querySelector("wsp-composer").draftText; }
  present(state, name) {
    this.querySelector("#agent").value = state.conversations[state.view.selectedConversationId].agentId;
    const composer = this.querySelector("wsp-composer");
    composer.recipient = name;
    composer.draftText = state.conversations[state.view.selectedConversationId].draft;
  }
  setConversationOpen(open) {
    const toggle = this.querySelector("#conversation-toggle");
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", `${open ? "Close" : "Open"} conversation`);
  }
  focusConversationToggle() { this.querySelector("#conversation-toggle").focus(); }
  setStatus(message, kind = "") {
    clearTimeout(this.#statusTimer);
    const composer = this.querySelector("wsp-composer");
    composer.setStatus(message, kind);
    if (message === "All changes saved" || message === "Saved · real agent reply received") {
      this.#statusTimer = setTimeout(() => composer.setStatus(""), 2500);
    }
  }
  setLocked(locked) {
    this.querySelector("#agent").disabled = locked;
    this.querySelector("wsp-composer").locked = locked;
  }
  setConflict(visible) { this.querySelector("wsp-composer").setConflict(visible); }
  setDeliveryAction(options) { this.querySelector("wsp-composer").setDeliveryAction(options); }
}

BottomControls.define("wsp-controls");
