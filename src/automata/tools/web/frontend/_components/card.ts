import { Base } from "./base";
import type { ResolvedTheme } from "../_theme/index";
import { cardStyle, cardTheme } from "./card.style";

/** A content container; provide a native heading or an accessible label when useful. */
export class Card extends Base {
  protected themedStyle(theme: ResolvedTheme): string { return cardTheme(theme); }
}
Card.css = cardStyle;
Card.define("ui-card");
