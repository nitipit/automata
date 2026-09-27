import { tokens } from "../tokens.js";
import { radius } from "../_tokens/primitives/radius.js";
import { spacing } from "../_tokens/primitives/spacing.js";
import { typography } from "../_tokens/primitives/typography.js";

/** Presentation roles owned by the Button component. */
export const buttonTokens = {
  background: tokens.action,
  backgroundHover: tokens.actionHover,
  dangerBackground: tokens.danger,
  foreground: tokens.actionText,
  radius: radius.md,
  paddingBlock: spacing.sm,
  paddingInline: spacing.md,
  weight: typography.weightMedium,
} as const;
