import { Base } from "./base";
import { registerSharedComponent } from "./create";
import { booleanData, ownValue, rejectChildren, stringData } from "./descriptor-data";
import type { ResolvedTheme } from "../_theme/index";
import { selectStyle, selectTheme } from "./select.style";

export type SelectOption = { readonly value: string; readonly label: string; readonly disabled?: boolean };
type SelectData = {
  label?: string;
  name?: string;
  options?: readonly SelectOption[];
  value?: string;
  disabled?: boolean;
  required?: boolean;
};

let nextSelectId = 0;

/** Labeled native single select; `change` bubbles from `control`. */
export class Select extends Base {
  static get create() { return createSelect; }
  static get observedAttributes(): string[] { return ["label", "name", "disabled", "required"]; }
  readonly control = document.createElement("select");
  private readonly labelElement = document.createElement("label");

  override connectedCallback(): void {
    const root = this.getRootNode() as Document | ShadowRoot;
    if (!this.control.id || root.getElementById(this.control.id) !== this.control) {
      let id: string;
      do { id = `ui-select-${++nextSelectId}`; } while (root.getElementById(id));
      this.control.id = id;
    }
    this.labelElement.htmlFor = this.control.id;
    if (this.control.parentNode !== this) this.append(this.labelElement, this.control);
    super.connectedCallback();
  }
  attributeChangedCallback(name: string, _oldValue: string | null, value: string | null): void {
    switch (name) {
      case "label": this.labelElement.textContent = value ?? ""; break;
      case "name":
        if (value === null) this.control.removeAttribute("name");
        else this.control.name = value;
        break;
      case "disabled": this.control.disabled = value !== null; break;
      case "required": this.control.required = value !== null; break;
    }
  }
  get value(): string { return this.control.value; }
  set value(value: string) { this.control.value = value; }
  get disabled(): boolean { return this.hasAttribute("disabled"); }
  set disabled(value: boolean) { this.toggleAttribute("disabled", value); }
  override focus(options?: FocusOptions): void { this.control.focus(options); }

  /** Replace the option list and its default without dispatching a change. */
  setOptions(options: readonly SelectOption[], value?: string): void {
    const selected = value === undefined ? -1 : options.findIndex(option => option.value === value);
    this.control.replaceChildren(...options.map(({ label, value, disabled }, index) => {
      const option = new Option(label, value, index === selected);
      option.disabled = disabled ?? false;
      return option;
    }));
    if (value !== undefined) this.control.selectedIndex = selected;
  }
  protected themedStyle(theme: ResolvedTheme): string { return selectTheme(theme); }
}
Select.css = selectStyle;
Select.define("ui-select");

const createSelect = registerSharedComponent("ui-select", Select,
  (element, data: SelectData | undefined, children) => {
    rejectChildren("ui-select", children);
    for (const name of ["label", "name"]) {
      const value = stringData(data, name);
      if (value !== undefined) element.setAttribute(name, value);
    }
    const rows = ownValue(data, "options");
    const options: SelectOption[] = [];
    if (Array.isArray(rows)) {
      for (let index = 0; index < rows.length; index++) {
        const row = ownValue(rows, String(index));
        const value = stringData(row, "value");
        const label = stringData(row, "label");
        if (value !== undefined && label !== undefined) options.push({ value, label, disabled: booleanData(row, "disabled") ?? false });
      }
    }
    element.setOptions(options, stringData(data, "value"));
    element.disabled = booleanData(data, "disabled") ?? false;
    element.toggleAttribute("required", booleanData(data, "required") ?? false);
  });
