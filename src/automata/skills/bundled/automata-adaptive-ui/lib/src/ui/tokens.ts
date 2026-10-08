import { type ColorReference, resolveColor } from "./_tokens/primitives/effects.js";
export { palette, paletteEntries, paletteName, paletteSource,
  type PaletteColor } from "./_tokens/primitives/color.js";
export { colorEffects, resolveColor, colorReferenceLabel,
  type ColorReference, type EffectReference } from "./_tokens/primitives/effects.js";

export type SemanticColorDefinition = {
  readonly variable: `--aui-${string}`;
  readonly color: ColorReference;
  readonly description: string;
};

/** UI intent selects official entries or explicitly separate derived effects. */
export const semanticColorRoles = {
  surface: { variable: "--aui-surface", color: "light.1", description: "Content and input surface" },
  text: { variable: "--aui-text", color: "dark.4", description: "Main content text" },
  mutedText: { variable: "--aui-muted-text", color: "dark.2", description: "Secondary labels and explanatory text" },
  border: { variable: "--aui-border", color: "dark.1", description: "Surface and control boundaries" },
  action: { variable: "--aui-action", color: "blue.4", description: "Suggested action background" },
  actionHover: { variable: "--aui-action-hover", color: "blue.5", description: "Hovered suggested action" },
  actionText: { variable: "--aui-action-text", color: "light.1", description: "Text on suggested and destructive actions" },
  danger: { variable: "--aui-danger", color: "red.4", description: "Destructive action background" },
  focus: { variable: "--aui-focus", color: "blue.4", description: "Keyboard focus indicator" },
  status: { variable: "--aui-status", color: "dark.2", description: "Status and empty-state text" },
  messageAgentSurface: { variable: "--aui-message-agent-surface", color: "light.2", description: "Agent message surface" },
  messageAgentText: { variable: "--aui-message-agent-text", color: "dark.4", description: "Agent message text" },
  messageUserSurface: { variable: "--aui-message-user-surface", color: "blue.1", description: "User message surface" },
  messageUserText: { variable: "--aui-message-user-text", color: "dark.4", description: "User message text" },
  shadow: { variable: "--aui-shadow", color: "effect.shadow", description: "Raised surface shadow" },
  clear: { variable: "--aui-clear", color: "effect.clear", description: "Unfilled surface" },
} as const satisfies Record<string, SemanticColorDefinition>;

export type SemanticColorRole = keyof typeof semanticColorRoles;
export type ComponentColorRoles = Readonly<Record<string, SemanticColorRole>>;

/** Existing --aui-* override names remain; approved palette defaults have changed. */
export const tokens = Object.fromEntries(
  Object.entries(semanticColorRoles).map(([role, definition]) => [
    role, `var(${definition.variable}, ${resolveColor(definition.color)})`,
  ]),
) as { readonly [Role in SemanticColorRole]: string };

export function componentColorValues<const Roles extends ComponentColorRoles>(roles: Roles) {
  return Object.fromEntries(
    Object.entries(roles).map(([role, semantic]) => [role, tokens[semantic]]),
  ) as { readonly [Role in keyof Roles]: (typeof tokens)[Roles[Role]] };
}
