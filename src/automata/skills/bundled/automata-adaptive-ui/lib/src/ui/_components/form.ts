import { Base } from "./base.js";
import { paletteEntries as colors } from "../_tokens/color.js";
import { radius } from "../_tokens/radius.js";
import { spacing } from "../_tokens/spacing.js";

/** Native fields/constraints stay HTML. Submit emits values without navigation or reset. */
export class Form extends Base {
  #form: HTMLFormElement | null = null;

  static {
    this.css = `
      display: block;
      form { display: grid; gap: ${spacing.md}; }
      label { display: grid; gap: ${spacing.sm}; }
      input:not([type="checkbox"]):not([type="radio"]), select, textarea {
        box-sizing: border-box;
        width: 100%;
        padding: ${spacing.sm};
        border: 1px solid ${colors["dark.1"]};
        border-radius: ${radius.md};
        color: ${colors["dark.4"]};
        background: ${colors["light.1"]};
        font: inherit;
      }
      input:focus-visible, select:focus-visible, textarea:focus-visible {
        outline: 2px solid ${colors["blue.4"]}; outline-offset: 2px;
      }
    `;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.#form) return;
    this.#form = this.querySelector<HTMLFormElement>(":scope > form");
    if (!this.#form) {
      this.#form = document.createElement("form");
      this.#form.append(...Array.from(this.childNodes));
      this.append(this.#form);
    }
    const form = this.#form;
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const submitter = (event as SubmitEvent).submitter;
      const values = Object.fromEntries(new globalThis.FormData(form, submitter));
      this.dispatchEvent(new CustomEvent("aui-form-submit", {
        bubbles: true,
        composed: true,
        detail: { values },
      }));
    });
  }
}
