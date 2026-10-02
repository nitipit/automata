import type { ChatData } from "./types.js";
let inputSequence = 0;
/** Chat-owned DOM composition; catalog Buttons own native button reconciliation. */
export function createChatView(chat: HTMLElement) {
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
  form.className = "composer";
  const label = document.createElement("label");
  const textarea = document.createElement("textarea");
  textarea.id = `chat-input-${++inputSequence}`;
  textarea.name = "message";
  textarea.rows = 1;
  textarea.required = true;
  textarea.maxLength = 6000;
  label.htmlFor = textarea.id;
  label.setAttribute("for", textarea.id);
  const footer = document.createElement("div");
  footer.className = "footer";
  const status = document.createElement("span");
  status.className = "status";
  status.setAttribute("role", "status");
  const button = document.createElement("aui-button");
  button.setAttribute("label", "Send");
  button.setAttribute("type", "submit");
  const feedback = document.createElement("pre");
  feedback.className = "feedback";
  feedback.setAttribute("role", "alert");
  const feedbackButton = document.createElement("aui-button");
  feedbackButton.className = "validation-send";
  feedbackButton.setAttribute("label", "Send validation feedback");
  feedbackButton.setAttribute("type", "button");
  feedbackButton.hidden = true;
  footer.append(status, button);
  form.append(label, textarea, footer, feedback, feedbackButton);
  chat.append(header, area, form);
  return { heading, area, empty, form, label, textarea, status, button, feedback, feedbackButton };
}
export type ChatView = ReturnType<typeof createChatView>;
export function updateChatView(view: ChatView, data: ChatData, chat: HTMLElement): void {
  view.heading.textContent = data.title;
  view.label.textContent = data.inputLabel;
  view.textarea.placeholder = data.placeholder;
  view.button.setAttribute("label", data.sendLabel);
  view.empty.textContent = data.emptyMessage;
  for (const article of chat.querySelectorAll(".message")) {
    const label = article.querySelector("strong");
    if (label) label.textContent = article.getAttribute("data-role") === "user" ? data.userLabel : data.agentLabel;
  }
}
export function disableChatView(view: ChatView, disabled: boolean): void {
  for (const button of [view.button, view.feedbackButton]) {
    button.setAttribute("aria-disabled", String(disabled));
    const native = button.querySelector("button");
    if (native) native.disabled = disabled;
  }
}
