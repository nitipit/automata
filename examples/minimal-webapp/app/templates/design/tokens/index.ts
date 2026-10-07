/** Adaptive UI's semantic roles, with a GNOME-inspired app theme. */
export { tokens } from "@adaptive/tokens";

export const space = { small: "0.5rem", medium: "1rem", large: "1.5rem" } as const;
export const radius = { panel: "0.75rem" } as const;

/** Theme overrides, not GTK/libadwaita widgets or native platform integration. */
export const theme = {
  "--aui-surface": "#ffffff",
  "--aui-text": "#2e3436",
  "--aui-muted-text": "#5e5c64",
  "--aui-border": "#deddda",
  "--aui-action": "#3584e4",
  "--aui-action-hover": "#1c71d8",
  "--aui-action-text": "#ffffff",
  "--aui-focus": "#1c71d8",
  "--app-background": "#fafafa",
  "--app-header": "#ebebeb",
  "--app-neutral": "#e5e5e5",
  "--app-neutral-hover": "#d5d5d5",
} as const;

export const controls = {
  neutral: "var(--app-neutral, #e5e5e5)",
  neutralHover: "var(--app-neutral-hover, #d5d5d5)",
} as const;
