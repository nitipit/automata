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
// A return link transports only the validated monitor query, not arbitrary URLs.
try {
  const query = sessionStorage.getItem('anatomy-monitor-query');
  if (query && query.length < 4096) {
    const params = new URLSearchParams(query);
    const allowed = ['tab','query','setup','selected','range','timezone','skill','limit','paused','start','end'];
    const safe = new URLSearchParams([...params].filter(([key]) => allowed.includes(key)));
    for (const link of document.querySelectorAll('[data-monitor-link]')) link.href = '/automata/index.html?' + safe;
  }
} catch { /* Disabled storage: browser history still retains the monitor URL. */ }
