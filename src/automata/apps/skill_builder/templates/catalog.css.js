import { ReferencePage } from './components/reference-page.js';

class CatalogPage extends ReferencePage {
  static {
    this.css = `
      .page-head { padding-bottom: 1.5rem; border-bottom: 1px solid var(--aui-border); }
      .catalog-intro { margin: clamp(2rem, 5vw, 4rem) 0 2rem; max-width: 65ch; }
      .catalog-description { color: var(--aui-muted-text); font-size: 1.05rem; margin-bottom: 1.25rem; }
      .catalog-count { display: inline-block; font-size: .8rem; padding: .25rem .65rem; border: 1px solid var(--aui-border); border-radius: 999px; color: var(--aui-muted-text); }
      .catalog-search { margin-bottom: 1.5rem; }
      .catalog-search label { display: block; margin-bottom: .4rem; font-weight: 650; }
      .search-controls { display: flex; flex-wrap: wrap; gap: .6rem; }
      .search-controls input { flex: 1 1 18rem; min-width: 0; padding: .6rem .75rem; border: 1px solid var(--aui-border); border-radius: .35rem; background: var(--aui-surface); color: var(--aui-text); font: inherit; }
      .search-controls button { padding: .6rem .8rem; border: 1px solid var(--aui-border); border-radius: .35rem; background: var(--aui-surface); color: var(--aui-text); font: inherit; cursor: pointer; }
      #search-count { color: var(--aui-muted-text); font-size: .85rem; margin: .5rem 0 0; }
      #search-empty { margin-bottom: 2rem; }
      [hidden] { display: none !important; }
      .skill-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr)); gap: 1.25rem; list-style: none; margin: 0 0 2rem; padding: 0; }
      .skill-card { position: relative; min-width: 0; border: 1px solid var(--aui-border); border-radius: .8rem; background: var(--aui-surface); }
      .skill-card:has(a[href]):hover { border-color: var(--aui-action); }
      .skill-link { display: flex; flex-direction: column; height: 100%; padding: 1.5rem; border-radius: inherit; color: var(--aui-text); text-decoration: none; }
      .skill-kind { font: .8rem ui-monospace, monospace; color: var(--aui-muted-text); margin-bottom: 2rem; }
      .skill-link h2 { margin-bottom: .75rem; font-size: 1.3rem; }
      .skill-description { color: var(--aui-muted-text); font-size: .95rem; margin-bottom: 1.5rem; }
      .skill-action { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-top: auto; color: var(--aui-action); font-size: .9rem; font-weight: 650; }
      .skill-action span { font-size: 1.2rem; }
      .catalog-help { padding: 1rem 0; border-top: 1px solid var(--aui-border); color: var(--aui-muted-text); font-size: .9rem; }
      .catalog-help summary { color: var(--aui-text); }
      .catalog-help p { max-width: 80ch; margin: 1rem 0; }
      .catalog-help code { padding: .1em .3em; border-radius: .25em; background: var(--webref-accent-soft); }
      footer { margin-top: 1rem; font-size: .8rem; }
    `;
  }

  #search;
  #onInput = () => this.#filter();
  #onClear = () => {
    this.#search.value = '';
    this.#filter();
    this.#search.focus();
  };

  connectedCallback() {
    super.connectedCallback();
    this.#search = this.querySelector('#skill-search');
    this.#search.addEventListener('input', this.#onInput);
    this.querySelector('#clear-search').addEventListener('click', this.#onClear);
    this.#filter();
  }

  #filter() {
    const query = this.#search.value.trim().toLocaleLowerCase();
    let shown = 0;
    for (const card of this.querySelectorAll('.skill-card')) {
      const text = `${card.dataset.name} ${card.querySelector('h2').textContent} ${card.querySelector('.skill-description').textContent}`;
      card.hidden = !text.toLocaleLowerCase().includes(query);
      if (!card.hidden) shown++;
    }
    this.querySelector('#search-count').textContent = `${shown} skill${shown === 1 ? '' : 's'} shown`;
    this.querySelector('#clear-search').hidden = !query;
    this.querySelector('#search-empty').hidden = shown !== 0;
  }

  disconnectedCallback() {
    this.#search?.removeEventListener('input', this.#onInput);
    this.querySelector('#clear-search')?.removeEventListener('click', this.#onClear);
    super.disconnectedCallback();
  }
}
CatalogPage.define('catalog-page');
