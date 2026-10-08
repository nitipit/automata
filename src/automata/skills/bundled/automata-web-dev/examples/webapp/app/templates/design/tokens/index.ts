import { resolveColor, type ColorReference, type PaletteColor, semanticColorRoles,
  type SemanticColorRole } from "@adaptive/colors";
export { tokens } from "@adaptive/colors";

export const space = { small: "0.5rem", medium: "1rem", large: "1.5rem" } as const;
export const radius = { panel: "0.75rem" } as const;

/** User-selected UI mappings of the official icon/illustration palette. */
export const themePalette = {
  surface: "light.1", text: "dark.4", mutedText: "dark.2", border: "dark.1",
  action: "blue.4", actionHover: "blue.5", actionText: "light.1", focus: "blue.4",
} as const satisfies Partial<Record<SemanticColorRole, PaletteColor>>;

/** Page roles/effects remain app-owned, distinct from the official swatch list. */
export const appColorRoles = {
  background: { variable: "--app-background", color: "light.2" },
  header: { variable: "--app-header", color: "light.3" },
  neutral: { variable: "--app-neutral", color: "light.3" },
  neutralHover: { variable: "--app-neutral-hover", color: "light.4" },
  shadow: { variable: "--app-shadow", color: "effect.appShadow" },
} as const satisfies Record<string, { variable: `--app-${string}`; color: ColorReference }>;

export function semanticTheme(choices: Partial<Record<SemanticColorRole, PaletteColor>>) {
  return Object.fromEntries(Object.entries(choices).map(([role, color]) => [
    semanticColorRoles[role as SemanticColorRole].variable, resolveColor(color),
  ]));
}

export const theme = {
  ...semanticTheme(themePalette),
  ...Object.fromEntries(Object.values(appColorRoles).map(({ variable, color }) => [
    variable, resolveColor(color),
  ])),
};

/** Alternate local Chat demonstration, not complete dark Theme coverage. */
export const alternateChatPalette = {
  messageAgentSurface: "green.1", messageAgentText: "dark.4",
  messageUserSurface: "purple.1", messageUserText: "dark.4",
} as const satisfies Partial<Record<SemanticColorRole, PaletteColor>>;
export const alternateChatTheme = semanticTheme(alternateChatPalette);

export const controls = Object.fromEntries(
  Object.entries(appColorRoles).map(([role, { variable, color }]) => [
    role, `var(${variable}, ${resolveColor(color)})`,
  ]),
) as { readonly [Role in keyof typeof appColorRoles]: string };
