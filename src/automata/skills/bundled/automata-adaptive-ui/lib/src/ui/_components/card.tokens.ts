import { tokens } from "../tokens.js";
import { radius } from "../_tokens/primitives/radius.js";
import { spacing } from "../_tokens/primitives/spacing.js";

/** Presentation roles owned by the Card component. */
export const cardTokens = {
  background: tokens.surface,
  foreground: tokens.text,
  border: tokens.border,
  radius: radius.md,
  gap: spacing.md,
  paddingSm: spacing.sm,
  paddingMd: spacing.md,
  paddingLg: spacing.lg,
} as const;
