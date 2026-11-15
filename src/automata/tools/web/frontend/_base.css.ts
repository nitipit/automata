import { bindTheme } from "./_theme/index";

/** Page-only reset + canonical theme binding; component defaults live in Base. */
export function applyBaseStyles(): () => void {
  const sheet = new CSSStyleSheet();
  document.adoptedStyleSheets.push(sheet);
  const stop = bindTheme(document.documentElement, ({ mode, roles: r }) => {
    sheet.replaceSync(`
      *, *::before, *::after { box-sizing: border-box; }
      html { min-height: 100%; background: ${r.canvas}; color-scheme: ${mode}; }
      body { margin: 0; color: ${r.text}; font: 16px/1.5 system-ui, sans-serif; }
      button, textarea, input, select { font: inherit; }
      :focus-visible { outline: 3px solid ${r.focus}; outline-offset: 3px; }
    `);
  });
  return () => { stop(); document.adoptedStyleSheets = document.adoptedStyleSheets.filter(value => value !== sheet); };
}
