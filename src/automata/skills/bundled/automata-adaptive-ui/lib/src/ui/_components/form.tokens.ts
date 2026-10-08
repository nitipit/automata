import { componentColorValues, type ComponentColorRoles } from "../tokens.js";

/** Color roles of the native controls composed by Form. */
export const formColorRoles = {
  border: "border",
  focus: "focus",
  action: "action",
  actionHover: "actionHover",
  actionText: "actionText",
} as const satisfies ComponentColorRoles;

export const formTokens = componentColorValues(formColorRoles);
