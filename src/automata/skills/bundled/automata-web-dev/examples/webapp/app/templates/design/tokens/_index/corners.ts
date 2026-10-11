import { Base } from "@adaptive/base";
import { paletteEntries, radius } from "@adaptive/tokens";
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
      .corners-grid { display: flex; flex-wrap: wrap; gap: 1.5rem; }
      .radius-example { width: 10rem; max-width: 100%; }
      .radius-surface { width: 100%; height: 6rem; }
      .circle-example { margin-top: 1.5rem; }
      .circle-note { margin: 0 0 .75rem; color: #5e5c64; font-size: .85rem; }
      .radius-circle { width: 6rem; height: 6rem; }
      .material-label { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; margin-top: .75rem; font-size: .85rem; }
      .material-label code { color: #5e5c64; font-size: .85rem; overflow-wrap: anywhere; }
    `;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.#mounted) return;
    this.#mounted = true;
    this.innerHTML = `
      <section aria-labelledby="radius-heading">
        <div class="specimen-heading"><h2 id="radius-heading">Corners</h2><p>Identical rectangles show each radius. Full creates a pill, or a circle on a square.</p></div>
        <div class="corners-grid" id="radius-tokens"></div>
      </section>`;
    const examples = this.querySelector("#radius-tokens")!;
    for (const [name, value] of Object.entries(radius)) {
      const surface = element("div", "radius-surface");
      surface.style.borderRadius = value;
      surface.style.backgroundColor = paletteEntries["blue.3"];
      surface.setAttribute("role", "img");
      surface.setAttribute("aria-label", `${name}: corner radius ${value}`);
      const specimen = element("div", "radius-example");
      specimen.append(surface, materialLabel(name, value));
      examples.append(specimen);
    }
    const circleExample = element("div", "radius-example circle-example");
    const circle = element("div", "radius-surface radius-circle");
    circle.style.borderRadius = radius.full;
    circle.style.backgroundColor = paletteEntries["blue.3"];
    circle.setAttribute("role", "img");
    circle.setAttribute("aria-label", `Full radius on a square produces a circle: ${radius.full}`);
    circleExample.append(element("p", "circle-note", "Full on a square"), circle,
      materialLabel("full", radius.full));
    this.querySelector("section")!.append(circleExample);
  }
}
