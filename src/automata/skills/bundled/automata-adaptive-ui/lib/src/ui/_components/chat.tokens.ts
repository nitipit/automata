import { componentColorValues, type ComponentColorRoles } from "../tokens.js";

/** Presentation roles only: no composer, connection or pending state. */
export const chatColorRoles = {
  border: "border",
  surface: "surface",
  text: "text",
  shadow: "shadow",
  status: "status",
  mutedText: "mutedText",
  messageAgentSurface: "messageAgentSurface",
  messageAgentText: "messageAgentText",
  messageUserSurface: "messageUserSurface",
  messageUserText: "messageUserText",
  focus: "focus",
} as const satisfies ComponentColorRoles;

export const chatTokens = componentColorValues(chatColorRoles);
