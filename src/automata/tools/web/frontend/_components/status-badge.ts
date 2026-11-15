import { Base } from "./base";
import type { ResolvedTheme } from "../_theme/index";
import { statusBadgeStyle, statusBadgeTheme } from "./status-badge.style";

/** Styled light-DOM status; usable inside a document or another shadow root. */
export class StatusBadge extends Base {
  protected themedStyle(theme: ResolvedTheme): string { return statusBadgeTheme(theme); }
}
StatusBadge.css = statusBadgeStyle;
StatusBadge.define("status-badge");
