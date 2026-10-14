import { Base } from "@adaptive/base";
import { typography } from "@adaptive/tokens";

export class Scale extends Base {
  #mounted = false;

  static {
    this.css = `
      display: block;
      margin-bottom: 3rem;
      .scale-heading { margin: 0 0 .5rem; }
      .scale-note { margin: 0 0 1.5rem; color: #5e5c64; font-size: ${typography.labelSize}; }
      .scale-board { padding: 2rem; border: 1px solid #deddda; border-radius: .75rem; background: #ffffff; }
      .type-row { padding: 1rem 0; border-bottom: 1px solid #deddda; }
      .type-row:first-child { padding-top: 0; }
      .type-row:last-child { padding-bottom: 0; border-bottom: 0; }
      .sample-caption { margin: 0 0 .5rem; color: #5e5c64; font-size: ${typography.labelSize}; }
      .heading-sample { margin: 0; }
      .body-sample { margin: 0; font-size: ${typography.bodySize}; }
      .label-sample { margin: 0; font-size: ${typography.labelSize}; }
      @media (max-width: 700px) { .scale-board { padding: 1.5rem; } }
    `;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.#mounted) return;
    this.#mounted = true;
    this.innerHTML = `
      <section aria-labelledby="scale-heading">
        <h2 id="scale-heading" class="scale-heading">Type scale</h2>
        <p class="scale-note">${typography.family} · Fluid root 15–17px across 600–1200px · Headings ${typography.weightMedium}/${typography.headingLineHeight} · Body ${typography.weightRegular}/${typography.lineHeight}</p>
        <div class="scale-board">
          <div class="type-row"><p class="sample-caption">h1 · ${typography.h1Size}</p><h1 class="heading-sample">Make room for what matters.</h1></div>
          <div class="type-row"><p class="sample-caption">h2 · ${typography.h2Size}</p><h2 class="heading-sample">Make room for what matters.</h2></div>
          <div class="type-row"><p class="sample-caption">h3 · ${typography.h3Size}</p><h3 class="heading-sample">Make room for what matters.</h3></div>
          <div class="type-row"><p class="sample-caption">h4 · ${typography.h4Size}</p><h4 class="heading-sample">Make room for what matters.</h4></div>
          <div class="type-row"><p class="sample-caption">h5 · ${typography.h5Size}</p><h5 class="heading-sample">Make room for what matters.</h5></div>
          <div class="type-row"><p class="sample-caption">h6 · ${typography.h6Size}</p><h6 class="heading-sample">Make room for what matters.</h6></div>
          <div class="type-row"><p class="sample-caption">Body · ${typography.bodySize}</p><p class="body-sample">Comfortable lines carry the thought forward.</p></div>
          <div class="type-row"><p class="sample-caption">Label · ${typography.labelSize}</p><p class="label-sample">A quiet detail, sized from the root—not its parent.</p></div>
        </div>
      </section>`;
  }
}
