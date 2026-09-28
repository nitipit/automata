import { TextComponent } from "./text.js";
import { FormComponent } from "./form.js";

/** Saved user interaction, including its exact component definition and values. */
export class FormResponseComponent extends TextComponent {
  static validateData(data) {
    const id = /^[a-zA-Z0-9_-]{1,100}$/;
    if (!data || !id.test(data.messageId) || !id.test(data.componentId)) throw new Error("Invalid form reference");
    const definition = FormComponent.validateData(data.definition);
    const values = FormComponent.validateValues(definition, data.values);
    return { messageId: data.messageId, componentId: data.componentId, definition, values };
  }
  applyData(data) {
    this.textContent = "Submitted form\n" + Object.entries(data.values).map(([key, value]) => `${key}: ${value}`).join("\n");
  }
}
FormResponseComponent.define("wsp-form-response");
