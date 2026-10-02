// Progressive enhancement: server-rendered pages remain ordinary navigable URLs.
let request;
let generation = 0;
let transition;
const selector = 'body > skill-page, body > catalog-page';
const modules = {
  'skill-page': '/templates/skill.css.js',
  'catalog-page': '/templates/catalog.css.js',
};

async function navigate(url, { pop = false } = {}) {
  request?.abort();
  const controller = request = new AbortController();
  const epoch = ++generation;
  try {
    const response = await fetch(url, {
      signal: controller.signal, headers: { Accept: 'text/html' },
    });
    if (!response.ok || new URL(response.url).origin !== location.origin ||
        !response.headers.get('content-type')?.includes('text/html')) {
      throw new Error('Use normal navigation');
    }
    const finalUrl = new URL(response.url);
    finalUrl.hash ||= new URL(url).hash;
    const next = new DOMParser().parseFromString(await response.text(), 'text/html');
    const page = next.querySelector(selector);
    if (!page || !modules[page.localName]) throw new Error('Not a skill page');
    await import(modules[page.localName]);
    await transition?.finished;
    if (controller.signal.aborted || epoch !== generation) return;
    const replace = () => {
      if (controller.signal.aborted || epoch !== generation) return;
      const current = document.querySelector(selector);
      if (!current) throw new Error('No current page');
      current.replaceWith(document.importNode(page, true));
      document.title = next.title;
      if (pop) {
        if (location.href !== finalUrl.href) history.replaceState(null, '', finalUrl.href);
      } else history.pushState(null, '', finalUrl.href);
      const hash = finalUrl.hash;
      const target = hash ? document.getElementById(decodeURIComponent(hash.slice(1))) : null;
      if (target) target.scrollIntoView();
      else window.scrollTo(0, 0);
      const focus = target || document.querySelector('article, main');
      if (focus) {
        if (!focus.hasAttribute('tabindex')) focus.tabIndex = -1;
        focus.focus({ preventScroll: true });
      }
    };
    if (document.startViewTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      transition = document.startViewTransition(replace);
      await transition.updateCallbackDone;
    } else replace();
  } catch (error) {
    if (controller.signal.aborted || epoch !== generation) return;
    // A failed enhancement must never strand a link or leave a popped URL stale.
    if (pop) location.reload();
    else location.assign(url);
  }
}

document.addEventListener('click', event => {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey ||
      event.shiftKey || event.altKey) return;
  const anchor = event.target.closest?.('a[href]');
  if (!anchor || anchor.hasAttribute('download') ||
      (anchor.target && anchor.target !== '_self')) return;
  const url = new URL(anchor.href);
  if (url.origin !== location.origin || !['http:', 'https:'].includes(url.protocol)) return;
  if (url.pathname === location.pathname && url.search === location.search) return;
  // Leave raw sources, downloads, licenses and arbitrary URLs to the browser.
  if (!(url.pathname.endsWith('/') || url.pathname.endsWith('.html'))) return;
  event.preventDefault();
  void navigate(url.href);
});

window.addEventListener('popstate', () => { void navigate(location.href, { pop: true }); });
