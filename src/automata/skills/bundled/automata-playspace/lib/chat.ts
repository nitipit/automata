// @ts-types="./adaptive-ui.d.ts"
import { Base } from "./adaptive-ui.js";
import type { ChatData, ChatSnapshot, Registry, Message, ComponentPayload, EventPayload, ComponentHandle } from "./types.js";
import { chatCSS } from "./chat.css.js";
import { validateChatData, chatDefinition } from "./chat.schema.js";
import { ContractError, component, event, emit, selector, parseTarget, safeId, newId, isRecord, validateComponent, validateEvent } from "./contracts.js";
import { chatInstances, validateChatSnapshot } from "./chat-state.js";
import { renderMessage } from "./render.js";
import { createChatView, updateChatView, disableChatView, type ChatView } from "./chat-view.js";
import { builtins } from "./registry.js";

const attributes = { title: "title", agentLabel: "agent-label", userLabel: "user-label",
  inputLabel: "input-label", sendLabel: "send-label", placeholder: "placeholder", emptyMessage: "empty-message" };

/** Playspace history/composer/admission owner; transport stays in page composition. */
export class Chat extends Base<ChatData> {
  #view: ChatView;
  #bound = false;
  #applying = false;
  #connected = false;
  #pending = false;
  #agentBusy = true;
  #disposed = false;
  #outgoing: ComponentPayload | undefined;
  #markedSent = false;
  #feedbackPayload: EventPayload | undefined;
  #data = validateChatData({});
  #registry: Registry = builtins;
  #messages: Message[] = [];
  #events: EventPayload[] = [];
  #handles = new Map<string, ComponentHandle>();
  static { this.css = chatCSS; }
  static get observedAttributes() { return Object.values(attributes); }
  static validateData(data) { return validateChatData(data); }
  connectedCallback() {
    super.connectedCallback();
    this.#ensureView();
    this.applyData(validateChatData(Object.fromEntries(Object.entries(attributes).map(([key, attr]) => [key, this.getAttribute(attr) ?? undefined]))));
    if (!this.#bound && !this.#disposed) {
      this.#bound = true;
      this.#view.textarea.addEventListener("input", this.#onInput);
      this.#view.form.addEventListener("submit", this.#onSubmit);
      this.#view.feedbackButton.addEventListener("click", this.#onFeedback);
      this.addEventListener("playspace-event", this.#onEvent);
    }
    this.#updateButton();
  }
  attributeChangedCallback(_name, oldValue, newValue) {
    if (oldValue !== newValue && this.isConnected && this.#view && !this.#applying) {
      this.applyData(validateChatData(Object.fromEntries(Object.entries(attributes).map(([key, attr]) => [key, this.getAttribute(attr) ?? undefined]))));
    }
  }
  applyData(data: ChatData): void {
    this.#data = data;
    this.#ensureView();
    this.#applying = true;
    try {
      for (const [key, attr] of Object.entries(attributes)) {
        if (this.getAttribute(attr) !== data[key]) this.setAttribute(attr, data[key]);
      }
    } finally { this.#applying = false; }
    updateChatView(this.#view, data, this);
    this.#updateButton();
  }
  #ensureView() { this.#view ??= createChatView(this); }
  #identity() {
    if (!this.id) this.id = newId("chat");
    if (!safeId(this.id)) throw new ContractError(chatDefinition.contract, { id: "Safe stable ps-chat ID required" });
    return this.id;
  }
  setRegistry(registry: Registry): void {
    if (this.#messages.length || this.#events.length) throw new Error("Configure trusted registry before history");
    this.#registry = Object.freeze({ ...registry });
  }
  setConnection(connected: boolean, pending = false): void {
    this.#connected = connected;
    if (pending) this.#pending = true;
    this.setStatus(connected ? this.#pending ? "Waiting for the outstanding reply…" : "Connected · replies arrive here" : "Disconnected · no automatic resend");
  }
  setAgentBusy(busy: boolean): void {
    this.#agentBusy = busy;
    if (this.#connected) this.setStatus(this.#pending ? "Waiting for the outstanding reply…" : busy ? "Agent busy · Send enables when ready" : "Connected · replies arrive here");
    else this.#updateButton();
  }
  setStatus(text: string): void {
    this.#ensureView();
    this.#view.status.textContent = text;
    this.#updateButton();
  }
  canSend() { return !this.#disposed && this.#connected && !this.#pending && !this.#agentBusy; }
  #updateButton() { if (this.#view) disableChatView(this.#view, !this.canSend()); }

  /** Local log only, not proof of receipt/admission. Same stable composer component. */
  markSent() {
    if (!this.#outgoing || this.#markedSent) return;
    this.#markedSent = true;
    this.addMessage("user", this.#outgoing);
    if (this.#view.textarea.value.trim() === (this.#outgoing.data.props as { text: string }).text) this.#view.textarea.value = "";
    this.#changed();
    this.setStatus("Sent · awaiting reply…");
  }
  reject(text: string): void {
    this.#pending = false;
    if (this.#outgoing && !this.#view.textarea.value) this.#view.textarea.value = (this.#outgoing.data.props as { text: string }).text;
    this.#outgoing = undefined;
    this.setStatus(text);
    this.#changed();
  }
  interrupt(text: string): void {
    this.#pending = false;
    this.#outgoing = undefined;
    this.#feedback();
    this.setStatus(text);
    this.#changed();
  }
  /** Components render; incoming events are validated/stored inertly, never effects. */
  receiveMessage(payload: unknown): boolean {
    if (this.#disposed) return false;
    try {
      if (isRecord(payload) && payload.type === "event") this.#events.push(this.#validateEvent(payload));
      else this.addMessage("agent", payload);
    } catch (error) {
      this.#pending = false;
      this.#outgoing = undefined;
      this.setStatus("Reply payload invalid · last-good history retained · no automatic resend");
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
  addMessage(role: Message["role"], value: unknown): string {
    if (this.#disposed) throw new Error("Chat is disposed");
    if (!["user", "agent"].includes(role)) throw new Error("Invalid history role");
    const content = validateComponent(value, this.#registry);
    const item = { id: crypto.randomUUID(), role, content };
    const candidate = this.snapshot();
    candidate.messages.push(item);
    // Unique IDs + linked contracts checked before constructing ANY new component.
    const history = validateChatSnapshot(candidate, this.#registry);
    const rendered = this.#render(item, undefined, history);
    this.#view.area.querySelector(".empty")?.remove();
    this.#view.area.append(rendered.element);
    this.#handles.set(content.data.id, rendered.handle);
    this.#messages.push(item);
    this.#view.area.scrollTop = this.#view.area.scrollHeight;
    this.#feedback();
    this.#changed();
    return item.id;
  }
  #captureStates() {
    const states = Object.create(null);
    for (const [id, handle] of this.#handles) if (handle.snapshot) states[id] = handle.snapshot();
    return states;
  }
  #validateEvent(payload: unknown): EventPayload {
    return validateEvent(payload, { ...this.#registry, "ps-chat": chatDefinition },
      chatInstances(this.#identity(), this.#messages, this.#captureStates(), this.#registry));
  }
  snapshot(): ChatSnapshot {
    this.#ensureView();
    return validateChatSnapshot({ version: 2, id: this.#identity(), settings: this.#data,
      messages: this.#messages, events: this.#events, composer: this.#view.textarea.value,
      pending: this.#pending, componentStates: this.#captureStates() }, this.#registry);
  }
  /** Atomic validation/construction; disconnected restoration and no event/send replay. */
  restore(value: unknown): boolean {
    if (this.#disposed) return false;
    const candidates = [];
    try {
      const snapshot = validateChatSnapshot(value, this.#registry);
      for (const item of snapshot.messages) candidates.push(this.#render(item, snapshot.componentStates[item.content.data.id], snapshot));
      this.#ensureView();
      this.#releaseHandles();
      this.#view.area.replaceChildren(...candidates.map(item => item.element));
      this.id = snapshot.id;
      this.#messages = snapshot.messages;
      this.#events = snapshot.events;
      snapshot.messages.forEach((item, index) => this.#handles.set(item.content.data.id, candidates[index].handle));
      this.applyData(snapshot.settings);
      this.#view.textarea.value = snapshot.composer;
      this.#connected = false;
      this.#agentBusy = true;
      this.#pending = false;
      this.#outgoing = undefined;
      this.setStatus(snapshot.pending ? "Restored · outstanding request interrupted/uncertain · no replay" : "Restored display history · disconnected · no replay");
      this.#feedback();
      return true;
    } catch (error) {
      for (const candidate of candidates) candidate.handle.dispose?.();
      this.#feedback(error);
      return false;
    }
  }
  #render(item: Message, state: any, history: ChatSnapshot) {
    return renderMessage(item, this.#registry[item.content.data.name], { state, history,
      changed: () => this.#changed(), canSend: () => this.canSend(),
      appendRevision: props => { if (!this.#disposed) this.addMessage("agent", component("ps-form", props)); },
    }, this.#data);
  }
  #releaseHandles() {
    for (const handle of this.#handles.values()) handle.dispose?.();
    this.#handles.clear();
  }
  #feedback(error?: unknown) {
    this.#ensureView();
    this.#view.feedback.textContent = error ? error instanceof ContractError ? error.message : "Component contract failed · last-good state retained; consult canonical definition" : "";
    this.#feedbackPayload = undefined;
    if (error instanceof ContractError) {
      try { this.#feedbackPayload = this.#validateEvent(event("validation-feedback", selector("ps-chat", this.#identity()), { contract: error.contract, fields: error.fields })); }
      catch { /* Unknown/internal contracts never become outbound feedback. */ }
    }
    this.#view.feedbackButton.hidden = !this.#feedbackPayload;
    this.#updateButton();
  }
  #changed() { if (!this.#disposed) this.dispatchEvent(new CustomEvent("chat-change", { bubbles: true, composed: true })); }
  #onInput = () => this.#changed();
  #onSubmit = (nativeEvent: Event) => { nativeEvent.preventDefault(); this.#submit(); };
  #onFeedback = () => {
    if (!this.#feedbackPayload || !this.canSend()) return;
    const payload = this.#feedbackPayload;
    this.#feedback(); // once per failure; never automatic repair/retry
    emit(this, payload);
  };
  #onEvent = (nativeEvent: CustomEvent<unknown>) => {
    if (!this.canSend()) return;
    try {
      const payload = this.#validateEvent(nativeEvent.detail);
      const { name, id } = parseTarget(payload.data.target);
      const emitter = name === "ps-chat" ? this : this.#handles.get(id)?.element;
      if (nativeEvent.target !== emitter) throw new ContractError(chatDefinition.contract, { target: "Native emitter must match the registered instance" });
      nativeEvent.stopPropagation();
      this.#events.push(payload);
      this.#pending = true;
      this.#outgoing = undefined;
      this.setStatus("Sending event…");
      this.dispatchEvent(new CustomEvent("agent-message", { bubbles: true, composed: true, detail: payload }));
      this.#changed();
    } catch (error) { this.#feedback(error); }
  };
  sendContent(value: unknown): boolean {
    if (!this.canSend()) return false;
    const content = validateComponent(value, this.#registry);
    this.addMessage("user", content);
    this.#outgoing = undefined;
    this.#pending = true;
    this.setStatus("Sending…");
    this.dispatchEvent(new CustomEvent("agent-message", { bubbles: true, composed: true, detail: content }));
    this.#changed();
    return true;
  }
  #submit() {
    if (!this.canSend()) return;
    const text = this.#view.textarea.value.trim();
    if (!text) return;
    this.#outgoing = component("ps-text", { text });
    this.#markedSent = false;
    this.#pending = true;
    this.setStatus("Sending…");
    this.dispatchEvent(new CustomEvent("agent-message", { bubbles: true, composed: true, detail: this.#outgoing }));
    this.#changed();
  }
  /** Explicit retirement; DOM movement is not retirement. */
  dispose() {
    if (this.#disposed) return;
    this.#disposed = true;
    this.#connected = false;
    this.#pending = false;
    this.#outgoing = undefined;
    this.#releaseHandles();
    this.#view?.textarea.removeEventListener("input", this.#onInput);
    this.#view?.form.removeEventListener("submit", this.#onSubmit);
    this.#view?.feedbackButton.removeEventListener("click", this.#onFeedback);
    this.removeEventListener("playspace-event", this.#onEvent);
    this.#updateButton();
  }
}
