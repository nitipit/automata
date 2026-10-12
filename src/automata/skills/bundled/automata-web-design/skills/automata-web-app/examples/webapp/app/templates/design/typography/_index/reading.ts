import { Base } from "@adaptive/base";
import { typography } from "@adaptive/tokens";

export class Reading extends Base {
  #mounted = false;

  static {
    this.css = `
      display: block;
      margin-bottom: 3rem;
      .specimen-heading { margin-bottom: 1.5rem; }
      .specimen-heading h2 { margin: 0 0 .35rem; }
      .specimen-heading p { margin: 0; color: #5e5c64; font-size: ${typography.labelSize}; }
      .type-board { padding: 2rem; border: 1px solid #deddda; border-radius: .75rem; background: #ffffff; font-size: ${typography.bodySize}; line-height: ${typography.lineHeight}; }
      .type-eyebrow { margin: 0 0 1rem; color: #5e5c64; font-size: ${typography.labelSize}; }
      .type-heading { margin: 0 0 1rem; font-size: ${typography.h3Size}; line-height: ${typography.headingLineHeight}; letter-spacing: -.025em; }
      .type-body { max-width: 58ch; margin: 0 0 1.5rem; font-size: ${typography.bodySize}; }
      .type-lists { display: flex; flex-wrap: wrap; gap: 1.5rem 3rem; max-width: 58ch; margin-bottom: 1.5rem; }
      .type-lists ul, .type-lists ol { flex: 1 1 14rem; margin: 0; padding-left: 1.5rem; }
      .type-lists li + li { margin-top: .35rem; }
      .type-label { display: block; font-size: ${typography.labelSize}; font-weight: ${typography.weightMedium}; }
      .specimen-note { margin: .75rem 0 0; color: #5e5c64; font-size: ${typography.labelSize}; }
      @media (max-width: 700px) { .type-board { padding: 1.5rem; } }
    `;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.#mounted) return;
    this.#mounted = true;
    this.innerHTML = `
      <section aria-labelledby="reading-heading">
        <div class="specimen-heading"><h2 id="reading-heading">Reading specimen</h2><p>Paragraphs, weights, emphasis, links, lists and labels in one composition.</p></div>
        <article id="typography-specimen" class="type-board">
          <p class="type-eyebrow">Field notes</p>
          <h3 class="type-heading">Make room for what matters.</h3>
          <p class="type-body">A clear heading gives us a place to begin. Comfortable lines carry the thought forward, while a smaller label leaves the next step easy to find. The same family holds the whole composition together.</p>
          <p class="type-body">Regular text uses ${typography.weightRegular} weight. <strong>A stronger phrase uses ${typography.weightMedium}.</strong> <em>Emphasis changes the voice without changing the scale.</em> A <a href="#scale-heading">link to the type scale</a> gives the next thought a destination.</p>
          <div class="type-lists">
            <ul><li>Start with a clear heading.</li><li>Keep lines comfortable to read.</li><li>Leave room between ideas.</li></ul>
            <ol><li>Read the composition.</li><li>Resize the viewport.</li><li>Notice what stays in proportion.</li></ol>
          </div>
          <span class="type-label">Field note · Typography study</span>
        </article>
        <p id="typography-values" class="specimen-note">Body ${typography.bodySize} / ${typography.lineHeight} · Label ${typography.labelSize} of the root · Reading measure 58ch</p>
      </section>`;
  }
}
