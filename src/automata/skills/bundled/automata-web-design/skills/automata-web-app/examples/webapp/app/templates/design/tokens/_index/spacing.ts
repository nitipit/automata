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
      .space-stage { display: grid; gap: 1.25rem; padding: 1.25rem; border: 1px solid #deddda; border-radius: .75rem; background: #ffffff; }
      .space-demo { display: grid; gap: .5rem; justify-items: start; }
      .diagram-label { margin: 0; font-size: .85rem; font-weight: 600; }
      .padding-diagram, .gap-diagram { display: flex; background: #99c1f1; }
      .space-block { width: 4rem; height: 2rem; flex: 0 0 4rem; background: #1c71d8; }
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
        <div class="specimen-heading"><h2 id="spacing-heading">Spacing</h2><p>Light blue shows padding around a block or the gap between blocks. The dark blocks stay the same size.</p></div>
        <div id="spacing-tokens" class="spacing-grid"></div>
      </section>`;
    const grid = this.querySelector("#spacing-tokens")!;
    for (const [name, value] of Object.entries(spacing)) {
      const stage = element("div", "space-stage");
      const paddingDemo = element("div", "space-demo");
      const padding = element("div", "padding-diagram");
      padding.style.padding = value;
      padding.setAttribute("role", "img");
      padding.setAttribute("aria-label", `${name}: ${value} padding around one block`);
      padding.append(element("div", "space-block"));
      paddingDemo.append(element("p", "diagram-label", "Padding"), padding);

      const gapDemo = element("div", "space-demo");
      const gap = element("div", "gap-diagram");
      gap.style.gap = value;
      gap.setAttribute("role", "img");
      gap.setAttribute("aria-label", `${name}: ${value} gap between two blocks`);
      gap.append(element("div", "space-block"), element("div", "space-block"));
      gapDemo.append(element("p", "diagram-label", "Gap"), gap);

      stage.append(paddingDemo, gapDemo);
      const specimen = element("div");
      specimen.append(stage, materialLabel(name, value));
      grid.append(specimen);
    }
  }
}
