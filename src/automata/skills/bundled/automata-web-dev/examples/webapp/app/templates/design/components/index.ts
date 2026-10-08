import { Form } from "@adaptive/form";
import { Chat } from "@adaptive/chat";
import { alternateChatTheme } from "../tokens/index.ts";

/** Application composition only; component schemas/state stay in Adaptive UI. */
export function mountComponentExamples(): void {
  const formHost = document.querySelector("#form-example");
  const chatHost = document.querySelector<HTMLElement>("#chat-example");
  if (!formHost || !chatHost) return;

  const primary = document.querySelector("#primary-button")!;
  const disabled = document.querySelector("#disabled-button")!;
  const result = document.querySelector("#button-result")!;
  primary.addEventListener("click", () => { result.textContent = "Primary clicked."; });
  disabled.addEventListener("click", () => { result.textContent = "Enabled button clicked."; });
  document.querySelector("#toggle-disabled")!.addEventListener("click", () => {
    disabled.toggleAttribute("disabled");
    disabled.setAttribute("label", disabled.hasAttribute("disabled") ? "Disabled" : "Enabled");
  });

  const data = Form.validateData({
    title: "Local preferences",
    fields: [
      { name: "name", kind: "text", label: "Name", required: true },
      { name: "density", kind: "choice", label: "Density", required: false, choices: [
        { value: "comfortable", label: "Comfortable" },
        { value: "compact", label: "Compact" },
      ] },
    ],
    submitLabel: "Show values locally",
  });
  const form = Form.create({ data });
  formHost.append(form);
  form.addEventListener("aui-form-submit", (event) => {
    const values = (event as CustomEvent<{ values: Record<string, string> }>).detail.values;
    document.querySelector("#form-result")!.textContent = JSON.stringify(values, null, 2);
  });
  let updated = false;
  document.querySelector("#update-form")!.addEventListener("click", () => {
    updated = !updated;
    form.applyData(Form.validateData({ ...data, title: updated ? "Updated preferences" : data.title }));
  });
  document.querySelector("#reset-form")!.addEventListener("click", () => {
    form.querySelector("form")!.reset();
  });

  const chat = Chat.create({ data: Chat.validateData({ title: "Local Chat preview" }) });
  chatHost.append(chat);
  chat.addMessage("agent", "Reusable components use semantic theme roles.");
  chat.addMessage("user", "This is sample history, not a sent message.");
  chat.setConnection(false);
  document.querySelector("#chat-theme")!.addEventListener("click", () => {
    const alternate = chatHost.dataset.theme !== "alternate";
    chatHost.dataset.theme = alternate ? "alternate" : "default";
    for (const [variable, value] of Object.entries(alternateChatTheme)) {
      if (alternate) chatHost.style.setProperty(variable, value);
      else chatHost.style.removeProperty(variable);
    }
  });
}
