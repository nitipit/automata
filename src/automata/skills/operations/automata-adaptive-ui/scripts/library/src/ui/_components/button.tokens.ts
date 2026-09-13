import { palette } from "../_tokens/primitives/color.js";
import { radius } from "../_tokens/primitives/radius.js";
import { spacing } from "../_tokens/primitives/spacing.js";
import { typography } from "../_tokens/primitives/typography.js";

/** Presentation roles owned by the Button component. */
export const buttonTokens = {
  background: palette.blue[600],
  backgroundHover: palette.blue[700],
  dangerBackground: palette.red[600],
  foreground: palette.white,
  radius: radius.md,
  paddingBlock: spacing.sm,
  paddingInline: spacing.md,
  weight: typography.weightMedium,
} as const;
