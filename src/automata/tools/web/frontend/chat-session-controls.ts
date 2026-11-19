import editIcon from "./_assets/gnomicon/document-edit-symbolic.svg";
import { Base } from "./_components/base";
import type { ResolvedTheme } from "./_theme/index";
import { sessionControlsStyle, sessionControlsTheme } from "./chat-session-controls.style";

type Availability = { switchSession: boolean; newSession: boolean; rename: boolean; renamePending: boolean };

/** Session chrome only: the page owns confirmation, navigation, and connection. */
export class ChatSessionControls extends Base {
  private readonly row = document.createElement("div");
  private readonly heading: HTMLHeadingElement;
  private readonly titleRow: HTMLElement;
  private readonly renameButton: HTMLButtonElement;
  private readonly renameForm: HTMLFormElement;
  private readonly nameInput: HTMLInputElement;
  private readonly renameError: HTMLElement;
  private readonly switchButton: HTMLButtonElement;
  private readonly newButton: HTMLButtonElement;
  private readonly connectionStatus: HTMLElement;
  private readonly connectionDetail: HTMLElement;
  private readonly retryButton: HTMLButtonElement;
  private initialName = "";
  private attemptedName?: string;

  onRename?: (name: string) => boolean;
  onSwitch?: () => void;
  onNewSubmit?: () => boolean;
  onNewData?: (data: FormData) => void;
  onRetry?: () => void;

  constructor() {
    super();
    this.row.className = "session-row";
    this.row.innerHTML = `
      <div class="session-identity">
        <div class="session-title">
          <h1 id="session-name">Untitled session</h1>
          <button id="rename" type="button" aria-label="Rename session" title="Rename session" disabled></button>
          <form id="rename-form" hidden>
            <input id="session-name-input" aria-label="Session name" autocomplete="off" aria-describedby="rename-error">
          </form>
        </div>
        <p id="rename-error" role="alert"></p>
      </div>
      <div class="session-actions">
        <button id="sessions" type="button" aria-haspopup="dialog" aria-controls="sessions-picker" disabled>Switch session</button>
        <form id="new-chat-form" method="post" action="/sessions" target="_blank" rel="noopener">
          <button id="new-chat" type="submit" title="Open a new session in a new tab" disabled>New session</button>
        </form>
      </div>
      <div class="session-connection">
        <span id="connection-status" role="status">Connecting…</span>
        <button id="connect" type="button" disabled>Retry connection</button>
        <p id="connection-detail" role="status"></p>
      </div>`;
    const find = <T extends HTMLElement>(selector: string) => this.row.querySelector<T>(selector)!;
    this.heading = find("#session-name");
    this.titleRow = find(".session-title");
    this.renameButton = find("#rename");
    this.renameForm = find("#rename-form");
    this.nameInput = find("#session-name-input");
    this.renameError = find("#rename-error");
    this.switchButton = find("#sessions");
    this.newButton = find("#new-chat");
    this.connectionStatus = find("#connection-status");
    this.connectionDetail = find("#connection-detail");
    this.retryButton = find("#connect");
    // Bundled, reviewed Gnomicon SVG only; never server/user markup.
    this.renameButton.innerHTML = editIcon;
    this.renameButton.firstElementChild?.setAttribute("aria-hidden", "true");
    this.renameButton.addEventListener("click", () => this.editName());
    this.heading.addEventListener("click", () => this.editName());
    this.nameInput.addEventListener("input", () => { this.attemptedName = undefined; this.clearRenameError(); });
    this.nameInput.addEventListener("blur", () => this.saveName(true));
    this.nameInput.addEventListener("keydown", event => {
      if (!event.isComposing && event.key === "Escape" && !this.nameInput.readOnly) {
        event.preventDefault();
        this.closeRename(true);
      }
    });
    this.renameForm.addEventListener("submit", event => { event.preventDefault(); this.saveName(false); });
    this.switchButton.addEventListener("click", () => this.onSwitch?.());
    this.retryButton.addEventListener("click", () => this.onRetry?.());
    const newForm = find<HTMLFormElement>("#new-chat-form");
    newForm.addEventListener("submit", event => {
      if (this.newButton.disabled || !this.onNewSubmit?.()) event.preventDefault();
    });
    newForm.addEventListener("formdata", event => this.onNewData?.(event.formData));
  }
  override connectedCallback() {
    if (this.row.parentNode !== this) this.append(this.row);
    super.connectedCallback();
  }
  setName(title: string) {
    if (this.heading.textContent !== title) this.heading.textContent = title;
    this.heading.title = title;
  }
  setAvailability({ switchSession, newSession, rename, renamePending }: Availability) {
    this.switchButton.disabled = !switchSession;
    this.newButton.disabled = !newSession;
    this.renameButton.disabled = !rename;
    this.nameInput.readOnly = renamePending;
  }
  setConnection(label: string, detail: string, retryVisible: boolean, retryEnabled: boolean) {
    if (this.connectionStatus.textContent !== label) this.connectionStatus.textContent = label;
    if (this.connectionDetail.textContent !== detail) this.connectionDetail.textContent = detail;
    this.retryButton.hidden = !retryVisible;
    this.retryButton.disabled = !retryEnabled;
  }
  focusSwitch() {
    if (!this.switchButton.disabled) this.switchButton.focus({ preventScroll: true });
  }
  finishRename(error?: string) {
    if (this.renameForm.hidden) return;
    if (error) this.renameError.textContent = error;
    else this.closeRename(document.activeElement === this.nameInput);
  }
  private clearRenameError() {
    this.renameError.textContent = "";
    this.nameInput.removeAttribute("aria-invalid");
  }
  private closeRename(restoreFocus: boolean) {
    this.renameForm.hidden = true;
    delete this.titleRow.dataset.editing;
    this.clearRenameError();
    if (restoreFocus && !this.renameButton.disabled) this.renameButton.focus({ preventScroll: true });
  }
  private editName() {
    if (this.renameButton.disabled || !this.renameForm.hidden) return;
    this.initialName = this.heading.textContent?.trim() ?? "";
    this.attemptedName = undefined;
    this.nameInput.value = this.initialName;
    this.renameForm.hidden = false;
    this.titleRow.dataset.editing = "";
    this.clearRenameError();
    this.nameInput.focus({ preventScroll: true });
    this.nameInput.select();
  }
  private saveName(fromBlur: boolean) {
    if (this.renameForm.hidden || this.nameInput.readOnly) return;
    const name = this.nameInput.value.trim();
    if (fromBlur && name === this.attemptedName) return;
    if (name === this.initialName) { this.closeRename(!fromBlur); return; }
    if (!name) {
      this.renameError.textContent = "Enter a session name.";
      this.nameInput.setAttribute("aria-invalid", "true");
      return;
    }
    this.attemptedName = name;
    if (!this.renameButton.disabled && this.onRename?.(name)) this.clearRenameError();
    else this.renameError.textContent = "Connection unavailable. Reconnect before saving.";
  }
  protected themedStyle(theme: ResolvedTheme) { return sessionControlsTheme(theme); }
}
ChatSessionControls.css = sessionControlsStyle;
ChatSessionControls.define("chat-session-controls");
