import { componentColorValues, type ComponentColorRoles } from "../tokens.js";
import { radius } from "../_tokens/primitives/radius.js";
import { spacing } from "../_tokens/primitives/spacing.js";
import { type ThemeColors } from "../theme.tokens.js";

export const cardColorRoles = {
  background: "surface",
  outlinedBackground: "clear",
  foreground: "text",
  border: "border",
} as const satisfies ComponentColorRoles;

/** Presentation roles owned by the Card component. */
export const cardTokens = {
  ...componentColorValues(cardColorRoles),
  radius: radius.md,
  gap: spacing.md,
  paddingSm: spacing.sm,
  paddingMd: spacing.md,
  paddingLg: spacing.lg,
} as const;

/** Scoped concrete paint; geometry/variants remain owned by Card. */
export function cardThemeStyles(scope: string, colors: ThemeColors, tag = "aui-card"): string {
  const selector = `${scope} ${tag}`;
  return `
    ${selector} { background: ${colors.surface}; color: ${colors.text}; border-color: ${colors.border}; }
    ${selector}[variant="outlined"] { background: ${colors.clear}; }
  `;
}
