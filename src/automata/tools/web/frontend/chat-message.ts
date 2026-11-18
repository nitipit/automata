import { Base } from "./_components/base";
import { createComponentRegistry } from "./_components/create";
import { stringData } from "./_components/descriptor-data";
import { Markdown } from "./_components/markdown";
import type { ResolvedTheme } from "./_theme/index";
import { chatMessageStyle, chatMessageThemeStyle } from "./chat-message.style";

export type ChatMessageData = { role: "user" | "assistant"; text: string };

/** Private message presentation. The app owns ordering, stream state, and tool-call routing. */
export class ChatMessage extends Base {
  private readonly article = document.createElement("article");
  private readonly speaker = document.createElement("span");
  private readonly interactive = document.createElement("div");
  private body?: HTMLElement;
  private activity?: HTMLParagraphElement;
  private outcome?: HTMLParagraphElement;

  static get create() { return createChatMessage; }

  protected themedStyle(theme: ResolvedTheme): string { return chatMessageThemeStyle(theme); }

  initialize({ role, text }: ChatMessageData, children: readonly HTMLElement[]) {
    if (this.body) throw new Error("ChatMessage is already initialized");
    this.dataset.speaker = role;
    this.article.className = `message ${role}`;
    this.speaker.className = "message-label";
    this.speaker.textContent = role === "user" ? "You" : "Automata";
    this.body = role === "assistant" ? new Markdown() : document.createElement("div");
    this.body.className = "message-body";
    this.interactive.className = "message-ui";
    this.article.append(this.speaker, this.body, this.interactive);
    this.append(this.article);
    this.setText(text);
    for (const child of children) this.mountInteractive(child);
  }

  setText(text: string) {
    if (this.body instanceof Markdown) this.body.source = text;
    else if (this.body) this.body.textContent = text;
  }

  get hasContent() { return !!this.body?.textContent || this.interactive.hasChildNodes(); }
  get hasOutcome() { return !!this.outcome; }

  private statusNote(className: string) {
    const note = document.createElement("p");
    note.className = className;
    note.setAttribute("role", "status");
    this.article.append(note);
    return note;
  }

  setActivity(text?: string) {
    if (text === undefined) {
      this.activity?.remove();
      this.activity = undefined;
    } else {
      this.activity ??= this.statusNote("reply-activity");
      if (this.activity.textContent !== text) this.activity.textContent = text;
    }
  }

  setOutcome(text: string) {
    this.outcome ??= this.statusNote("reply-outcome");
    if (this.outcome.textContent !== text) this.outcome.textContent = text;
  }

  mountInteractive(child: HTMLElement) {
    if (child.parentElement !== this.interactive) this.interactive.append(child);
  }

  private inactiveBlock(blockId: string) {
    return [...this.interactive.querySelectorAll<HTMLElement>(":scope > .inactive-ui")]
      .find(node => node.dataset.blockId === blockId);
  }

  clearInactiveInteractive(blockId: string) { this.inactiveBlock(blockId)?.remove(); }

  showInactiveInteractive(blockId: string) {
    if (this.inactiveBlock(blockId)) return;
    const notice = document.createElement("div");
    notice.className = "inactive-ui";
    notice.dataset.blockId = blockId;
    notice.textContent = "Interactive content from this reply is inactive after reload or a session switch.";
    this.mountInteractive(notice);
  }
}

ChatMessage.css = chatMessageStyle;
ChatMessage.define("chat-message");

const chatComponents = createComponentRegistry();
const createChatMessage = chatComponents.register("chat-message", ChatMessage,
  (element, data: ChatMessageData | undefined, children) => {
    const role = stringData(data, "role");
    const text = stringData(data, "text");
    if ((role !== "user" && role !== "assistant") || text === undefined) {
      throw new TypeError("chat-message requires a user or assistant role and text");
    }
    element.initialize({ role, text }, children);
  });
