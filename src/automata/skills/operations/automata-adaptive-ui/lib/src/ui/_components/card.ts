import { Base } from "./base.js";
import { type CardData, validateCardData } from "./card.schema.js";
import { cardTokens as tokens } from "./card.tokens.js";

/** A styled surface container for composing catalog content. */
export class Card extends Base<CardData> {
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
    this.applyData(validateCardData({
      variant: this.getAttribute("variant") ?? undefined,
      padding: this.getAttribute("padding") ?? undefined,
    }));
  }

  override applyData(data: CardData): void {
    this.setAttribute("variant", data.variant);
    this.setAttribute("padding", data.padding);
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
