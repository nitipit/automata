import { Base, Button, Card } from '/lib/adaptive-ui.js';
import { initializeTheme, setTheme } from '../theme.js';
Button.define('aui-button');
Card.define('aui-card');
class AnatomyNav extends Base {
  static { this.css = `display:block; margin:1rem 0 1.5rem;
    nav { display:flex; flex-wrap:wrap; gap:.4rem; }
    a { padding:.55rem .8rem; border-radius:.35rem; color:var(--aui-muted-text); text-decoration:none; }
    a:hover { background:var(--anatomy-accent-soft); }
    a[aria-current] { color:var(--aui-action); background:var(--anatomy-accent-soft); font-weight:650; }
  `; }
}
AnatomyNav.define('anatomy-nav');
const picker = document.getElementById('theme');
picker.value = initializeTheme();
picker.addEventListener('change', () => setTheme(picker.value));
// Remember only section-local allowlisted queries, never arbitrary return URLs.
const contracts = {
  overview: ['paused'], skills: ['query','setup'], tools: ['query','setup'],
  activity: ['range','timezone','skill','limit','paused','start','end'],
};
function restoreQueries() {
  try {
    for (const link of document.querySelectorAll('anatomy-nav [data-section]')) {
      const section = link.dataset.section;
      // Current URL wins; detail pages can return to the remembered catalog query.
      const query = link.pathname === location.pathname ? location.search : sessionStorage.getItem(`anatomy-query-${section}`);
      if (query?.length >= 4096) continue;
      const safe = new URLSearchParams([...new URLSearchParams(query || '')].filter(([key]) => contracts[section].includes(key)));
      link.search = safe.toString();
    }
  } catch { /* Disabled storage: browser history still retains section URLs. */ }
}
restoreQueries();
document.addEventListener('anatomy-query-change', restoreQueries);
