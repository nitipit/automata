// @ts-types="./adaptive-ui.d.ts"
import { Button, Form } from "./adaptive-ui.js";
import { Chat } from "./chat.js";
import { TextComponent, JSONComponent } from "./content.js";
import { FormComponent } from "./form.js";

/** Register once per page realm; catalog tags retain their own names/ownership. */
export function registerPlayspace() {
  for (const [tag, Component] of [["aui-button", Button], ["aui-form", Form],
    ["ps-text", TextComponent], ["ps-json", JSONComponent], ["ps-form", FormComponent], ["ps-chat", Chat]] as const) {
    const existing = customElements.get(tag);
    if (existing && existing !== Component) throw new Error(`Conflicting trusted definition for ${tag}`);
    if (!existing) Component.define(tag);
  }
}
export { Chat };
export { builtins } from "./registry.js";
export { component, text, json, event, ContractError, validateComponent, validateEvent } from "./contracts.js";
export { formContracts } from "./form.schema.js";
export { validateChatSnapshot } from "./chat-state.js";
export type { ComponentPayload, EventPayload, Payload, Registry, ComponentDefinition, ChatSnapshot, FormProps, FormState, Submission } from "./types.js";
