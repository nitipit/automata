import { Base } from "./base.js";
import { paletteEntries as colors } from "../_tokens/color.js";
import { radius } from "../_tokens/radius.js";
import { spacing } from "../_tokens/spacing.js";

/** Plain container: content is ordinary HTML; appearance belongs to this CSS. */
export class Card extends Base {
  static {
    this.css = `
      display: grid;
      gap: ${spacing.md};
      padding: ${spacing.lg};
      border: 1px solid ${colors["light.4"]};
      border-radius: ${radius.md};
      background: ${colors["light.1"]};
      color: ${colors["dark.4"]};
    `;
  }
}
