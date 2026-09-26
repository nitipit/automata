import { palette } from "./_tokens/primitives/color.js";

/** Supported semantic CSS values. Override --aui-* on an ancestor or component. */
export const tokens = {
  surface: `var(--aui-surface, ${palette.white})`,
  text: `var(--aui-text, ${palette.slate[950]})`,
  mutedText: "var(--aui-muted-text, #475569)",
  border: `var(--aui-border, ${palette.slate[300]})`,
  action: `var(--aui-action, ${palette.blue[600]})`,
  actionHover: `var(--aui-action-hover, ${palette.blue[700]})`,
  actionText: `var(--aui-action-text, ${palette.white})`,
  danger: `var(--aui-danger, ${palette.red[600]})`,
  focus: `var(--aui-focus, ${palette.blue[600]})`,
  status: "var(--aui-status, #475569)",
} as const;
