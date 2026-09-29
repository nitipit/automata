import { ReferencePage } from './components/reference-page.js';

class CatalogPage extends ReferencePage {
  static {
    this.css = `
      li { margin: 1rem 0; }
      main { max-width: 70ch; }
      [aria-disabled=true] { color: var(--aui-muted-text); text-decoration: none; }
      [role=status] { display: block; color: var(--aui-muted-text); font-size: .85rem; }
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
      status.textContent = 'Checking availability in this preview…';
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
      // Native Engrave does not promise HEAD support. Read status only; never
      // follow a redirect or probe anything beyond the maintained entry URL.
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
    status.textContent = available
      ? 'Available in this preview.' : 'Unavailable in this preview.';
  }

  disconnectedCallback() {
    this.#request?.abort();
    super.disconnectedCallback();
  }
}
CatalogPage.define('catalog-page');
