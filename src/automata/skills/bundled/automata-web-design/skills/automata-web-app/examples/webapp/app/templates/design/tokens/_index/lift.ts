import { Base } from "@adaptive/base";
import { lift, paletteEntries, radius } from "@adaptive/tokens";
import { element } from "./dom.ts";

export class Lift extends Base {
  #mounted = false;

  static {
    this.css = `
      display: block;
      margin-bottom: 3rem;
      .specimen-heading { margin-bottom: 1.5rem; }
      .specimen-heading h2 { margin: 0 0 .35rem; font-size: 1.25rem; }
      .specimen-heading p { margin: 0; color: #5e5c64; font-size: .85rem; }
      .lift-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 1rem; }
      .lift-stage { min-height: 8rem; display: grid; place-items: center; padding: 1.5rem .5rem; background: #f6f5f4; }
      .lift-surface { width: 80%; min-height: 4rem; display: grid; place-items: center; border: 1px solid #deddda; font-size: .85rem; }
      .lift-shape { display: block; width: 4rem; height: 4rem; overflow: visible; }
      .lift-label { margin: .5rem 0 0; text-align: center; font-size: .85rem; }
      .lift-kind { margin: 1.5rem 0 .5rem; font-size: .85rem; font-weight: 600; }
      @media (max-width: 1100px) { .lift-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
      @media (max-width: 700px) { .lift-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    `;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.#mounted) return;
    this.#mounted = true;
    this.innerHTML = `
      <section aria-labelledby="lift-heading">
        <div class="specimen-heading"><h2 id="lift-heading">Lift</h2><p>Six levels of visual depth. 0 stays flat; 1–5 move the visible shape away from its backdrop.</p></div>
        <h3 class="lift-kind">Surfaces</h3>
        <div id="lift-surfaces" class="lift-grid"></div>
        <h3 class="lift-kind">Shapes</h3>
        <div id="lift-shapes" class="lift-grid"></div>
      </section>`;
    for (const [level, value] of Object.entries(lift)) {
      const surface = element("div", "lift-surface", "Surface");
      surface.style.borderRadius = radius.md;
      surface.style.backgroundColor = paletteEntries["light.1"];
      surface.style.filter = value;
      const shape = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      shape.setAttribute("viewBox", "0 0 100 100");
      shape.setAttribute("aria-hidden", "true");
      shape.classList.add("lift-shape");
      shape.style.filter = value;
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", "M50 4 62 34 95 36 70 58 78 91 50 73 22 91 30 58 5 36 38 34Z");
      path.setAttribute("fill", paletteEntries["blue.2"]);
      shape.append(path);
      for (const [target, sample] of [["#lift-surfaces", surface], ["#lift-shapes", shape]] as const) {
        const stage = element("div", "lift-stage");
        stage.append(sample);
        const specimen = element("div", "lift-specimen");
        specimen.append(stage, element("p", "lift-label", `Lift ${level}`));
        this.querySelector(target)!.append(specimen);
      }
    }
  }
}
