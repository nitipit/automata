import { Base } from '/lib/adaptive-ui.js';

import { initializeTheme } from '/shared/theme.js';

export class ReferencePage extends Base {
  static {
    this.css = `

  --webref-bg: var(--anatomy-bg);
  --webref-accent-soft: var(--anatomy-accent-soft);
  --webref-success: var(--anatomy-success);
* { box-sizing: border-box; }
& {
  display: block;
  min-height: 50vh;
  margin: 0;
  padding: clamp(1rem, 3vw, 2.5rem) 0;
  background: var(--webref-bg);
  color: var(--aui-text);
  font: 16px/1.6 system-ui, sans-serif;
}
main { width: 90%; max-width: 1200px; margin: auto; }
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

  #applyTheme = () => {
    this.dataset.theme = document.documentElement.dataset.theme;
    document.dispatchEvent(new CustomEvent('webref-theme-change'));
  };

  connectedCallback() {
    super.connectedCallback();
    initializeTheme();
    document.addEventListener('anatomy-theme-change', this.#applyTheme);
    this.#applyTheme();
  }

  disconnectedCallback() {
    document.removeEventListener('anatomy-theme-change', this.#applyTheme);
    super.disconnectedCallback?.();
  }
}
