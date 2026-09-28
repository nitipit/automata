import { Base, tokens } from "/lib/adaptive-ui.js";

const BOARD_URL = "/boards/project-northstar/main/index.html";
const boundedId = value => typeof value === "string" && /^[a-zA-Z0-9_-]{1,80}$/.test(value);

// The host owns location, actor and destination. Board messages are proposals,
// not human authority: a host-owned confirmation is required before routing.
export class WorkSurface extends Base {
  static {
    this.css = `
      display:flex; flex:1; min-width:0; min-height:0; flex-direction:column;
      background:${tokens.surface};
      iframe { display:block; width:100%; flex:1; min-height:0; border:0; }
      .board-request { padding:12px 24px; border-top:1px solid ${tokens.border};
        max-height:55%; overflow:auto; flex-shrink:0; box-sizing:border-box; }
      p { margin:0 0 8px; white-space:pre-wrap; overflow-wrap:anywhere; }
      button { padding:8px 12px; margin-right:8px; cursor:pointer; }
      button:focus-visible { outline:2px solid ${tokens.focus}; }
      [hidden] { display:none; }
    `;
  }
  constructor() {
    super();
    this.innerHTML = `
      <iframe title="Northstar · Main webboard" sandbox="allow-scripts"
        referrerpolicy="no-referrer" src="${BOARD_URL}"></iframe>
      <section class="board-request" aria-label="Webboard event" hidden>
        <p class="preview"></p>
        <button class="confirm" type="button">Send board event to Automata</button>
        <button class="dismiss" type="button">Dismiss</button>
        <p class="status" role="status"></p>
      </section>`;
    this.frame = this.querySelector("iframe");
    this.panel = this.querySelector("section");
    this.confirm = this.querySelector(".confirm");
    this.dismiss = this.querySelector(".dismiss");
    this.loads = 0;
    this.used = new Set();
    this.lastProposal = -Infinity;
    this.receive = event => this.propose(event);
    this.frame.addEventListener("load", () => {
      this.generation = null;
      this.replyPort?.close();
      this.replyPort = null;
      this.pending = null;
      this.confirm.hidden = this.dismiss.hidden = true;
      if (++this.loads !== 1) {
        this.panel.hidden = false;
        this.status("Board navigated; its event capability is revoked until page reload.");
        return;
      }
      this.generation = crypto.randomUUID();
      const channel = new MessageChannel();
      this.replyPort = channel.port1;
      // A document-owned reply port avoids WindowProxy delivery to a replacement
      // document during the interval BEFORE its navigation load event revokes us.
      this.frame.contentWindow.postMessage({ kind: "workspace.board-init", version: 1,
        generation: this.generation }, "*", [channel.port2]);
    });
    this.confirm.addEventListener("click", () => void this.send());
    this.dismiss.addEventListener("click", () => { this.pending = null; this.panel.hidden = true; });
  }
  connectedCallback() {
    super.connectedCallback?.();
    window.addEventListener("message", this.receive);
  }
  disconnectedCallback() {
    window.removeEventListener("message", this.receive);
    this.replyPort?.close();
    this.generation = null;
    super.disconnectedCallback?.();
  }
  status(text) { this.querySelector(".status").textContent = text; }
  propose(event) {
    if (event.source !== this.frame.contentWindow || event.origin !== "null"
        || !this.generation || this.pending || this.inFlight || this.used.size >= 100
        || performance.now() - this.lastProposal < 1000) return;
    const value = event.data;
    if (!value || typeof value !== "object" || Array.isArray(value)
        || Object.keys(value).sort().join() !== "componentId,generation,kind,operationId,text,version"
        || value.kind !== "workspace.board-proposal" || value.version !== 1
        || value.generation !== this.generation || !boundedId(value.componentId)
        || !boundedId(value.operationId) || this.used.has(value.operationId)
        || typeof value.text !== "string" || !value.text.trim() || value.text.length > 2000) return;
    this.lastProposal = performance.now();
    this.used.add(value.operationId);
    this.pending = { componentId: value.componentId, operationId: value.operationId, text: value.text };
    this.panel.hidden = false;
    this.confirm.hidden = this.dismiss.hidden = false;
    this.querySelector(".preview").textContent =
      `Source: project-northstar / main\nComponent: ${value.componentId}\n`
      + `Operation: ${value.operationId}\nAction: notify-agent → Automata\n\n${value.text}`;
    this.status("Review this untrusted board text. Sending does not authorize other actions.");
  }
  async send() {
    if (!this.pending || this.inFlight || !this.generation) return;
    const proposal = this.pending;
    const generation = this.generation;
    this.pending = null;
    this.inFlight = true;
    this.confirm.hidden = this.dismiss.hidden = true;
    const payload = {
      kind: "workspace.webboard-event", version: 1,
      projectId: "project-northstar", webboardId: "main",
      origin: { projectId: "project-northstar", webboardId: "main" },
      actor: { kind: "local-user", id: "local-user", authority: "host-confirmed-notification" },
      componentId: proposal.componentId, operationId: proposal.operationId,
      action: "notify-agent", text: proposal.text,
    };
    this.status("Awaiting assigned agent; no automatic retry.");
    try {
      if (!this.exchange) throw new Error("Assigned agent unavailable; nothing sent");
      const reply = await this.exchange(payload);
      if (this.generation !== generation) return;
      this.status(reply.text);
      this.replyPort?.postMessage({ kind: "workspace.board-result", version: 1,
        generation, operationId: proposal.operationId, text: reply.text });
    } catch (error) {
      if (this.generation === generation) this.status(String(error.message).slice(0, 1000));
    } finally { this.inFlight = false; }
  }
}
WorkSurface.define("wsp-surface");
