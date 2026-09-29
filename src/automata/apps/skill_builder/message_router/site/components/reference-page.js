import { Base } from '../lib/adaptive-ui.js';

// Only the document reset is global; all page rules are Adapter-scoped below.
const reset = new CSSStyleSheet();
reset.replaceSync('html, body { margin: 0; min-height: 100%; }');
document.adoptedStyleSheets = [...document.adoptedStyleSheets, reset];

const choices = new Set(['system', 'light', 'dark']);

export class ReferencePage extends Base {
  static {
    this.css = `

  color-scheme: light;
  --aui-surface: #ffffff;
  --aui-text: #172b4d;
  --aui-muted-text: #475569;
  --aui-border: #cbd5e1;
  --aui-action: #1d4ed8;
  --aui-focus: #1d4ed8;
  --webref-bg: #f8fafc;
  --webref-accent-soft: #dbeafe;
  --webref-success: #166534;
&[data-theme=dark] {
  color-scheme: dark;
  --aui-surface: #1e293b;
  --aui-text: #e2e8f0;
  --aui-muted-text: #b6c3d2;
  --aui-border: #475569;
  --aui-action: #60a5fa;
  --aui-focus: #93c5fd;
  --webref-bg: #0f172a;
  --webref-accent-soft: #1e3a5f;
  --webref-success: #86efac;
}
* { box-sizing: border-box; }
& {
  display: block;
  min-height: 100vh;
  margin: 0;
  padding: clamp(1rem, 3vw, 2.5rem);
  background: var(--webref-bg);
  color: var(--aui-text);
  font: 16px/1.6 system-ui, sans-serif;
}
main { max-width: 1080px; margin: auto; }
h1, h2, h3, p { margin-top: 0; }
h1 { font-size: clamp(2rem, 4vw, 2.8rem); line-height: 1.15; margin-bottom: .6rem; }
h2 { font-size: 1.4rem; line-height: 1.3; }
h3 { font-size: 1.05rem; }
a { color: var(--aui-action); }
.page-head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.brand { font-size: .85rem; font-weight: 750; letter-spacing: .08em; text-decoration: none; color: var(--aui-text); }
label { display: flex; align-items: center; gap: .5rem; font-size: .85rem; }
select { padding: .5rem; background: var(--aui-surface); color: var(--aui-text); border: 1px solid var(--aui-border); border-radius: .35rem; font: inherit; }
nav { display: flex; gap: .35rem; flex-wrap: wrap; border-bottom: 1px solid var(--aui-border); padding: 1rem 0; }
nav a { padding: .45rem .7rem; border-radius: .35rem; text-decoration: none; }
nav a[aria-current=page] { background: var(--webref-accent-soft); font-weight: 700; }
nav a:hover { text-decoration: underline; }
:focus-visible { outline: 3px solid var(--aui-focus); outline-offset: 3px; }
.skip-link { position: absolute; top: -5rem; }
.skip-link:focus { top: .5rem; background: var(--aui-surface); padding: .5rem; z-index: 10; }
.guide-heading { margin: 2rem 0 1rem; }
.eyebrow { font-size: .75rem; letter-spacing: .12em; font-weight: 700; color: var(--aui-action); margin-bottom: .5rem; }
.goal { font-size: 1.2rem; max-width: 48rem; }
.guide-context { border-left: 3px solid var(--aui-border); padding: 1rem; color: var(--aui-muted-text); font-size: .9rem; }
.lesson { min-width: 0; margin: 1.5rem 0; padding: clamp(1rem, 3vw, 1.6rem); border: 1px solid var(--aui-border); border-radius: .6rem; background: var(--aui-surface); }
.lesson h3 { margin-top: 1.2rem; }
.lesson li { margin-bottom: .5rem; }
.result { border-left: 3px solid var(--webref-success); padding-left: 1rem; margin-top: 1rem; }
code { overflow-wrap: anywhere; }
pre { max-width: 100%; overflow: auto; }
details { margin: 1rem 0; }
summary { cursor: pointer; }
.next { display: block; margin: 2rem 0; font-weight: 600; }
footer { border-top: 1px solid var(--aui-border); padding-top: 1rem; color: var(--aui-muted-text); font-size: .85rem; }
`;
  }

  #system = matchMedia('(prefers-color-scheme: dark)');
  #preference = 'system';
  #selector;
  #selectTheme = () => {
    this.#preference = this.#selector.value;
    try { localStorage.setItem('message-router-webref-theme', this.#preference); }
    catch { /* Apply without persistence. */ }
    this.#applyTheme();
  };
  #systemChanged = () => {
    if (this.#preference === 'system') this.#applyTheme();
  };

  connectedCallback() {
    super.connectedCallback();
    try {
      const saved = localStorage.getItem('message-router-webref-theme');
      if (choices.has(saved)) this.#preference = saved;
    } catch { /* Storage is optional. */ }
    this.#selector = this.querySelector('#theme');
    this.#selector.value = this.#preference;
    this.#selector.addEventListener('change', this.#selectTheme);
    this.#system.addEventListener('change', this.#systemChanged);
    this.#applyTheme();
  }

  disconnectedCallback() {
    this.#selector?.removeEventListener('change', this.#selectTheme);
    this.#system.removeEventListener('change', this.#systemChanged);
    super.disconnectedCallback?.();
  }

  #applyTheme() {
    this.dataset.theme = this.#preference === 'system'
      ? (this.#system.matches ? 'dark' : 'light') : this.#preference;
    document.dispatchEvent(new CustomEvent('webref-theme-change'));
  }
}
