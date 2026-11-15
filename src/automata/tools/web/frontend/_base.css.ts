import { color } from "./_tokens/color";

/** Page-level reset; component rules remain scoped by Adapter. */
export function applyBaseStyles() {
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(`
    *, *::before, *::after { box-sizing: border-box; }
    html { min-height: 100%; background: ${color.canvas}; }
    body { margin: 0; color: ${color.ink}; font: 16px/1.5 system-ui, sans-serif; }
    button, textarea, input, select { font: inherit; }
    :focus-visible { outline: 3px solid ${color.focus}; outline-offset: 3px; }
  `);
  document.adoptedStyleSheets.push(sheet);
}
