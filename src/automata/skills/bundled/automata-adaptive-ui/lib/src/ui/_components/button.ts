import { Base } from "./base.js";
import { paletteEntries as colors } from "../_tokens/color.js";
import { radius } from "../_tokens/radius.js";
import { spacing } from "../_tokens/spacing.js";
import { typography } from "../_tokens/typography.js";

export type ButtonData = {
  label?: string;
  type?: "button" | "submit" | "reset";
  disabled?: boolean;
};

/** Light-DOM native button. Disabled follows attribute presence, not its text. */
export class Button extends Base<ButtonData> {
  #button: HTMLButtonElement | null = null;

  static get observedAttributes(): string[] {
    return ["label", "type", "disabled"];
  }

  static {
    this.css = `
      display: inline-flex;
      vertical-align: middle;
      button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        box-sizing: border-box;
        min-height: 2.25rem;
        margin: 0;
        border: 1px solid ${colors["blue.5"]};
        border-radius: ${radius.md};
        padding: ${spacing.sm} ${spacing.md};
        background: ${colors["blue.4"]};
        color: ${colors["light.1"]};
        font: inherit;
        font-size: .875rem;
        font-weight: ${typography.weightMedium};
        line-height: 1.25;
        text-align: center;
        cursor: pointer;
      }
      button:hover:not(:disabled) { background: ${colors["blue.5"]}; }
      button:focus-visible { outline: 2px solid ${colors["blue.4"]}; outline-offset: 3px; }
      button:disabled {
        background: ${colors["light.3"]};
        border-color: ${colors["light.4"]};
        color: ${colors["dark.2"]};
        cursor: not-allowed;
      }
    `;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    this.syncButton();
  }

  attributeChangedCallback(): void {
    if (this.isConnected) this.syncButton();
  }

  override applyData(data: ButtonData = {}): void {
    if (data.label !== undefined) this.setAttribute("label", data.label);
    if (data.type !== undefined) this.setAttribute("type", data.type);
    if (data.disabled !== undefined) this.toggleAttribute("disabled", data.disabled);
    this.syncButton();
  }

  private syncButton(): void {
    if (!this.#button) {
      this.#button = this.querySelector<HTMLButtonElement>(":scope > button") ??
        document.createElement("button");
      if (!this.#button.parentNode) this.append(this.#button);
    }
    const label = this.getAttribute("label");
    if (label !== null) this.#button.textContent = label;
    this.#button.type = (this.getAttribute("type") ?? "button") as HTMLButtonElement["type"];
    this.#button.disabled = this.hasAttribute("disabled");
  }
}
