import { Base } from "@adaptive/base";
import { radius, space, tokens } from "../tokens/index.ts";

/** Local demo interaction. Page navigation resets it; no backend persistence. */
export class Counter extends Base {
  #count = 0;
  #handleClick = (event: Event) => {
    const target = event.target as Element;
    const button = target.closest("ui-button");
    if (!button || !this.contains(button)) return;
    this.#count = button.getAttribute("data-action") === "reset"
      ? 0
      : this.#count + 1;
    this.querySelector("output")!.textContent = String(this.#count);
  };

  static {
    this.css = `
      display: grid;
      gap: ${space.large};
      padding: clamp(1.5rem, 4vw, 2.5rem);
      background: ${tokens.surface};
      color: ${tokens.text};
      border: 1px solid ${tokens.border};
      border-radius: ${radius.panel};
      box-shadow: 0 18px 50px rgb(22 48 39 / 5%);
      .eyebrow { color: ${tokens.mutedText}; font-size: .75rem; letter-spacing: .12em; text-transform: uppercase; }
      output { display: block; font-size: clamp(4rem, 10vw, 6rem); font-weight: 650; line-height: 1; letter-spacing: -.07em; }
      .actions { display: flex; flex-wrap: wrap; gap: ${space.small}; }
      p { margin: 0; color: ${tokens.mutedText}; }
    `;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (!this.querySelector("output")) {
      this.innerHTML = `
        <div class="eyebrow">A little interaction</div>
        <output aria-label="Counter value" aria-live="polite">0</output>
        <p>One component. Shared tokens. Native browser behavior.</p>
        <div class="actions">
          <ui-button label="Add one" data-action="increment"></ui-button>
          <ui-button label="Reset" data-action="reset"></ui-button>
        </div>`;
    }
    this.addEventListener("click", this.#handleClick);
  }

  override disconnectedCallback(): void {
    this.removeEventListener("click", this.#handleClick);
    super.disconnectedCallback?.();
  }
}
