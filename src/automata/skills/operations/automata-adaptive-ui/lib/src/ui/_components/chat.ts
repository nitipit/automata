import { Base } from "./base.js";
import {
  type ChatData,
  validateChatData,
} from "./chat.schema.js";

export type ChatMessageRole = "user" | "agent";
export type ChatPayload = { text: string; context: Record<string, unknown> };
export type ChatReplyPayload = { text: string; [key: string]: unknown };

let nextChatInputId = 0;

/**
 * A text chat presentation component with semantic, bridge-neutral events.
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
  #inputId = `chat-input-${++nextChatInputId}`;
  #data: ChatData = validateChatData({});

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
      border: 1px solid #dce3eb;
      border-radius: 1.25rem;
      background: #fff;
      box-shadow: 0 18px 65px #14283e12;
      font-size: 1.2rem;

      header {
        padding: 1.4rem 1.6rem;
        border-bottom: 1px solid #e7ecf1;
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
        color: #64748b;
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
        color: #475569;
        font-size: .95rem;
      }

      .message p {
        margin: 0;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }

      form {
        padding: 1rem 1.5rem 1.4rem;
        border-top: 1px solid #e7ecf1;
      }

      label {
        display: block;
        margin-bottom: .4rem;
        color: #475569;
        font-size: 1rem;
      }

      textarea {
        width: 100%;
        min-height: 5rem;
        box-sizing: border-box;
        resize: vertical;
        padding: .7rem;
        border: 1px solid #cbd5e1;
        border-radius: .65rem;
        font: inherit;
      }

      .footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        margin-top: .6rem;
      }

      .status {
        color: #64748b;
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
    const label = this.querySelector("label");
    if (label) label.textContent = data.inputLabel;
    const textarea = this.querySelector("textarea") as HTMLTextAreaElement | null;
    if (textarea) {
      textarea.placeholder = data.placeholder;
      textarea.maxLength = 6000;
    }
    const button = this.querySelector("aui-button");
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
   * This is not proof of remote receipt or admission. Call once per dispatch;
   * repeated calls append duplicate log entries.
   */
  markSent(): void {
    if (this.#outgoing === undefined) return;
    this.addMessage("user", this.#outgoing);
    const textarea = this.querySelector("textarea") as HTMLTextAreaElement | null;
    if (textarea) textarea.value = "";
    this.setStatus("Sent · awaiting reply…");
  }

  /**
   * Clear pending state and restore outgoing text only if the composer is empty.
   * Existing log entries remain; this neither retracts nor retries a remote send.
   */
  reject(text: string): void {
    this.#pending = false;
    const textarea = this.querySelector("textarea") as HTMLTextAreaElement | null;
    if (textarea && !textarea.value && this.#outgoing !== undefined) {
      textarea.value = this.#outgoing;
    }
    this.setStatus(text);
  }

  /**
   * Accept a component payload, not a bridge envelope. The caller owns routing and
   * correlation. Valid and invalid payloads both end the local pending request;
   * invalid payloads display an error without retrying or adding a message.
   */
  receiveMessage(payload: unknown): void {
    if (!isChatReplyPayload(payload)) {
      this.#pending = false;
      this.#outgoing = undefined;
      this.setStatus("Reply payload is invalid for Chat · no automatic resend");
      return;
    }
    this.addMessage("agent", payload.text);
    this.#pending = false;
    this.#outgoing = undefined;
    this.setStatus("Reply received · ready for your next message");
  }

  /** Adds a literal text message to the conversation log. */
  addMessage(role: ChatMessageRole, text: string): void {
    this.#ensureMarkup();
    const area = this.querySelector(".messages");
    if (!area) return;
    area.querySelector(".empty")?.remove();
    const message = document.createElement("article");
    message.className = "message";
    message.setAttribute("data-role", role);
    const label = document.createElement("strong");
    label.textContent = role === "user" ? this.#data.userLabel : this.#data.agentLabel;
    const content = document.createElement("p");
    content.textContent = text;
    message.append(label, content);
    area.append(message);
    area.scrollTop = area.scrollHeight;
  }

  #mount(): void {
    this.#mounted = true;
    this.#ensureMarkup();
    if (this.#bound) return;
    this.#bound = true;
    const form = this.querySelector("form");
    form?.addEventListener("submit", (event) => {
      event.preventDefault();
      this.#submit();
    });
  }

  #submit(): void {
    if (!this.#connected || this.#pending || this.#agentBusy) return;
    const textarea = this.querySelector("textarea") as HTMLTextAreaElement | null;
    const text = textarea?.value.trim() ?? "";
    if (!text) return;
    this.#pending = true;
    this.#outgoing = text;
    this.setStatus("Sending…");
    this.dispatchEvent(new CustomEvent("agent-message", {
      bubbles: true,
      composed: true,
      detail: {
        text,
        context: { componentId: this.id || "chat" },
      } satisfies ChatPayload,
    }));
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
    const label = document.createElement("label");
    label.htmlFor = this.#inputId;
    label.setAttribute("for", this.#inputId);
    const textarea = document.createElement("textarea");
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
    footer.append(status, button);
    form.append(label, textarea, footer);
    this.append(header, area, form);
  }

  #updateButton(): void {
    const disabled = !this.#connected || this.#pending || this.#agentBusy;
    const nativeButton = this.querySelector("aui-button button") as HTMLButtonElement | null;
    if (nativeButton) nativeButton.disabled = disabled;
    const button = this.querySelector("aui-button");
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

function isChatReplyPayload(value: unknown): value is ChatReplyPayload {
  return value !== null && typeof value === "object" && !Array.isArray(value) &&
    typeof (value as { text?: unknown }).text === "string";
}
