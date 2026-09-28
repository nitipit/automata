import { TextComponent } from "./text.js";
import { FormComponent } from "./form.js";
import { FormResponseComponent } from "./form-response.js";

const registry = new Map([
  ["text:1", { tag: "wsp-text", component: TextComponent }],
  ["form:1", { tag: "wsp-form", component: FormComponent }],
  ["form-response:1", { tag: "wsp-form-response", component: FormResponseComponent }],
]);
const identifier = /^[a-zA-Z0-9_-]{1,100}$/;
export function validateContent(content) {
  if (!Array.isArray(content) || !content.length || content.length > 16) throw new Error("Expected 1–16 components");
  if (new TextEncoder().encode(JSON.stringify(content)).length > 24000) throw new Error("Content too large");
  const ids = new Set();
  return content.map(description => {
    if (!description || typeof description.id !== "string" || !identifier.test(description.id) || ids.has(description.id)) throw new Error("Invalid component identity");
    ids.add(description.id);
    const entry = registry.get(`${description.type}:${description.version}`);
    if (!entry || description.version !== 1) throw new Error("Unsupported component type/version");
    return { id: description.id, type: description.type, version: 1, data: entry.component.validateData(description.data) };
  });
}
export function createComponent(description, interaction) {
  const validated = validateContent([description])[0];
  const entry = registry.get(`${validated.type}:${validated.version}`);
  const element = document.createElement(entry.tag);
  element.applyData(validated.data, interaction);
  return element;
}
