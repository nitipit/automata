import { Base, tokens } from "/lib/adaptive-ui.js";

export class MessageComposer extends Base {
  static {
    this.css = `
      display:block;
      flex:1;
      min-width:0;
      form { display:flex; flex-direction:column; min-width:0; }
      .meta {
        display:flex;
        flex-wrap:wrap;
        align-items:center;
        gap:var(--workspace-space-sm);
        min-height:32px;
        margin-bottom:var(--workspace-space-xs);
      }
      .notice { flex:1; min-width:0; color:${tokens.status}; font-size:.75rem; overflow-wrap:anywhere; }
      .notice[data-kind="error"] { color:${tokens.danger}; }
      .notice[data-kind="pending"] { color:var(--workspace-warning); }
      .actions { display:flex; flex-wrap:wrap; gap:var(--workspace-space-sm); }
      .actions:not(:has(button:not([hidden]))) { display:none; }
      button { min-height:32px; border:0; cursor:pointer; }
      .actions button { padding:0; background:transparent; color:${tokens.action}; font:inherit; font-size:.76rem; }
      #send {
        padding:0 var(--workspace-space-md);
        border-radius:var(--workspace-radius-sm);
        background:${tokens.action};
        color:${tokens.actionText};
        font:600 .86rem/1 system-ui;
      }
      #send:hover { background:${tokens.actionHover}; }
      button:focus-visible { outline:2px solid ${tokens.focus}; outline-offset:2px; }
      [hidden] { display:none !important; }
      textarea {
        display:block;
        width:100%;
        min-width:0;
        field-sizing:content;
        min-height:42px;
        max-height:30dvh;
        overflow-y:auto;
        padding:11px var(--workspace-space-sm);
        border:1px solid ${tokens.border};
        border-radius:var(--workspace-radius-sm);
        outline:0;
        resize:none;
        background:${tokens.surface};
        color:${tokens.text};
        font:inherit;
        line-height:1.3;
      }
      textarea::placeholder { color:${tokens.mutedText}; }
      textarea:focus { border-color:${tokens.focus}; box-shadow:0 0 0 2px var(--workspace-focus-soft); }
      :disabled { opacity:.5; cursor:not-allowed; }
    `;
  }

  constructor() {
    super();
    this.innerHTML = `
      <form>
        <div class="meta">
          <span class="notice" role="status" aria-live="polite"></span>
          <span class="actions"><button id="resolve-send" type="button" hidden>Check delivery</button><button id="copy-recovery" type="button" hidden>Copy local changes</button></span>
          <button id="send" type="submit" aria-label="Send message" hidden>Send</button>
        </div>
        <textarea id="compose" rows="1" aria-label="Message" placeholder="Message…"></textarea>
      </form>`;
    this.querySelector("textarea").addEventListener("input", (event) => {
      this.#syncSendVisibility();
      this.dispatchEvent(new CustomEvent("draft-change", { detail: event.target.value }));
    });
    this.querySelector("form").addEventListener("submit", (event) => {
      event.preventDefault();
      this.dispatchEvent(new CustomEvent("send-message", { detail: this.draftText.trim() }));
    });
    this.querySelector("textarea").addEventListener("blur", () => {
      this.dispatchEvent(new Event("draft-blur"));
    });
    this.querySelector("#resolve-send").addEventListener("click", () => {
      this.dispatchEvent(new Event("reconcile-delivery"));
    });
    this.querySelector("#copy-recovery").addEventListener("click", () => {
      this.dispatchEvent(new Event("copy-recovery"));
    });
    this.#syncMetaVisibility();
  }

  #syncMetaVisibility() {
    const hasAction = [...this.querySelectorAll(".actions button")].some((button) => !button.hidden);
    this.querySelector(".meta").hidden = !this.querySelector(".notice").textContent &&
      this.querySelector("#send").hidden && !hasAction;
  }
  #syncSendVisibility() {
    this.querySelector("#send").hidden = !this.draftText.trim();
    this.#syncMetaVisibility();
  }

  setStatus(message, kind = "") {
    const notice = this.querySelector(".notice");
    notice.textContent = message;
    notice.dataset.kind = kind;
    this.#syncMetaVisibility();
  }
  setConflict(visible) {
    this.querySelector("#copy-recovery").hidden = !visible;
    this.#syncMetaVisibility();
  }
  setDeliveryAction({ visible, label = "Check delivery" }) {
    const button = this.querySelector("#resolve-send");
    button.hidden = !visible;
    button.textContent = label;
    this.#syncMetaVisibility();
  }

  get draftText() { return this.querySelector("textarea").value; }
  set draftText(value) {
    const input = this.querySelector("textarea");
    if (input.value !== value) input.value = value;
    this.#syncSendVisibility();
  }
  set recipient(name) { this.querySelector("textarea").placeholder = `Message ${name}…`; }
  set locked(value) {
    this.querySelector("textarea").disabled = value;
    this.querySelector("#send").disabled = value;
  }
}

MessageComposer.define("wsp-composer");
