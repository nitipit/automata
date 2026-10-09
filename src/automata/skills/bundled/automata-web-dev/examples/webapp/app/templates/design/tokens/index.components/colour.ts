import { Base } from "@adaptive/base";
import { paletteEntries, paletteName, type PaletteColor } from "@adaptive/tokens";
import { element } from "./dom.ts";

/** Compact palette families; primitive values stay in the library. */
export class Colour extends Base {
  #mounted = false;

  static {
    this.css = `
      display: block;
      margin-bottom: 3rem;
      .specimen-heading { margin-bottom: 1.5rem; }
      .specimen-heading h2 { margin: 0 0 .35rem; font-size: 1.25rem; }
      .palette-family { margin-bottom: .75rem; }
      .palette-family h3 { margin: 0 0 .65rem; font-size: 1rem; font-weight: 600; }
      .palette-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: .75rem; }
      .palette-chip { min-width: 0; }
      .swatch { height: 4rem; border: 1px solid #c0bfbc; border-radius: .75rem; }
      .swatch-label { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: .2rem .5rem; margin-top: .5rem; }
      .swatch-label span { font-size: .85rem; }
      .swatch-label code { color: #5e5c64; font-size: .75rem; overflow-wrap: anywhere; }
      @media (max-width: 480px) {
        .palette-grid { gap: .4rem; }
        .swatch { height: 3rem; border-radius: .5rem; }
        .swatch-label span { font-size: .75rem; }
        .swatch-label code { font-size: .7rem; }
      }
    `;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.#mounted) return;
    this.#mounted = true;
    this.innerHTML = `
      <section aria-labelledby="palette-heading">
        <div class="specimen-heading"><h2 id="palette-heading">Colour</h2></div>
        <div id="palette-tokens"></div>
      </section>`;
    const palette = this.querySelector("#palette-tokens")!;
    const families = new Map<string, HTMLElement>();
    for (const [key, value] of Object.entries(paletteEntries)) {
      const name = paletteName(key as PaletteColor);
      const family = name.split(" ")[0];
      if (!families.has(family)) {
        const section = element("section", "palette-family");
        const grid = element("div", "palette-grid");
        section.append(element("h3", "", family), grid);
        palette.append(section);
        families.set(family, grid);
      }
      const swatch = element("div", "swatch");
      swatch.style.backgroundColor = value;
      const label = element("div", "swatch-label");
      label.append(element("span", "", name), element("code", "", value));
      const chip = element("div", "palette-chip");
      chip.title = key;
      chip.append(swatch, label);
      families.get(family)!.append(chip);
    }
  }
}
