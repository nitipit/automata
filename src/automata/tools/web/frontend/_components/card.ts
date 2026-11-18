import { Base } from "./base";
import type { ResolvedTheme } from "../_theme/index";
import { cardStyle, cardTheme } from "./card.style";
import { registerSharedComponent } from "./create";
import { stringData } from "./descriptor-data";

type CardData = { label?: string };

/** A content container; provide a native heading or an accessible label when useful. */
export class Card extends Base {
  static get create() { return createCard; }
  protected themedStyle(theme: ResolvedTheme): string { return cardTheme(theme); }
}
Card.css = cardStyle;
Card.define("ui-card");
const createCard = registerSharedComponent("ui-card", Card,
  (element, data: CardData | undefined, children) => {
    const label = stringData(data, "label");
    if (label !== undefined) element.setAttribute("aria-label", label);
    element.append(...children);
  });
