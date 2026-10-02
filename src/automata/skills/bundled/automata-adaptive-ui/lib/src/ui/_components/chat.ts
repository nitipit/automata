import { Base } from "./base.js";
import { tokens } from "../tokens.js";
import {
  type ChatData,
  validateChatData,
} from "./chat.schema.js";

import {
  ChatContractError, type ChatComponentHandle, type ChatContent,
  type ChatMessage, type ChatMessageRole, type ChatRegistry, validateChatContent,
} from "./chat-content.js";
import { type ChatSnapshot, validateChatSnapshot } from "./chat-state.js";
export type { ChatMessageRole } from "./chat-content.js";
export type ChatPayload = { text: string; content: ChatContent; context: Record<string, unknown> };

let nextChatInputId = 0;

/**
 * A literal/structured chat presentation with bridge-neutral events and explicit snapshots.
 * Register `Button` as `aui-button` before registering `Chat`; the catalog
 * example demonstrates that required composition wiring.
 */
export class Chat extends Base<ChatData> {
  #mounted = false;
  #bound = false;
  #applyingData = false;
  #connected = false;
  #pending = false;
  #agentBusy = true;
  #outgoing: string | undefined;
  #markedSent = false;
  #inputId = `chat-input-${++nextChatInputId}`;
  #data: ChatData = validateChatData({});
  #registry: ChatRegistry = {};
  #messages: ChatMessage[] = [];
  #handles = new Map<string, ChatComponentHandle>();
  #textarea: HTMLTextAreaElement | null = null;
  #form: HTMLFormElement | null = null;
  #disposed = false;

  static get observedAttributes(): string[] {
    return [
      "title",
      "agent-label",
      "user-label",
      "input-label",
      "send-label",
      "placeholder",
      "empty-message",
    ];
  }

  static {
    this.css = `
      display: flex;
      flex-direction: column;
      width: min(48rem, 100%);
      height: min(48rem, 90dvh);
      min-height: 30rem;
      box-sizing: border-box;
      overflow: hidden;
      border: 1px solid ${tokens.border};
      border-radius: 1.25rem;
      background: ${tokens.surface};
      box-shadow: 0 18px 65px #14283e12;
      font-size: 1.2rem;

      header {
        padding: 1.4rem 1.6rem;
        border-bottom: 1px solid ${tokens.border};
      }

      h1 {
        margin: 0;
        font-size: 1.65rem;
      }

      .messages {
        display: flex;
        flex: 1;
        flex-direction: column;
        gap: 1rem;
        overflow-y: auto;
        padding: 1.5rem;
      }

      .empty {
        max-width: 28rem;
        margin: auto;
        color: ${tokens.status};
        text-align: center;
      }

      .message {
        max-width: 85%;
        padding: .8rem 1rem;
        border-radius: 1rem;
        background: #f1f5f9;
      }

      .message[data-role="user"] {
        align-self: flex-end;
        background: #e9f0ff;
      }

      .message strong {
        display: block;
        margin-bottom: .3rem;
        color: ${tokens.mutedText};
        font-size: .95rem;
      }

      .message p {
        margin: 0;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }

      form {
        padding: 1rem 1.5rem 1.4rem;
        border-top: 1px solid ${tokens.border};
      }

      label {
        display: block;
        margin-bottom: .4rem;
        color: ${tokens.mutedText};
        font-size: 1rem;
      }

      textarea {
        width: 100%;
        min-height: 5rem;
        box-sizing: border-box;
        resize: vertical;
        padding: .7rem;
        border: 1px solid ${tokens.border};
        border-radius: .65rem;
        font: inherit;
      }

      textarea:focus-visible {
        outline: 2px solid ${tokens.focus};
        outline-offset: 2px;
      }

      .footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        margin-top: .6rem;
      }

      .status {
        color: ${tokens.status};
        font-size: 1rem;
      }

      aui-button {
        font-size: inherit;
      }

      button:disabled {
        opacity: .45;
        cursor: not-allowed;
      }
    `;
  }

  static override validateData(data: unknown): ChatData {
    return validateChatData(data);
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (!this.#mounted) {
      this.#mount();
      this.applyData(this.dataFromAttributes());
    }
  }

  attributeChangedCallback(
    _name: string,
    oldValue: string | null,
    newValue: string | null,
  ): void {
    if (
      oldValue !== newValue && this.isConnected && this.#mounted &&
      !this.#applyingData
    ) {
      this.applyData(this.dataFromAttributes());
    }
  }

