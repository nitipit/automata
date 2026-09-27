import { Base } from "./base.js";
import { type CardData, validateCardData } from "./card.schema.js";
import { cardTokens as tokens } from "./card.tokens.js";

/** A styled surface container for composing catalog content. */
export class Card extends Base<CardData> {
  #applyingData = false;

  static get observedAttributes(): string[] {
    return ["variant", "padding"];
  }

  static {
    this.css = `
      display: grid;
      gap: ${tokens.gap};
      box-sizing: border-box;
      padding: ${tokens.paddingMd};
      border: 1px solid ${tokens.border};
      border-radius: ${tokens.radius};
      background: ${tokens.background};
      color: ${tokens.foreground};
    `;
  }

  static override validateData(data: unknown): CardData {
    return validateCardData(data);
  }

  override connectedCallback(): void {
    super.connectedCallback();
    this.applyAttributes();
  }

  attributeChangedCallback(_name: string, oldValue: string | null, newValue: string | null): void {
    if (oldValue !== newValue && this.isConnected && !this.#applyingData) this.applyAttributes();
  }

  override applyData(data: CardData): void {
    this.#applyingData = true;
    try {
      if (this.getAttribute("variant") !== data.variant) this.setAttribute("variant", data.variant);
      if (this.getAttribute("padding") !== data.padding) this.setAttribute("padding", data.padding);
    } finally {
      this.#applyingData = false;
    }
  }

  private applyAttributes(): void {
    this.applyData(validateCardData({
      variant: this.getAttribute("variant") ?? undefined,
      padding: this.getAttribute("padding") ?? undefined,
    }));
  }
}

Card.addStyle(`
  &[variant="outlined"] {
    background: transparent;
  }

  &[padding="sm"] {
    padding: ${tokens.paddingSm};
  }

  &[padding="lg"] {
    padding: ${tokens.paddingLg};
  }
`);
