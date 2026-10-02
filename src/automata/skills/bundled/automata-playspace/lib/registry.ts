import { textDefinition, jsonDefinition } from "./content.js";
import { formDefinition } from "./form.js";

/** Trusted imported definitions only. JSON/cache may select names, never define code. */
export const builtins = Object.freeze({
  "ps-text": textDefinition,
  "ps-json": jsonDefinition,
  "ps-form": formDefinition,
});