  override applyData(data: ChatData): void {
    this.#data = data;
    this.#ensureMarkup();
    this.#applyingAttributes(() => {
      this.setAttributeIfChanged("title", data.title);
      this.setAttributeIfChanged("agent-label", data.agentLabel);
      this.setAttributeIfChanged("user-label", data.userLabel);
      this.setAttributeIfChanged("input-label", data.inputLabel);
      this.setAttributeIfChanged("send-label", data.sendLabel);
      this.setAttributeIfChanged("placeholder", data.placeholder);
      this.setAttributeIfChanged("empty-message", data.emptyMessage);
    });

    const heading = this.querySelector("h1");
    if (heading) heading.textContent = data.title;
    const label = this.#form?.querySelector("label");
    if (label) label.textContent = data.inputLabel;
    const textarea = this.#textarea;
    if (textarea) {
      textarea.placeholder = data.placeholder;
      textarea.maxLength = 6000;
    }
    const button = this.#form?.querySelector("aui-button");
    if (button) {
      button.setAttribute("label", data.sendLabel);
      button.setAttribute("type", "submit");
    }
    const empty = this.querySelector(".empty");
    if (empty) empty.textContent = data.emptyMessage;
    this.#updateButton();
  }

  /**
   * Reflect transport state without sending or retrying. A true pending flag
   * latches the outstanding request; false does not clear it on reconnection.
   * receiveMessage() or reject() clears the component's pending state.
   */
  setConnection(connected: boolean, pending = false): void {
    this.#connected = connected;
    if (pending) this.#pending = true;
    this.setStatus(
      connected
        ? this.#pending
          ? "Waiting for the outstanding reply…"
          : "Connected · replies arrive here"
        : "Disconnected · no automatic resend",
    );
  }

  /** Disables explicit Send while the existing Pi session is busy. */
  setAgentBusy(busy: boolean): void {
    this.#agentBusy = busy;
    if (this.#connected) {
      this.setStatus(
        this.#pending
          ? "Waiting for the outstanding reply…"
          : busy
          ? "Agent is busy in the existing session · Send will enable when ready"
          : "Connected · replies arrive here",
      );
    } else {
      this.#updateButton();
    }
  }

  setStatus(text: string): void {
    this.#ensureMarkup();
    const status = this.querySelector(".status");
    if (status) status.textContent = text;
    this.#updateButton();
  }

  /**
   * Add the outgoing text to the local log and clear the composer after dispatch.
   * This is not proof of remote receipt or admission. Repeated calls for one
   * dispatch are ignored.
   */
  markSent(): void {
    if (this.#outgoing === undefined || this.#markedSent) return;
    this.#markedSent = true;
    this.addMessage("user", this.#outgoing);
    const textarea = this.#textarea;
    // Preserve text typed while dispatch was in progress.
    if (textarea?.value.trim() === this.#outgoing) textarea.value = "";
    this.#changed();
    this.setStatus("Sent · awaiting reply…");
  }

  /**
   * Clear pending state and restore outgoing text only if the composer is empty.
   * Existing log entries remain; this neither retracts nor retries a remote send.
   */
  reject(text: string): void {
    this.#pending = false;
    const textarea = this.#textarea;
    if (textarea && !textarea.value && this.#outgoing !== undefined) {
      textarea.value = this.#outgoing;
    }
    this.#outgoing = undefined;
    this.setStatus(text);
    this.#changed();
  }

  /** Interrupt presentation only; never retracts remote effects or restores/replays a send. */
  interrupt(text: string): void {
    this.#pending = false;
    this.#outgoing = undefined;
    this.setStatus(text);
    this.#changed();
  }

  /**
   * Accept a component payload, not a bridge envelope. The caller owns routing and
   * correlation. Valid and invalid payloads both end the local pending request;
   * invalid payloads display an error without retrying or adding a message.
   */
  receiveMessage(payload: unknown): boolean {
    if (this.#disposed) return false;
    try {
      this.addMessage("agent", validateChatContent(payload, this.#registry));
    } catch (error) {
      this.#pending = false;
      this.#outgoing = undefined;
      this.setStatus("Reply payload is invalid for Chat · no automatic resend");
      this.#feedback(error);
      this.#changed();
      return false;
    }
    this.#pending = false;
    this.#outgoing = undefined;
    this.setStatus("Reply received · ready for your next message");
    this.#changed();
    return true;
  }

  /** Literal strings retain the basic Chat API; structured objects are validated. */
  addMessage(role: ChatMessageRole, value: unknown): string {
    if (this.#disposed) throw new Error("Chat is disposed");
    if (role !== "user" && role !== "agent") throw new Error("Invalid Chat role");
    const content = validateChatContent(typeof value === "string" ? { type: "text", data: value } : value, this.#registry);
    const item: ChatMessage = { id: crypto.randomUUID(), role, content };
    const rendered = this.#render(item);
    this.#ensureMarkup();
    const area = this.querySelector(".messages")!;
    area.querySelector(".empty")?.remove();
    area.append(rendered.element);
    if (rendered.handle) this.#handles.set(item.id, rendered.handle);
    this.#messages.push(item);
    area.scrollTop = area.scrollHeight;
    this.#feedback();
    this.#changed();
    return item.id;
  }

  /** Configure trusted definitions before adding/restoring messages. */
  setRegistry(registry: ChatRegistry): void {
    if (this.#messages.length) throw new Error("Configure registry before history");
    this.#registry = Object.freeze({ ...registry });
  }

  snapshot(): ChatSnapshot {
    const componentStates: Record<string, unknown> = {};
    for (const [id, handle] of this.#handles) {
      if (handle.snapshot) componentStates[id] = handle.snapshot();
    }
    return validateChatSnapshot({ version: 1, settings: this.#data, messages: this.#messages,
      composer: this.#textarea?.value ?? "", pending: this.#pending, componentStates }, this.#registry);
  }

  /** Atomic candidate validation/construction. Pending becomes uncertain; never replayed. */
  restore(value: unknown): boolean {
    if (this.#disposed) return false;
    const candidates: { element: HTMLElement; handle?: ChatComponentHandle }[] = [];
    try {
      const snapshot = validateChatSnapshot(value, this.#registry);
      for (const item of snapshot.messages) candidates.push(this.#render(item, snapshot.componentStates[item.id]));
      this.#ensureMarkup();
      this.#releaseHandles();
      const area = this.querySelector(".messages")!;
      area.replaceChildren(...candidates.map((item) => item.element));
      this.#messages = snapshot.messages;
      snapshot.messages.forEach((item, index) => {
        const handle = candidates[index].handle;
        if (handle) this.#handles.set(item.id, handle);
      });
      this.applyData(snapshot.settings);
      this.#textarea!.value = snapshot.composer;
      this.#pending = false;
      this.#outgoing = undefined;
      this.setStatus(snapshot.pending ? "Restored · outstanding request interrupted/uncertain · no replay" : "Restored display history · no requests replayed");
      this.#feedback();
      return true;
    } catch (error) {
      for (const item of candidates) item.handle?.dispose?.();
      this.#feedback(error);
      return false;
    }
  }

  /** Caller disposes a replaced/retired instance; DOM movement is not retirement. */
  dispose(): void {
    this.#disposed = true;
    this.#connected = false;
    this.#pending = false;
    this.#outgoing = undefined;
    this.#releaseHandles();
    this.#updateButton();
  }

  #render(item: ChatMessage, state?: unknown): { element: HTMLElement; handle?: ChatComponentHandle } {
    const element = document.createElement("article");
    element.className = "message";
    element.setAttribute("data-role", item.role);
    element.setAttribute("data-message-id", item.id);
    const label = document.createElement("strong");
    label.textContent = item.role === "user" ? this.#data.userLabel : this.#data.agentLabel;
    let body: HTMLElement;
    let handle: ChatComponentHandle | undefined;
    if (item.content.type === "component") {
      const { name, props } = item.content.data;
      let live = true;
      const created = this.#registry[name].create(props, { messageId: item.id, state, changed: () => { if (live && !this.#disposed) this.#changed(); } });
      handle = { ...created, dispose: () => { live = false; created.dispose?.(); } };
      body = handle.element;
    } else {
      body = document.createElement(item.content.type === "text" ? "p" : "pre");
      body.textContent = item.content.type === "text" ? item.content.data : JSON.stringify(item.content.data, null, 2);
    }
    element.append(label, body);
    return { element, handle };
  }

  #releaseHandles(): void {
    for (const handle of this.#handles.values()) handle.dispose?.();
    this.#handles.clear();
  }

  #feedback(error?: unknown): void {
    this.#ensureMarkup();
    const feedback = this.querySelector(".feedback");
    if (feedback) feedback.textContent = error ? error instanceof ChatContractError ? error.message : "Component contract failed · last-good state preserved; consult its canonical definition" : "";
  }

  #changed(): void {
    if (!this.#disposed) this.dispatchEvent(new CustomEvent("chat-change", { bubbles: true, composed: true }));
  }

  #mount(): void {
    this.#mounted = true;
    this.#ensureMarkup();
    if (this.#bound) return;
    this.#bound = true;
    const form = this.#form;
    this.#textarea?.addEventListener("input", () => this.#changed());
    form?.addEventListener("submit", (event) => {
      event.preventDefault();
      this.#submit();
    });
  }

  /** Shared admission gate for composer and explicitly submitted components. */
  canSend(): boolean {
    return !this.#disposed && this.#connected && !this.#pending && !this.#agentBusy;
  }

  /** Sends complete validated content only on an explicit component action. */
  sendContent(value: unknown): boolean {
    if (!this.canSend()) return false;
    const content = validateChatContent(value, this.#registry);
    this.#pending = true;
    this.#outgoing = undefined;
    this.addMessage("user", content);
    this.setStatus("Sending…");
    this.dispatchEvent(new CustomEvent("agent-message", {
      bubbles: true, composed: true,
      detail: { content, context: { componentId: this.id || "chat" } },
    }));
    this.#changed();
    return true;
  }

  #submit(): void {
    if (!this.canSend()) return;
    const textarea = this.#textarea;
    const text = textarea?.value.trim() ?? "";
    if (!text) return;
    this.#pending = true;
    this.#outgoing = text;
    this.#markedSent = false;
    this.setStatus("Sending…");
    this.dispatchEvent(new CustomEvent("agent-message", {
      bubbles: true,
      composed: true,
      detail: {
        text,
        content: { type: "text", data: text },
        context: { componentId: this.id || "chat" },
      } satisfies ChatPayload,
    }));
    this.#changed();
  }

  #ensureMarkup(): void {
    if (this.querySelector(".messages") && this.querySelector("form")) return;

    const header = document.createElement("header");
    const heading = document.createElement("h1");
    header.append(heading);

    const area = document.createElement("section");
    area.className = "messages";
    area.setAttribute("role", "log");
    area.setAttribute("aria-label", "Conversation");
    area.setAttribute("aria-live", "polite");
    const empty = document.createElement("p");
    empty.className = "empty";
    area.append(empty);

    const form = document.createElement("form");
    this.#form = form;
    const label = document.createElement("label");
    label.htmlFor = this.#inputId;
    label.setAttribute("for", this.#inputId);
    const textarea = document.createElement("textarea");
    this.#textarea = textarea;
    textarea.id = this.#inputId;
    textarea.name = "message";
    textarea.required = true;
    textarea.maxLength = 6000;
    const footer = document.createElement("div");
    footer.className = "footer";
    const status = document.createElement("span");
    status.className = "status";
    status.setAttribute("role", "status");
    const button = document.createElement("aui-button");
    // Button validates its required label when it is connected, so initialize
    // it before appending the custom element to the footer.
    button.setAttribute("label", this.#data.sendLabel);
    button.setAttribute("type", "submit");
    const feedback = document.createElement("pre");
    feedback.className = "feedback";
    feedback.setAttribute("role", "alert");
    footer.append(status, button);
    form.append(label, textarea, footer, feedback);
    this.append(header, area, form);
  }

  #updateButton(): void {
    const disabled = this.#disposed || !this.#connected || this.#pending || this.#agentBusy;
    const nativeButton = this.#form?.querySelector("aui-button button") as HTMLButtonElement | null;
    if (nativeButton) nativeButton.disabled = disabled;
    const button = this.#form?.querySelector("aui-button");
    if (button) button.setAttribute("aria-disabled", String(disabled));
  }

  #applyingAttributes(callback: () => void): void {
    this.#applyingData = true;
    try {
      callback();
    } finally {
      this.#applyingData = false;
    }
  }

  private dataFromAttributes(): ChatData {
    return validateChatData({
      title: this.getAttribute("title") ?? undefined,
      agentLabel: this.getAttribute("agent-label") ?? undefined,
      userLabel: this.getAttribute("user-label") ?? undefined,
      inputLabel: this.getAttribute("input-label") ?? undefined,
      sendLabel: this.getAttribute("send-label") ?? undefined,
      placeholder: this.getAttribute("placeholder") ?? undefined,
      emptyMessage: this.getAttribute("empty-message") ?? undefined,
    });
  }

  private setAttributeIfChanged(name: string, value: string): void {
    if (this.getAttribute(name) !== value) this.setAttribute(name, value);
  }
}

