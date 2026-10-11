import { Base } from "@adaptive/base";
import { spacing } from "@adaptive/tokens";
import { element, materialLabel } from "./dom.ts";

export class Spacing extends Base {
  #mounted = false;

  static {
    this.css = `
      display: block;
      margin-bottom: 3rem;
      .specimen-heading { margin-bottom: 1.5rem; }
      .specimen-heading h2 { margin: 0 0 .35rem; font-size: 1.25rem; }
      .specimen-heading p { margin: 0; color: #5e5c64; font-size: .85rem; }
      .spacing-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1.5rem; align-items: start; }
      .space-stage { border: 1px solid #deddda; border-radius: .75rem; background: #ffffff; }
      .space-stack { display: grid; }
      .space-stack p { margin: 0; }
      .space-title { font-size: 1rem; font-weight: 600; }
      .space-body { font-size: .85rem; }
      .space-caption { color: #5e5c64; font-size: .85rem; }
      .material-label { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; margin-top: .75rem; font-size: .85rem; }
      .material-label code { color: #5e5c64; font-size: .85rem; overflow-wrap: anywhere; }
      @media (max-width: 700px) {
        .spacing-grid { grid-template-columns: 1fr; }
        .space-stage, .material-label { max-width: 28rem; }
      }
    `;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.#mounted) return;
    this.#mounted = true;
    this.innerHTML = `
      <section aria-labelledby="spacing-heading">
        <div class="specimen-heading"><h2 id="spacing-heading">Spacing</h2><p>The same small composition, with each primitive setting its padding and rhythm.</p></div>
        <div id="spacing-tokens" class="spacing-grid"></div>
      </section>`;
    const grid = this.querySelector("#spacing-tokens")!;
    for (const [name, value] of Object.entries(spacing)) {
      const stage = element("div", "space-stage");
      stage.style.padding = value;
      const stack = element("div", "space-stack");
      stack.style.gap = value;
      stack.append(element("p", "space-title", "Daily notes"),
        element("p", "space-body", "A little room between the essentials."),
        element("p", "space-caption", "Today · Three entries"));
      stage.append(stack);
      const specimen = element("div");
      specimen.append(stage, materialLabel(name, value));
      grid.append(specimen);
    }
  }
}
