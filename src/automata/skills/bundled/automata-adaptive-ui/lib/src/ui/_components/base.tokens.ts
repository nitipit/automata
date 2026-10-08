import { componentColorValues, type ComponentColorRoles } from "../tokens.js";

/** Shared foreground baseline; composed controls may select their own roles. */
export const baseColorRoles = {
  foreground: "text",
} as const satisfies ComponentColorRoles;

export const baseTokens = componentColorValues(baseColorRoles);
