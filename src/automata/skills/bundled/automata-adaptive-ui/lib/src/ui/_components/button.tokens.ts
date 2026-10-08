import { componentColorValues, type ComponentColorRoles } from "../tokens.js";
import { radius } from "../_tokens/primitives/radius.js";
import { spacing } from "../_tokens/primitives/spacing.js";
import { typography } from "../_tokens/primitives/typography.js";
import { type ThemeColors } from "../theme.tokens.js";

/** Color roles reference semantic intent, independently of a selected theme. */
export const buttonColorRoles = {
  background: "action",
  backgroundHover: "actionHover",
  dangerBackground: "danger",
  foreground: "actionText",
  focus: "focus",
} as const satisfies ComponentColorRoles;

/** Presentation roles owned by the Button component. */
export const buttonTokens = {
  ...componentColorValues(buttonColorRoles),
  radius: radius.md,
  paddingBlock: spacing.sm,
  paddingInline: spacing.md,
  weight: typography.weightMedium,
} as const;

/** Scoped concrete paint; structural Adapter styles and native behavior stay owned by Button. */
export function buttonThemeStyles(scope: string, colors: ThemeColors, tag = "aui-button"): string {
  const selector = `${scope} ${tag}`;
  return `
    ${selector} button { background: ${colors.action}; color: ${colors.actionText}; }
    ${selector} button:hover:not(:disabled) { background: ${colors.actionHover}; }
    ${selector}[tone="danger"] button,
    ${selector}[tone="danger"] button:hover:not(:disabled) { background: ${colors.danger}; }
    ${selector} button:focus-visible { outline-color: ${colors.focus}; }
  `;
}
