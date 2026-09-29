import { ReferencePage } from './components/reference-page.js';

class CatalogPage extends ReferencePage {
  static {
    this.css = `
      .page-head { padding-bottom: 1.5rem; border-bottom: 1px solid var(--aui-border); }
      .catalog-intro { margin: clamp(2rem, 5vw, 4rem) 0 2rem; max-width: 65ch; }
      .catalog-description { color: var(--aui-muted-text); font-size: 1.05rem; margin-bottom: 1.25rem; }
      .catalog-count { display: inline-block; font-size: .8rem; padding: .25rem .65rem; border: 1px solid var(--aui-border); border-radius: 999px; color: var(--aui-muted-text); }
      .skill-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr)); gap: 1.25rem; list-style: none; margin: 0 0 2rem; padding: 0; }
      .skill-card { position: relative; min-width: 0; border: 1px solid var(--aui-border); border-radius: .8rem; background: var(--aui-surface); }
      .skill-card:has(a[href]):hover { border-color: var(--aui-action); }
      .skill-link { display: flex; flex-direction: column; height: 100%; padding: 1.5rem; border-radius: inherit; color: var(--aui-text); text-decoration: none; }
      .skill-kind { font: .8rem ui-monospace, monospace; color: var(--aui-muted-text); margin-bottom: 2rem; }
      .skill-link h2 { margin-bottom: .75rem; font-size: 1.3rem; }
      .skill-description { color: var(--aui-muted-text); font-size: .95rem; margin-bottom: 1.5rem; }
      .skill-action { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-top: auto; color: var(--aui-action); font-size: .9rem; font-weight: 650; }
      .skill-action span { font-size: 1.2rem; }
      .skill-status { position: absolute; top: 1.25rem; right: 1.5rem; display: inline-flex; align-items: center; gap: .4rem; font-size: .75rem; color: var(--aui-muted-text); pointer-events: none; }
      .skill-status::before { content: ''; width: .4rem; height: .4rem; border-radius: 50%; background: currentColor; }
      .skill-status[data-state=available] { color: var(--webref-success); }
      [aria-disabled=true] .skill-action { color: var(--aui-muted-text); }
      .catalog-help { padding: 1rem 0; border-top: 1px solid var(--aui-border); color: var(--aui-muted-text); font-size: .9rem; }
      .catalog-help summary { color: var(--aui-text); }
      .catalog-help p { max-width: 80ch; margin: 1rem 0; }
      .catalog-help code { padding: .1em .3em; border-radius: .25em; background: var(--webref-accent-soft); }
      footer { margin-top: 1rem; font-size: .8rem; }
    `;
  }

  #request;

  connectedCallback() {
    super.connectedCallback();
    this.#request?.abort();
    const request = this.#request = new AbortController();
    for (const link of this.querySelectorAll('[data-catalog-href]')) {
      const status = link.nextElementSibling;
      link.removeAttribute('href');
      link.setAttribute('aria-disabled', 'true');
      link.tabIndex = -1;
      status.dataset.state = 'checking';
      status.textContent = 'Checking…';
      this.#check(link, status, request);
    }
  }

  async #check(link, status, request) {
    let available = false;
    let target;
    try {
      target = new URL(link.dataset.catalogHref, location.origin);
      if (target.origin !== location.origin || target.username || target.password) {
        throw new Error('Not a local catalog entry');
      }
      // Read GET status only; never follow a redirect or probe anything
      // beyond the discovered entry URL.
      const response = await fetch(target.href, {
        method: 'GET', mode: 'same-origin', credentials: 'same-origin',
        redirect: 'error', cache: 'no-store',
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(5000)]),
      });
      available = response.ok;
      await response.body?.cancel();
    } catch {
      // HTTP/network/timeout failures do not establish a specific cause.
      available = false;
    }
    if (request.signal.aborted || !this.isConnected) return;
    if (available) {
      link.href = target.pathname + target.search + target.hash;
      link.removeAttribute('aria-disabled');
      link.removeAttribute('tabindex');
    }
    status.dataset.state = available ? 'available' : 'unavailable';
    status.textContent = available ? 'Available' : 'Unavailable';
  }

  disconnectedCallback() {
    this.#request?.abort();
    super.disconnectedCallback();
  }
}
CatalogPage.define('catalog-page');
