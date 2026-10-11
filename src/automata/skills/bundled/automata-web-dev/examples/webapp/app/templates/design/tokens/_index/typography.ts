import { Base } from "@adaptive/base";
import { typography } from "@adaptive/tokens";

/** A compact primitive reference; full specimens belong to the Typography page. */
export class Typography extends Base {
  #mounted = false;

  static {
    this.css = `
      display: block;
      margin-bottom: 3rem;
      h2 { margin: 0 0 .75rem; font-size: 1.25rem; }
      .type-values { display: flex; flex-wrap: wrap; gap: .5rem 1.25rem; margin-bottom: .75rem; }
      .type-values span { color: #5e5c64; font-size: .85rem; }
      dl { margin: 0 0 1rem; }
      dt { font-weight: ${typography.weightMedium}; }
      dd { margin: .25rem 0 .75rem; }
      a { font-size: .85rem; }
    `;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.#mounted) return;
    this.#mounted = true;
    this.innerHTML = `
      <section aria-labelledby="type-heading">
        <h2 id="type-heading">Typography</h2>
        <p class="type-values"><span>${typography.family}</span><span>Line height ${typography.lineHeight}</span><span>Weight ${typography.weightMedium}</span></p>
        <dl>
          <dt>Root</dt><dd><code>${typography.rootSize}</code></dd>
          <dt>Body</dt><dd><code>${typography.bodySize}</code></dd>
          <dt>Headings h1–h6</dt><dd><code>${typography.h1Size} · ${typography.h2Size} · ${typography.h3Size} · ${typography.h4Size} · ${typography.h5Size} · ${typography.h6Size}</code></dd>
          <dt>Label</dt><dd><code>${typography.labelSize}</code> of the root</dd>
        </dl>
        <a href="/design/typography/">Explore typography →</a>
      </section>`;
  }
}
