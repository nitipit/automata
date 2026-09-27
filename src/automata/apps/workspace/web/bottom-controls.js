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
      #agent, #conversation-toggle, .connection button {
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
      #agent { max-width:30%; display:flex; align-items:center; }
      .connection { padding:var(--workspace-space-sm); font-size:.8rem; }
      .connection button { height:30px; }
      .connection button:disabled { opacity:.5; cursor:default; }
      #connection-status { overflow-wrap:anywhere; }
      .connection p { margin:4px 0; }
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
        #agent { max-width:29%; padding:0 var(--workspace-space-xs); font-size:.85rem; }
        #conversation-toggle { padding:0 var(--workspace-space-xs); font-size:.85rem; }
      }
    `;
  }

  constructor() {
    super();
    this.innerHTML = `
      <div class="connection" aria-label="Agent connection">
        <button id="connect" type="button" disabled>Connect</button>
        <button id="disconnect" type="button" disabled>Disconnect</button>
        <span id="connection-status" role="status">Disconnected · assignment unavailable</span>
        <p>Reconnect restores transport only. History is not automatically supplied; agent context is unknown.</p>
      </div>
      <div class="bar" role="group" aria-label="Workspace controls">
        <button id="conversation-toggle" type="button" aria-controls="conversation-panel"
          aria-expanded="false" aria-label="Open conversation">Conversation</button>
        <wsp-composer></wsp-composer>
        <span id="agent" aria-label="Assigned agent">Unassigned</span>
      </div>`;
    this.querySelector("#conversation-toggle").addEventListener("click", () => {
      this.dispatchEvent(new Event("conversation-toggle"));
    });
    this.querySelector("#connect").addEventListener("click", () => this.dispatchEvent(new Event("connect-agent")));
    this.querySelector("#disconnect").addEventListener("click", () => this.dispatchEvent(new Event("disconnect-agent")));
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
    this.querySelector("#agent").textContent = name;
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
  setConnection({ phase, binding, lastSession, attempted, detail }) {
    this.querySelector("#connect").textContent = attempted ? "Reconnect" : "Connect";
    this.querySelector("#connect").disabled = !binding || phase !== "disconnected";
    this.querySelector("#disconnect").disabled = phase !== "connected";
    const status = phase === "connected" ? "Connected · router; assigned agent available at connection check"
      : phase === "connecting" ? "Connecting…" : "Disconnected";
    this.querySelector("#connection-status").textContent = `${status} · ${lastSession ? `last authenticated response runtime: ${lastSession}` : "runtime unknown"}${detail ? ` · ${detail}` : ""}`;
  }
  setLocked(locked) {
    this.querySelector("wsp-composer").locked = locked;
  }
  setConflict(visible) { this.querySelector("wsp-composer").setConflict(visible); }
  setDeliveryAction(options) { this.querySelector("wsp-composer").setDeliveryAction(options); }
}

BottomControls.define("wsp-controls");
