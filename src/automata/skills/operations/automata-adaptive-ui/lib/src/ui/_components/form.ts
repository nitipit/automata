import { Base } from "./base.js";
import { tokens } from "../tokens.js";
import {
  type FormData,
  type FormField,
  validateFormData,
} from "./form.schema.js";

/** A semantic choice/text form that remains independent of channel transport. */
export class Form extends Base<FormData> {
  #form: HTMLFormElement | null = null;
  #applyingData = false;

  static get observedAttributes(): string[] {
    return ["title", "submit-label", "fields"];
  }

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
        border: 1px solid ${tokens.border};
        border-radius: 0.35rem;
        color: inherit;
        font: inherit;
      }

      input:focus-visible, button:focus-visible {
        outline: 2px solid ${tokens.focus};
        outline-offset: 2px;
      }

      .choice-group {
        display: grid;
        gap: 0.35rem;
      }

      .choice {
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 0.45rem;
      }

      button {
        min-height: 2.5rem;
        border: 0;
        border-radius: 0.35rem;
        padding: 0.5rem 0.85rem;
        background: ${tokens.action};
        color: ${tokens.actionText};
        font: inherit;
        cursor: pointer;
      }

      button:hover { background: ${tokens.actionHover}; }
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

  attributeChangedCallback(_name: string, oldValue: string | null, newValue: string | null): void {
    if (oldValue !== newValue && this.isConnected && !this.#applyingData) {
      const data = this.dataFromAttributes();
      if (data) this.applyData(data);
    }
  }

  /**
   * Preserve text drafts by name/kind and a radio selection only while its value
   * remains among the new choices. Removed/changed-kind fields lose their draft.
   * Native form.reset() explicitly clears drafts to the current blank defaults.
   * Call validateData() before direct applyData() calls.
   */
  override applyData(data: FormData): void {
    const form = this.ensureForm();
    const previous = new Map<string, { kind: string; value: string }>();
    for (const input of form.querySelectorAll("input")) {
      if (input.type === "text") previous.set(input.name, { kind: "text", value: input.value });
      if (input.type === "radio" && input.checked) {
        previous.set(input.name, { kind: "choice", value: input.value });
      }
    }
    const focused = form.contains(document.activeElement) ? document.activeElement as HTMLElement : null;
    const focusedInput = focused instanceof HTMLInputElement ? focused : null;
    const focusName = focusedInput?.name;
    const focusValue = focusedInput?.value;
    const selection = focusedInput?.type === "text"
      ? [focusedInput.selectionStart, focusedInput.selectionEnd] : null;

    this.#applyingData = true;
    try {
      this.setAttributeIfChanged("title", data.title ?? "");
      this.setAttributeIfChanged("submit-label", data.submitLabel);
      this.setAttributeIfChanged("fields", JSON.stringify(data.fields));
    } finally {
      this.#applyingData = false;
    }
    form.replaceChildren();
    if (data.title) {
      const heading = document.createElement("h2");
      heading.textContent = data.title;
      form.append(heading);
    }
    const fieldset = document.createElement("fieldset");
    for (const field of data.fields) {
      const element = this.renderField(field);
      const draft = previous.get(field.name);
      if (draft?.kind === field.kind) {
        if (field.kind === "text") {
          (element.querySelector("input") as HTMLInputElement).value = draft.value;
        } else {
          const option = Array.from(element.querySelectorAll("input"))
            .find((input) => input.value === draft.value);
          if (option) option.checked = true;
        }
      }
      fieldset.append(element);
    }
    form.append(fieldset);

    const submit = document.createElement("button");
    submit.type = "submit";
    submit.textContent = data.submitLabel;
    form.append(submit);
    if (focusedInput && focusName) {
      const target = Array.from(form.querySelectorAll("input"))
        .find((input) => input.name === focusName && input.type === focusedInput.type &&
          (input.type !== "radio" || input.value === focusValue));
      if (target) {
        target.focus();
        if (selection && selection[0] !== null && selection[1] !== null) {
          target.setSelectionRange(selection[0], selection[1]);
        }
      }
    } else if (focused?.tagName === "BUTTON") submit.focus();
  }

  private setAttributeIfChanged(name: string, value: string): void {
    if (this.getAttribute(name) !== value) this.setAttribute(name, value);
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
      const group = document.createElement("fieldset");
      group.className = "choice-group";
      const legend = document.createElement("legend");
      legend.textContent = field.label;
      group.append(legend);
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
