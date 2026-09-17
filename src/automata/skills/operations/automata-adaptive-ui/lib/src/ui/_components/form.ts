import { Base } from "./base.js";
import {
  type FormData,
  type FormField,
  validateFormData,
} from "./form.schema.js";

/** A semantic choice/text form that remains independent of channel transport. */
export class Form extends Base<FormData> {
  #form: HTMLFormElement | null = null;

  static {
    this.css = `
      display: block;

      form {
        display: grid;
        gap: 1rem;
      }

      fieldset {
        display: grid;
        gap: 0.75rem;
        min-inline-size: 0;
        margin: 0;
        padding: 0;
        border: 0;
      }

      legend {
        margin-block-end: 0.5rem;
        font-weight: 700;
      }

      label {
        display: grid;
        gap: 0.35rem;
      }

      input[type="text"] {
        min-height: 2.25rem;
        box-sizing: border-box;
        padding: 0.4rem 0.55rem;
        border: 1px solid #94a3b8;
        border-radius: 0.35rem;
        color: inherit;
        font: inherit;
      }

      .choice-group {
        display: grid;
        gap: 0.35rem;
      }

      .choice {
        display: flex;
        grid-template-columns: auto 1fr;
        align-items: center;
        gap: 0.45rem;
      }

      button {
        min-height: 2.5rem;
        border: 0;
        border-radius: 0.35rem;
        padding: 0.5rem 0.85rem;
        background: #2563eb;
        color: white;
        font: inherit;
        cursor: pointer;
      }
    `;
  }

  static override validateData(data: unknown): FormData {
    return validateFormData(data);
  }

  override connectedCallback(): void {
    super.connectedCallback();
    const data = this.dataFromAttributes();
    if (data) this.applyData(data);
  }

  /**
   * Rebuild the form from validated data. Existing input values are discarded;
   * callers needing draft preservation must capture and restore them separately.
   */
  override applyData(data: FormData): void {
    const form = this.ensureForm();
    form.replaceChildren();
    if (data.title) {
      const legend = document.createElement("legend");
      legend.textContent = data.title;
      form.append(legend);
    }
    const fieldset = document.createElement("fieldset");
    for (const field of data.fields) fieldset.append(this.renderField(field));
    form.append(fieldset);

    const submit = document.createElement("button");
    submit.type = "submit";
    submit.textContent = data.submitLabel;
    form.append(submit);
  }

  private ensureForm(): HTMLFormElement {
    if (!this.#form) {
      const existing = this.querySelector(":scope > form");
      this.#form = existing instanceof HTMLFormElement ? existing : document.createElement("form");
      if (!existing) this.append(this.#form);
      this.#form.addEventListener("submit", (event) => {
        event.preventDefault();
        const values: Record<string, string> = {};
        for (const element of this.#form?.elements ?? []) {
          if (!(element instanceof HTMLInputElement) || !element.name) continue;
          if (element.type === "radio" && !element.checked) continue;
          values[element.name] = element.value;
        }
        this.dispatchEvent(new CustomEvent("aui-form-submit", {
          bubbles: true,
          detail: { values },
        }));
      });
    }
    return this.#form;
  }

  private renderField(field: FormField): HTMLElement {
    if (field.kind === "choice") {
      const group = document.createElement("div");
      group.className = "choice-group";
      const label = document.createElement("span");
      label.textContent = field.label;
      group.append(label);
      for (const choice of field.choices) {
        const option = document.createElement("label");
        option.className = "choice";
        const input = document.createElement("input");
        input.type = "radio";
        input.name = field.name;
        input.value = choice.value;
        input.required = field.required;
        const text = document.createElement("span");
        text.textContent = choice.label;
        option.append(input, text);
        group.append(option);
      }
      return group;
    }

    const label = document.createElement("label");
    label.textContent = field.label;
    const input = document.createElement("input");
    input.type = "text";
    input.name = field.name;
    input.required = field.required;
    if (field.minLength !== undefined) input.minLength = field.minLength;
    if (field.maxLength !== undefined) input.maxLength = field.maxLength;
    label.append(input);
    return label;
  }

  private dataFromAttributes(): FormData | undefined {
    const fields = this.getAttribute("fields");
    if (!fields) return undefined;
    return validateFormData({
      title: this.getAttribute("title") ?? undefined,
      submitLabel: this.getAttribute("submit-label") ?? undefined,
      fields: JSON.parse(fields),
    });
  }
}
