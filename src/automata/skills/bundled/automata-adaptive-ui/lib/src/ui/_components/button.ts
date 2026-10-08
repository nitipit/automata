import { Base } from "./base.js";
import { type ButtonData, validateButtonData } from "./button.schema.js";
import { buttonTokens as tokens } from "./button.tokens.js";

/**
 * Native-button wrapper. `disabled` data reflects the boolean attribute: presence
 * disables, including disabled="false". Removing it enables the native control.
 * Validate data before direct applyData(); omitted disabled defaults to false.
 */
export class Button extends Base<ButtonData> {
  #button: HTMLButtonElement | null = null;
  #applyingData = false;

  static get observedAttributes(): string[] {
    return ["label", "tone", "type", "disabled"];
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
        outline: 2px solid ${tokens.focus};
        outline-offset: 2px;
      }

      button:hover:not(:disabled) {
        background: ${tokens.backgroundHover};
      }

      button:disabled {
        opacity: .45;
        cursor: not-allowed;
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
      this.toggleAttribute("disabled", data.disabled);
      this.setAttributeIfChanged("aria-disabled", String(data.disabled));
      button.disabled = data.disabled;
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
      disabled: this.hasAttribute("disabled"),
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
