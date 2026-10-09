import { Base } from "@adaptive/base";
import { typography } from "@adaptive/tokens";
import { element } from "./dom.ts";

export class Typography extends Base {
  #mounted = false;

  static {
    this.css = `
      display: block;
      margin-bottom: 3rem;
      .specimen-heading { margin-bottom: 1.5rem; }
      .specimen-heading h2 { margin: 0 0 .35rem; font-size: 1.25rem; }
      .specimen-heading p { margin: 0; color: #5e5c64; font-size: .85rem; }
      .type-board { padding: 2rem; border: 1px solid #deddda; border-radius: .75rem; background: #ffffff; }
      .type-eyebrow { margin: 0 0 1rem; color: #5e5c64; font-size: .85rem; }
      .type-heading { margin: 0 0 1rem; font-size: 2rem; line-height: 1.25; letter-spacing: -.025em; }
      .type-body { max-width: 58ch; margin: 0 0 1.5rem; font-size: 1rem; }
      .type-label { display: block; font-size: .85rem; }
      .specimen-note { display: flex; flex-wrap: wrap; gap: .5rem 1.25rem; margin: .75rem 0 0; color: #5e5c64; font-size: .85rem; }
      @media (max-width: 700px) { .type-board { padding: 1.5rem; } }
    `;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.#mounted) return;
    this.#mounted = true;
    this.innerHTML = `
      <section aria-labelledby="type-heading">
        <div class="specimen-heading"><h2 id="type-heading">Typography</h2><p>One familiar family. A heading, a paragraph, and a quiet label.</p></div>
        <div id="typography-specimen" class="type-board">
          <p class="type-eyebrow">Field notes</p>
          <h3 class="type-heading">Make room for what matters.</h3>
          <p class="type-body">A clear heading gives us a place to begin. Comfortable lines carry the thought forward, while a smaller label leaves the next step easy to find. The same family holds the whole composition together.</p>
          <span class="type-label">Continue reading</span>
        </div>
        <p id="typography-values" class="specimen-note"></p>
      </section>`;
    const type = this.querySelector<HTMLElement>("#typography-specimen")!;
    type.style.fontFamily = typography.family;
    type.style.lineHeight = typography.lineHeight;
    for (const sample of type.querySelectorAll<HTMLElement>(".type-heading, .type-label")) {
      sample.style.fontWeight = typography.weightMedium;
    }
    const values = this.querySelector("#typography-values")!;
    for (const value of [typography.family, `Line height ${typography.lineHeight}`,
      `Weight ${typography.weightMedium}`, "Heading 2rem · Body 1rem · Label .85rem"]) {
      values.append(element("span", "", value));
    }
  }
}
