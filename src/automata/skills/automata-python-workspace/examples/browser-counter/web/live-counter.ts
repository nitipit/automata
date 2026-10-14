/// <reference path="./adaptive-ui.d.ts" />
import { Base, Button, Card } from "@adaptive-ui";
Button.define("aui-button");
Card.define("aui-card");

type State = { count: number; object_id: string } | null;
type RuntimeEvent = {
  kind: string; source?: string; runtime_id?: string; generation: number; seq?: number;
  state?: State; busy?: boolean; healthy?: boolean; status?: string;
  error?: string; message?: string; reason?: string; events?: RuntimeEvent[];
};

/** Owns constrained action payloads, websocket projection, and interaction state. */
class LiveCounter extends Base {
  #socket?: WebSocket;
  #timer?: number;
  #connected = false;
  #busy = false;
  #pending = false;
  #healthy = true;
  #state: State = null;
  #generation = 0;
  #runtimeID = "";
  #log: string[] = [];

  static {
    this.css = `
      display: grid; gap: 20px;
      aui-card { display: block; }
      .panel { padding: clamp(20px, 5vw, 36px); }
      .connection { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
      .badge { border-radius: 30px; background: #e8eee9; padding: 4px 12px; font-size: .8rem; }
      output { display: block; font-size: clamp(4rem, 12vw, 6rem); line-height: 1.2; letter-spacing: -.06em; margin: 18px 0; }
      .actions, form { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 18px; }
      label { font-size: .9rem; }
      input { width: 140px; font: inherit; padding: 9px 12px; border: 1px solid #81998c; border-radius: 8px; }
      input:focus-visible { outline: 3px solid #287c69; outline-offset: 3px; }
      .identity { font: .8rem ui-monospace, monospace; overflow-wrap: anywhere; color: #50695f; }
      .notice { min-height: 1.5em; color: #984a21; }
      h2 { font-size: 1rem; margin: 0 0 12px; }
      pre { margin: 0; max-height: 230px; overflow: auto; font: .8rem/1.7 ui-monospace, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
    `;
  }

  override connectedCallback() {
    super.connectedCallback();
    this.innerHTML = `
      <aui-card><section class="panel" aria-label="Live Python counter">
        <div class="connection"><span class="badge" id="connection" role="status">Connecting…</span>
          <span class="badge" id="generation">Generation —</span></div>
        <output aria-label="Counter value" aria-live="polite">—</output>
        <div class="identity">counter · Python object id <span id="identity">—</span></div>
        <div class="actions">
          <aui-button label="Subtract one" data-action="decrement"></aui-button>
          <aui-button label="Add one" data-action="increment" tone="primary"></aui-button>
        </div>
        <form><label for="value">Set value</label>
          <input id="value" name="value" type="number" step="1" min="-1000000000000" max="1000000000000" value="0" required>
          <aui-button label="Apply value" type="submit"></aui-button>
        </form>
        <p class="notice" id="notice" role="status"></p>
      </section></aui-card>
      <aui-card><section class="panel"><h2>Event bridge</h2><pre id="log" aria-label="Runtime event log"></pre></section></aui-card>`;
    this.addEventListener("click", this.#click);
    this.querySelector("form")!.addEventListener("submit", this.#submit);
    this.#connect();
  }

  #click = (event: Event) => {
    const button = (event.target as Element).closest("aui-button[data-action]");
    if (button) this.#action(button.getAttribute("data-action")!);
  };
  #submit = (event: Event) => {
    event.preventDefault();
    const input = this.querySelector("input")!;
    if (input.reportValidity()) this.#action("set", Number(input.value));
  };

  async #action(action: string, value = 0) {
    if (!this.#connected || this.#busy || this.#pending || !this.#healthy) return;
    this.#pending = true;
    this.#render();
    try {
      const response = await fetch("/action", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, value }),
      });
      const reply = await response.json();
      if (!response.ok || reply.status !== "ok") {
        this.querySelector("#notice")!.textContent = reply.error || reply.detail || "Action failed";
      }
    } catch {
      this.querySelector("#notice")!.textContent = "Connection lost; action outcome unknown. Not replayed.";
    } finally {
      this.#pending = false;
      this.#render();
    }
  }

  #connect() {
    const socket = new WebSocket(`ws://${location.host}/events`);
    this.#socket = socket;
    socket.onopen = () => { this.#connected = true; this.#render(); };
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as RuntimeEvent;
      if (event.runtime_id && this.#runtimeID && event.runtime_id !== this.#runtimeID) {
        this.querySelector("#notice")!.textContent = "Runtime replaced; previous live state lost. No command replay.";
      }
      this.#runtimeID = event.runtime_id || this.#runtimeID;
      if (event.kind === "snapshot") {
        this.#state = event.state ?? null;
        this.#busy = event.busy ?? false;
        this.#healthy = event.healthy ?? false;
        this.#log = [];
        for (const previous of event.events ?? []) this.#record(previous);
      } else {
        if (event.kind === "state") this.#state = event.state ?? null;
        if (event.kind === "busy") this.#busy = true;
        if (event.kind === "idle") { this.#busy = false; this.#healthy = event.healthy ?? true; }
        if (event.kind === "ready") { this.#healthy = true; this.#busy = false; }
        if (["state_lost", "projection_error", "state_unknown"].includes(event.kind)) this.#state = null;
        this.#record(event);
      }
      if (["state_lost", "projection_error", "state_unknown"].includes(event.kind)) {
        this.querySelector("#notice")!.textContent = event.reason || event.message || "State lost";
      }
      this.#generation = event.generation;
      this.#render();
    };
    socket.onclose = () => {
      this.#connected = false;
      this.#render();
      // Reconnect transport only; never replay an action or Python code.
      if (this.isConnected) this.#timer = setTimeout(() => this.#connect(), 1000);
    };
  }

  #record(event: RuntimeEvent) {
    const count = event.state ? ` → ${event.state.count}` : "";
    this.#log.unshift(`#${event.seq} ${event.source || "runtime"} · ${event.kind}${count}${event.error ? ` · ${event.error}` : ""}`);
    this.#log = this.#log.slice(0, 60);
  }

  #render() {
    this.querySelector("#connection")!.textContent = !this.#connected ? "Disconnected" :
      !this.#healthy ? "Restart required" : this.#busy ? "Python busy" : "Connected · idle";
    this.querySelector("#generation")!.textContent = `Generation ${this.#generation || "—"} · ${this.#runtimeID.slice(0, 8)}`;
    this.querySelector("#generation")!.setAttribute("title", `Runtime ${this.#runtimeID}`);
    this.querySelector("output")!.textContent = this.#state ? String(this.#state.count) : "—";
    this.querySelector("#identity")!.textContent = this.#state?.object_id || "unavailable";
    this.querySelector("#log")!.textContent = this.#log.join("\n");
    for (const button of this.querySelectorAll("aui-button")) {
      button.toggleAttribute("disabled", !this.#connected || this.#busy || this.#pending || !this.#healthy);
    }
  }

  override disconnectedCallback() {
    clearTimeout(this.#timer);
    this.#socket?.close();
    this.removeEventListener("click", this.#click);
    this.querySelector("form")?.removeEventListener("submit", this.#submit);
    super.disconnectedCallback?.();
  }
}
LiveCounter.define("live-counter");
