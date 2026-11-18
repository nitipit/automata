import sendIcon from "./_assets/gnomicon/paper-plane.svg";
import stopIcon from "./_assets/gnomicon/media-playback-stop.svg";
import { Base } from "./_components/base";
import { Select, type SelectOption } from "./_components/select";
import type { ResolvedTheme } from "./_theme/index";
import { composerStyle, composerTheme } from "./chat-composer.style";

type Action = "send" | "stop" | "stopping";
type OptionList = { choices: [string, string][]; selected?: string; fallback: string };

/** One stable native form per chat. Requests are intents; the page owns confirmation. */
export class ChatComposer extends Base {
  private readonly form = document.createElement("form");
  private readonly prompt: HTMLTextAreaElement;
  private readonly send: HTMLButtonElement;
  private readonly model: Select;
  private readonly thinking: Select;
  private confirmedModel = "";
  private confirmedLevel = "";
  private allowSend = false;
  onSend?: (text: string) => void;
  onStop?: () => void;
  onModel?: (key: string) => void;
  onThinking?: (level: string) => void;

  constructor() {
    super();
    const form = this.form;
    form.id = "composer";
    form.innerHTML = `
      <p id="connection-detail" role="status"></p>
      <p id="run-status" role="status" aria-live="polite"></p>
      <label for="prompt">Message</label>
      <textarea id="prompt" name="prompt" rows="3" placeholder="Write a message…" required></textarea>
      <div class="composer-actions">
        <div class="runtime-controls" role="group" aria-label="Next message settings"></div>
        <button id="send" type="button" aria-label="Send message" title="Send message" disabled></button>
      </div>
      <p id="runtime-controls-status" role="status"></p>
      <p class="composer-hint">Enter to send · Shift+Enter for a new line</p>`;
    this.prompt = form.querySelector("textarea")!;
    this.send = form.querySelector("button")!;
    const initial = { disabled: true, value: "", options: [{ value: "", label: "Unavailable", disabled: true }] };
    this.model = Select.create({ _data: { ...initial, label: "Model", name: "model" } });
    this.thinking = Select.create({ _data: { ...initial, label: "Thinking", name: "thinking-level" } });
    form.querySelector(".runtime-controls")!.append(this.model, this.thinking);
    form.addEventListener("submit", event => {
      event.preventDefault();
      const text = this.draft.trim();
      if (this.allowSend && text) this.onSend?.(text);
    });
    this.prompt.addEventListener("keydown", event => {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault(); form.requestSubmit();
      }
    });
    this.prompt.addEventListener("input", () => this.refreshButton());
    this.send.addEventListener("click", () => {
      if (this.send.dataset.action === "stop") this.onStop?.();
      else if (this.allowSend) form.requestSubmit();
    });
    this.model.addEventListener("change", () => {
      const key = this.model.value;
      this.model.value = this.confirmedModel;
      if (key !== this.confirmedModel) this.onModel?.(key);
    });
    this.thinking.addEventListener("change", () => {
      const level = this.thinking.value;
      this.thinking.value = this.confirmedLevel;
      if (level !== this.confirmedLevel) this.onThinking?.(level);
    });
  }
  override connectedCallback() {
    if (this.form.parentNode !== this) this.append(this.form);
    super.connectedCallback();
  }
  get draft() { return this.prompt.value; }
  set draft(text: string) { this.prompt.value = text; this.refreshButton(); }
  get runStatus() { return this.form.querySelector("#run-status")!.textContent ?? ""; }
  set runStatus(text: string) { this.form.querySelector("#run-status")!.textContent = text; }
  set connectionDetail(text: string) { this.form.querySelector("#connection-detail")!.textContent = text; }
  setAction(mode: Action, allowSend: boolean, editorDisabled: boolean) {
    this.allowSend = allowSend;
    this.prompt.disabled = editorDisabled;
    if (this.send.dataset.action !== mode) {
      this.send.dataset.action = mode;
      this.send.innerHTML = mode === "send" ? sendIcon : stopIcon;
      this.send.firstElementChild?.setAttribute("aria-hidden", "true");
      this.send.title = mode === "send" ? "Send message" : mode === "stop" ? "Stop response" : "Stopping…";
      this.send.setAttribute("aria-label", this.send.title);
    }
    this.refreshButton();
  }
  private refreshButton() {
    const mode = this.send.dataset.action;
    this.send.disabled = mode !== "stop" && !(mode === "send" && this.allowSend && this.draft.trim());
  }
  setOptions(model: OptionList, level: OptionList) {
    const populate = (select: Select, { choices, selected, fallback }: OptionList) => {
      const current = selected ?? "";
      const options: SelectOption[] = choices.map(([value, label]) => ({ value, label }));
      if (!selected || !options.some(({ value }) => value === current)) {
        options.unshift({ value: current, label: fallback, disabled: true });
      }
      select.setOptions(options, current);
      return current;
    };
    this.confirmedModel = populate(this.model, model);
    this.confirmedLevel = populate(this.thinking, level);
  }
  setControls(modelDisabled: boolean, thinkingDisabled: boolean, note: string) {
    this.model.disabled = modelDisabled;
    this.thinking.disabled = thinkingDisabled;
    const status = this.form.querySelector("#runtime-controls-status")!;
    if (status.textContent !== note) status.textContent = note;
  }
  protected themedStyle(theme: ResolvedTheme) { return composerTheme(theme); }
}
ChatComposer.css = composerStyle;
ChatComposer.define("chat-composer");
