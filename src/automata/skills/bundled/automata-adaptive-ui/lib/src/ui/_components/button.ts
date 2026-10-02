import { Base } from "./base.js";
import { type ButtonData, validateButtonData } from "./button.schema.js";
import { buttonTokens as tokens } from "./button.tokens.js";
import { tokens as semantic } from "../tokens.js";

/** A native-button wrapper with validated catalog data and Adapter styles. */
export class Button extends Base<ButtonData> {
  #button: HTMLButtonElement | null = null;
  #applyingData = false;

  static get observedAttributes(): string[] {
    return ["label", "tone", "type"];
  }

  static {
    this.css = `
      display: inline-block;

      button {
        min-height: 2.5rem;
        border: 0;
        border-radius: ${tokens.radius};
        padding: ${tokens.paddingBlock} ${tokens.paddingInline};
        background: ${tokens.background};
        color: ${tokens.foreground};
        font: inherit;
        font-weight: ${tokens.weight};
        cursor: pointer;
      }

      button:focus-visible {
        outline: 2px solid ${semantic.focus};
        outline-offset: 2px;
      }

      button:hover {
        background: ${tokens.backgroundHover};
      }
    `;
  }

  static override validateData(data: unknown): ButtonData {
    return validateButtonData(data);
  }

  override connectedCallback(): void {
    super.connectedCallback();
    this.applyAttributes();
  }

  attributeChangedCallback(
    _name: string,
    oldValue: string | null,
    newValue: string | null,
  ): void {
    if (
      oldValue !== newValue && this.isConnected && !this.#applyingData
    ) {
      this.applyAttributes();
    }
  }

  override applyData(data: ButtonData): void {
    const button = this.ensureButton();
    this.#applyingData = true;
    try {
      this.setAttributeIfChanged("label", data.label);
      this.setAttributeIfChanged("tone", data.tone);
      this.setAttributeIfChanged("type", data.type);
      button.type = data.type;
      button.textContent = data.label;
    } finally {
      this.#applyingData = false;
    }
  }

  private applyAttributes(): void {
    this.applyData(validateButtonData({
      label: this.getAttribute("label") ?? undefined,
      tone: this.getAttribute("tone") ?? undefined,
      type: this.getAttribute("type") ?? undefined,
    }));
  }

  private setAttributeIfChanged(name: string, value: string): void {
    if (this.getAttribute(name) !== value) {
      this.setAttribute(name, value);
    }
  }

  private ensureButton(): HTMLButtonElement {
    if (!this.#button) {
      const existing = this.querySelector(":scope > button");
      this.#button = existing instanceof HTMLButtonElement
        ? existing
        : document.createElement("button");
      if (!existing) {
        this.append(this.#button);
      }
    }
    return this.#button;
  }
}

Button.addStyle(`
  &[tone="danger"] button {
    background: ${tokens.dangerBackground};
  }
`);
