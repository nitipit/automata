import { palette } from "../_tokens/primitives/color.js";
import { radius } from "../_tokens/primitives/radius.js";
import { spacing } from "../_tokens/primitives/spacing.js";

/** Presentation roles owned by the Card component. */
export const cardTokens = {
  background: palette.white,
  foreground: palette.slate[950],
  border: palette.slate[300],
  radius: radius.md,
  gap: spacing.md,
  paddingSm: spacing.sm,
  paddingMd: spacing.md,
  paddingLg: spacing.lg,
} as const;
