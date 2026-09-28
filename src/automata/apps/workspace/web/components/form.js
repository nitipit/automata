import { Base, Form } from "/lib/adaptive-ui.js";

Form.define("aui-form");

// This adapter owns submission semantics; the catalog owns rendering-data schema.
export class FormComponent extends Base {
  static { this.css = "display:block; min-width:0; .form-status {font-size:.85rem;}"; }
  static validateData(data) { return Form.validateData(data); }
  static validateValues(data, values, complete = true) {
    if (!values || typeof values !== "object" || Array.isArray(values)) throw new Error("Invalid form values");
    if (Object.keys(values).some(name => !data.fields.some(field => field.name === name))) {
      throw new Error("Unknown form field");
    }
    const result = Object.create(null);
    for (const field of data.fields) {
      const value = values[field.name] ?? "";
      if (typeof value !== "string" || value.length > 6000) throw new Error("Invalid field value");
      if (complete && field.required && !value.trim()) throw new Error(`${field.label} is required`);
      if (field.kind === "choice" && value && !field.choices.some(choice => choice.value === value)) {
        throw new Error("Choice is no longer offered");
      }
      if (complete && field.kind === "text" && value &&
          (value.length < (field.minLength ?? 0) || value.length > (field.maxLength ?? 6000))) {
        throw new Error(`${field.label} has invalid length`);
      }
      result[field.name] = value;
    }
    return result;
  }
  applyData(data, interaction = {}) {
    const changed = JSON.stringify(this.data) !== JSON.stringify(data);
    this.data = data;
    this.interaction = interaction;
    if (!this.form) {
      this.form = document.createElement("aui-form");
      this.fieldset = document.createElement("fieldset");
      this.fieldset.style.cssText = "border:0; padding:0; margin:0; min-width:0";
      this.fieldset.append(this.form);
      this.status = document.createElement("p");
      this.status.className = "form-status";
      this.status.setAttribute("role", "status");
      this.append(this.fieldset, this.status);
      this.form.addEventListener("input", () => this.emit("component-draft", this.readValues()));
      this.form.addEventListener("aui-form-submit", event => {
        event.stopPropagation();
        if (this.interaction.status && this.interaction.status !== "draft") return;
        try {
          const values = FormComponent.validateValues(this.data, event.detail.values);
          this.emit("component-submit", values);
        } catch (error) { this.status.textContent = error.message; }
      });
    }
    this.fieldset.disabled = Boolean(interaction.status && interaction.status !== "draft");
    if (changed) this.form.applyData(data);
    const values = FormComponent.validateValues(data, interaction.values ?? {}, false);
    for (const input of this.form.querySelectorAll("input")) {
      if (input.type === "text") input.value = values[input.name] ?? "";
      else input.checked = values[input.name] === input.value;
    }
    const locked = interaction.status && interaction.status !== "draft";
    for (const input of this.form.querySelectorAll("input,button")) input.disabled = Boolean(locked);
    this.status.textContent = locked ? `${interaction.status} · ${interaction.detail ?? "No automatic resend"}` : "";
  }
  readValues() {
    const values = Object.create(null);
    for (const input of this.form.querySelectorAll("input")) {
      if (input.type === "text" || input.checked) values[input.name] = input.value;
    }
    return values;
  }
  emit(type, values) {
    this.dispatchEvent(new CustomEvent(type, { bubbles: true, composed: true, detail: { values } }));
  }
}
FormComponent.define("wsp-form");
