import { Base } from "@adaptive/base";
import { paletteEntries, radius, resolveColor } from "@adaptive/tokens";
import { element, materialLabel } from "./dom.ts";

export class Transparency extends Base {
  #mounted = false;

  static {
    this.css = `
      display: block;
      margin-bottom: 3rem;
      .specimen-heading { margin-bottom: 1.5rem; }
      .specimen-heading h2 { margin: 0 0 .35rem; font-size: 1.25rem; }
      .specimen-heading p { margin: 0; color: #5e5c64; font-size: .85rem; }
      .surface-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1.5rem; align-items: start; }
      .effect-stage { min-height: 11rem; display: flex; align-items: center; justify-content: center; border-radius: .75rem; }
      .effect-surface { width: 65%; min-height: 6rem; display: grid; place-items: center; border: 1px solid #deddda; font-size: .85rem; }
      .effect-stage.is-clear { background-size: 1rem 1rem; }
      .effect-stage.is-clear .effect-surface { border-color: #77767b; }
      .material-label { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; margin-top: .75rem; font-size: .85rem; }
      .material-label code { color: #5e5c64; font-size: .85rem; overflow-wrap: anywhere; }
      @media (max-width: 700px) {
        .surface-grid { grid-template-columns: 1fr; }
        .effect-stage, .material-label { max-width: 28rem; }
      }
    `;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.#mounted) return;
    this.#mounted = true;
    this.innerHTML = `
      <section aria-labelledby="effects-heading">
        <div class="specimen-heading"><h2 id="effects-heading">Transparency</h2><p>Let the backdrop show through a surface.</p></div>
        <div id="effect-tokens" class="surface-grid"></div>
      </section>`;
    const stage = element("div", "effect-stage is-clear");
    const checker = paletteEntries["light.3"];
    stage.style.backgroundColor = paletteEntries["light.1"];
    stage.style.backgroundImage = `linear-gradient(45deg, ${checker} 25%, transparent 25%, transparent 75%, ${checker} 75%), linear-gradient(45deg, ${checker} 25%, transparent 25%, transparent 75%, ${checker} 75%)`;
    stage.style.backgroundPosition = "0 0, .5rem .5rem";
    const surface = element("div", "effect-surface", "Let the backdrop through");
    surface.style.borderRadius = radius.md;
    surface.style.backgroundColor = resolveColor("effect.clear");
    stage.append(surface);
    const specimen = element("div");
    specimen.append(stage, materialLabel("clear", "transparent"));
    this.querySelector("#effect-tokens")!.append(specimen);
  }
}
