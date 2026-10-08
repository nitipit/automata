import { type PaletteColor } from "./_tokens/primitives/color.js";
import { resolveColor } from "./_tokens/primitives/effects.js";

export type ThemeMode = "light" | "dark";
/** Small Theme selections, not the complete legacy semantic/Chat catalog. */
export type ThemeTokens = Record<
  "background" | "surface" | "text" | "mutedText" | "border" | "action" |
  "actionHover" | "actionText" | "danger" | "focus", PaletteColor
> & { clear: "effect.clear" };
export type ThemeColors = { readonly [Role in keyof ThemeTokens]: string };
export type ThemeStyleFactory = (scope: string, colors: ThemeColors) => string;

export const themeTokens = {
  light: {
    background: "light.2", surface: "light.1", text: "dark.4",
    mutedText: "dark.2", border: "dark.1", action: "blue.4",
    actionHover: "blue.5", actionText: "light.1", danger: "red.4",
    focus: "blue.4", clear: "effect.clear",
  },
  dark: {
    background: "dark.4", surface: "dark.3", text: "light.2",
    mutedText: "light.3", border: "light.5", action: "blue.1",
    actionHover: "blue.2", actionText: "dark.4", danger: "red.1",
    focus: "blue.1", clear: "effect.clear",
  },
} as const satisfies Record<ThemeMode, ThemeTokens>;

export function validateThemeMode(value: unknown): ThemeMode {
  if (value !== "light" && value !== "dark") throw new TypeError("Theme mode must be light or dark");
  return value;
}

export function resolveThemeColors(mode: ThemeMode): ThemeColors {
  const choices = themeTokens[validateThemeMode(mode)];
  return Object.fromEntries(Object.entries(choices).map(([role, entry]) => [
    role, resolveColor(entry),
  ])) as ThemeColors;
}

/** 16px root anchors: body16→18px and heading28→40px at viewport600→1200px.
 * Rem bounds respond to root text sizing; no custom properties are generated.
 */
export const themeTypography = {
  body: "clamp(1rem, calc(0.875rem + 0.333333vw), 1.125rem)",
  heading: "clamp(1.75rem, calc(1rem + 2vw), 2.5rem)",
} as const;
