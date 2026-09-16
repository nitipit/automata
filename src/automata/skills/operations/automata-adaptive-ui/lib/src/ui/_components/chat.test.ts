const globals = globalThis as unknown as Record<string, unknown>;
const originals = new Map<string, unknown>();
for (const name of [
  "HTMLElement",
  "CSSStyleSheet",
  "MutationObserver",
  "CustomEvent",
  "document",
]) {
  originals.set(name, globals[name]);
}

class FakeNode {
  children: FakeNode[] = [];
  parentNode: FakeNode | null = null;
  listeners = new Map<string, (event: FakeEvent) => void>();
  attributes = new Map<string, string>();
  className = "";
  id = "";
  htmlFor = "";
  name = "";
  value = "";
  placeholder = "";
  maxLength = 0;
  required = false;
  textContent = "";
  scrollTop = 0;
  scrollHeight = 0;
  isConnected = true;
  adoptedStyleSheets: FakeStyleSheet[] = [];
  onConnect: (() => void) | undefined;
  tagName: string;

  constructor(tagName = "div") {
    this.tagName = tagName;
  }

  append(...nodes: FakeNode[]): void {
    for (const node of nodes) {
      node.parentNode = this;
      this.children.push(node);
      node.onConnect?.();
    }
  }

  remove(): void {
    this.parentNode?.children.splice(this.parentNode.children.indexOf(this), 1);
  }

  setAttribute(name: string, value: string): void {
    this.attributes.set(name, value);
  }

  getAttribute(name: string): string | null {
    return this.attributes.get(name) ?? null;
  }

  addEventListener(name: string, listener: (event: FakeEvent) => void): void {
    this.listeners.set(name, listener);
  }

  dispatchEvent(event: FakeEvent): boolean {
    this.listeners.get(event.type)?.(event);
    return true;
  }

  querySelector(selector: string): FakeNode | null {
    return this.find((node) => matches(node, selector));
  }

  getRootNode(): FakeNode {
    return this;
  }

  emit(type: string): void {
    this.listeners.get(type)?.(new FakeEvent(type));
  }

  private find(predicate: (node: FakeNode) => boolean): FakeNode | null {
    for (const child of this.children) {
      if (predicate(child)) return child;
      const nested = child.find(predicate);
      if (nested) return nested;
    }
    return null;
  }
}

class FakeEvent {
  constructor(public type: string) {}
  preventDefault(): void {}
}

class FakeCustomEvent extends FakeEvent {
  constructor(
    type: string,
    public init: { detail?: unknown; bubbles?: boolean; composed?: boolean },
  ) {
    super(type);
  }
  get detail(): unknown {
    return this.init.detail;
  }
}

class FakeStyleSheet {
  cssRules: unknown[] = [];
  replaceSync(_css: string): void {}
}

class FakeMutationObserver {
  constructor(_callback: () => void) {}
  observe(_target: unknown, _options: unknown): void {}
  disconnect(): void {}
}

const fakeDocument = new FakeNode("document");
Object.assign(fakeDocument, {
  adoptedStyleSheets: [] as FakeStyleSheet[],
  createElement: (tagName: string) => {
    const node = new FakeNode(tagName);
    if (tagName === "aui-button") {
      node.onConnect = () => {
        if (!node.getAttribute("label")) {
          throw new Error("Button label is required before connection");
        }
      };
    }
    return node;
  },
});
installFakes();
const { Chat } = await import("./chat.ts");
restoreFakes();

