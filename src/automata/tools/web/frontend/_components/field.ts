import { Base } from "./base";
import type { ResolvedTheme } from "../_theme/index";
import { fieldStyle, fieldTheme } from "./field.style";
import { registerSharedComponent } from "./create";
import { booleanData, rejectChildren, stringData } from "./descriptor-data";

const textAttributes = ["label", "help", "error", "type", "name", "placeholder", "autocomplete", "value"] as const;
type FieldData = Partial<Record<typeof textAttributes[number], string>> & { disabled?: boolean; required?: boolean };

let nextFieldId = 0;

/** Labeled native input; input/change events bubble naturally from `control`. */
export class Field extends Base {
  static get create() { return createField; }
  static get observedAttributes(): string[] { return [...textAttributes, "disabled", "required"]; }
  readonly control = document.createElement("input");
  private readonly labelElement = document.createElement("label");
  private readonly helpElement = document.createElement("div");
  private readonly errorElement = document.createElement("div");
  private readonly fieldId = `ui-field-${++nextFieldId}`;

  connectedCallback(): void {
    if (this.control.parentNode !== this) {
      this.control.id = this.fieldId;
      this.labelElement.htmlFor = this.fieldId;
      this.helpElement.id = `${this.fieldId}-help`;
      this.helpElement.className = "field-help";
      this.errorElement.id = `${this.fieldId}-error`;
      this.errorElement.className = "field-error";
      this.append(this.labelElement, this.control, this.helpElement, this.errorElement);
    }
    this.sync();
    super.connectedCallback();
  }

  attributeChangedCallback(name: string, oldValue: string | null, newValue: string | null): void {
    if (name === "value" && oldValue !== newValue) this.control.value = newValue ?? "";
    this.sync();
  }
  get value(): string { return this.control.value; }
  set value(value: string) { this.control.value = value; }
  get disabled(): boolean { return this.hasAttribute("disabled"); }
  set disabled(value: boolean) { this.toggleAttribute("disabled", value); }
  override focus(options?: FocusOptions): void { this.control.focus(options); }

  private sync(): void {
    this.labelElement.textContent = this.getAttribute("label") ?? "";
    const help = this.getAttribute("help") ?? "";
    const error = this.getAttribute("error") ?? "";
    this.helpElement.textContent = help;
    this.errorElement.textContent = error;
    this.helpElement.hidden = !help;
    this.errorElement.hidden = !error;
    this.control.disabled = this.disabled;
    this.control.required = this.hasAttribute("required");
    for (const name of ["type", "name", "placeholder", "autocomplete"]) {
      const value = this.getAttribute(name);
      if (value === null) this.control.removeAttribute(name);
      else this.control.setAttribute(name, value);
    }
    const descriptions = [help && `${this.fieldId}-help`, error && `${this.fieldId}-error`].filter(Boolean);
    if (descriptions.length) this.control.setAttribute("aria-describedby", descriptions.join(" "));
    else this.control.removeAttribute("aria-describedby");
    if (error) this.control.setAttribute("aria-invalid", "true");
    else this.control.removeAttribute("aria-invalid");
  }
  protected themedStyle(theme: ResolvedTheme): string { return fieldTheme(theme); }
}
Field.css = fieldStyle;
Field.define("ui-field");
const createField = registerSharedComponent("ui-field", Field,
  (element, data: FieldData | undefined, children) => {
    rejectChildren("ui-field", children);
    for (const name of textAttributes) {
      const value = stringData(data, name);
      if (value !== undefined) element.setAttribute(name, value);
    }
    element.disabled = booleanData(data, "disabled") ?? false;
    element.toggleAttribute("required", booleanData(data, "required") ?? false);
  });
