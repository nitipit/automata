import { Base } from "@adaptive/base";
import { paletteEntries, radius, spacing } from "@adaptive/tokens";
import { element, materialLabel } from "./dom.ts";

export class Corners extends Base {
  #mounted = false;

  static {
    this.css = `
      display: block;
      margin-bottom: 3rem;
      .specimen-heading { margin-bottom: 1.5rem; }
      .specimen-heading h2 { margin: 0 0 .35rem; font-size: 1.25rem; }
      .specimen-heading p { margin: 0; color: #5e5c64; font-size: .85rem; }
      .radius-surface { min-height: 10rem; display: grid; align-content: end; gap: .5rem; max-width: 28rem; border: 1px solid #62a0ea; }
      .radius-surface strong { font-size: 1.25rem; font-weight: 600; }
      .radius-surface p { margin: 0; font-size: .85rem; }
      .material-label { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; margin-top: .75rem; font-size: .85rem; }
      .material-label code { color: #5e5c64; font-size: .85rem; overflow-wrap: anywhere; }
      .radius-caption { max-width: 28rem; }
    `;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.#mounted) return;
    this.#mounted = true;
    this.innerHTML = `
      <section aria-labelledby="radius-heading">
        <div class="specimen-heading"><h2 id="radius-heading">Corners</h2><p>A radius on a real surface, rather than an isolated shape.</p></div>
        <div id="radius-tokens"></div>
      </section>`;
    const examples = this.querySelector("#radius-tokens")!;
    for (const [name, value] of Object.entries(radius)) {
      const surface = element("div", "radius-surface");
      surface.style.borderRadius = value;
      surface.style.padding = spacing.lg;
      surface.style.backgroundColor = paletteEntries["blue.1"];
      surface.append(element("strong", "", "Rounded edges"),
        element("p", "", "A clear boundary, with a little softness."));
      const label = materialLabel(name, value);
      label.classList.add("radius-caption");
      examples.append(surface, label);
    }
  }
}