Deno.test("Chat emits a contextual event and keeps literal messages through send/reply states", () => {
  installFakes();
  try {
    const chat = new Chat();
  chat.id = "chat-1";
  chat.connectedCallback();
  chat.setConnection(true);
  chat.setAgentBusy(false);

  let received: FakeCustomEvent | undefined;
  chat.addEventListener("agent-message", (event) => {
    received = event as unknown as FakeCustomEvent;
  });
  const textarea = chat.querySelector("textarea");
  const label = chat.querySelector("label");
  const form = chat.querySelector("form");
  if (!textarea || !label || !form) throw new Error("Chat composer was not mounted");
  if (
    !textarea.id || !textarea.id.startsWith("chat-input-") ||
    label.htmlFor !== textarea.id || label.getAttribute("for") !== textarea.id
  ) {
    throw new Error("Chat input label is not associated with its unique textarea");
  }
  const secondChat = new Chat();
  secondChat.connectedCallback();
  const secondTextarea = secondChat.querySelector("textarea");
  if (!secondTextarea || secondTextarea.id === textarea.id) {
    throw new Error("Chat input IDs must be unique per instance");
  }
  textarea.value = "<b>literal</b>";
  form.emit("submit");

  const detail = received?.detail as { text: string; context: { componentId: string } };
  if (
    !received?.init.bubbles || !received.init.composed ||
    detail.text !== "<b>literal</b>" || detail.context.componentId !== "chat-1"
  ) {
    throw new Error("Chat event did not preserve text and component context");
  }
  chat.markSent();
  const area = chat.querySelector(".messages");
  const sent = area?.children[0]?.children[1];
  if (sent?.textContent !== "<b>literal</b>") {
    throw new Error("Chat rendered outgoing text as markup");
  }

  chat.reject("Try again");
  if (textarea.value !== "<b>literal</b>") {
    throw new Error("Chat did not restore rejected text for deliberate retry");
  }
  chat.receiveMessage({ text: "<i>reply</i>" });
  const reply = area?.children[1]?.children[1];
    if (!reply || reply.textContent !== "<i>reply</i>") {
      throw new Error("Chat rendered reply text incorrectly");
    }
  textarea.value = "next";
  form.emit("submit");
  received = undefined;
  chat.receiveMessage("<i>invalid legacy reply</i>");
  if (chat.querySelector(".status")?.textContent !== "Reply payload is invalid for Chat · no automatic resend") {
    throw new Error("Chat accepted a non-object reply payload");
  }
  if (received) throw new Error("Invalid reply automatically resent a message");
  form.emit("submit");
  if (!received) throw new Error("Invalid component reply left Chat permanently pending");
  } finally {
    restoreFakes();
  }
});

Deno.test("Chat initializes its catalog Button before the element connects", () => {
  installFakes();
  try {
    const chat = new Chat();
    chat.connectedCallback();
    const button = chat.querySelector("aui-button");
    if (button?.getAttribute("label") !== "Send") {
      throw new Error("Chat did not initialize the Button label before connection");
    }
  } finally {
    restoreFakes();
  }
});

Deno.test("Chat preserves explicit disconnected, pending, and busy presentation states", () => {
  installFakes();
  try {
    const chat = new Chat();
  chat.connectedCallback();
  chat.setConnection(false);
  if (chat.querySelector(".status")?.textContent !== "Disconnected · no automatic resend") {
    throw new Error("Disconnected state is not visible");
  }
  chat.setConnection(true, true);
  if (chat.querySelector(".status")?.textContent !== "Waiting for the outstanding reply…") {
    throw new Error("Pending state is not visible");
  }
  chat.setAgentBusy(true);
    if (chat.querySelector(".status")?.textContent !== "Waiting for the outstanding reply…") {
      throw new Error("Pending state was hidden by busy state");
    }
  } finally {
    restoreFakes();
  }
});

function installFakes(): void {
  globals.HTMLElement = FakeNode;
  globals.CSSStyleSheet = FakeStyleSheet;
  globals.MutationObserver = FakeMutationObserver;
  globals.CustomEvent = FakeCustomEvent;
  globals.document = fakeDocument;
}

function restoreFakes(): void {
  for (const [name, value] of originals) {
    if (value === undefined) delete globals[name];
    else globals[name] = value;
  }
}

function matches(node: FakeNode, selector: string): boolean {
  if (selector === "aui-button button") return false;
  if (selector.startsWith(".")) return node.className.split(/\s+/).includes(selector.slice(1));
  if (selector.includes(" ")) return false;
  return node.tagName === selector;
}
