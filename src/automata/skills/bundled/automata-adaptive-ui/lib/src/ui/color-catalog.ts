import { baseColorRoles } from "./_components/base.tokens.js";
import { buttonColorRoles } from "./_components/button.tokens.js";
import { cardColorRoles } from "./_components/card.tokens.js";
import { formColorRoles } from "./_components/form.tokens.js";
import { chatColorRoles } from "./_components/chat.tokens.js";
import { type ComponentColorRoles } from "./tokens.js";

/** Public color metadata without custom-element/DOM or framework dependencies. */
export { palette, paletteEntries, paletteSource, paletteName, type PaletteColor,
  colorEffects, resolveColor, colorReferenceLabel, type ColorReference, type EffectReference,
  semanticColorRoles,
  type SemanticColorRole, type SemanticColorDefinition, tokens,
  type ComponentColorRoles } from "./tokens.js";

/** Canonical component catalog; documentation consumes the owning definitions. */
export const componentColorRoles = {
  Base: baseColorRoles,
  Button: buttonColorRoles,
  Card: cardColorRoles,
  Form: formColorRoles,
  Chat: chatColorRoles,
} as const satisfies Record<string, ComponentColorRoles>;
