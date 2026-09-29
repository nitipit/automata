import { Base } from '../lib/adaptive-ui.js';
import Prism from '../lib/prism.js';
import lineNumbersCSS from './prism-line-numbers.css.js';

class CodeExample extends Base {
  static {
    this.css = `
      display: block;
      min-width: 0;
      margin: .8rem 0;
      pre {
        margin: 0;
        padding: 1rem;
        border: 1px solid var(--aui-border);
        border-radius: .4rem;
        background: var(--webref-bg);
        color: var(--aui-text);
        overflow: auto;
        white-space: pre;
        font: .82rem/1.65 ui-monospace, monospace;
        tab-size: 2;
      }
      code { white-space: inherit; overflow-wrap: normal; }
      ${lineNumbersCSS}
      .line-numbers-rows { border-color: var(--aui-border); }
      .line-numbers-rows > span::before { color: var(--aui-muted-text); }
      .token.comment, .token.prolog { color: var(--aui-muted-text); font-style: italic; }
      .token.keyword, .token.atrule { color: light-dark(#6d28d9, #c4b5fd); }
      .token.string, .token.regex { color: light-dark(#166534, #86efac); }
      .token.number, .token.boolean { color: light-dark(#9a3412, #fdba74); }
      .token.function, .token.class-name { color: var(--aui-action); }
      .token.property, .token.variable, .token.tag { color: light-dark(#9d174d, #f9a8d4); }
      .token.italic { font-style: italic; }
      .token.bold { font-weight: 700; }
    `;
  }

  highlight() {
    for (const code of this.querySelectorAll('pre > code')) {
      if (code.classList.contains('language-mermaid')) continue;
      const raw = code.textContent;
      // Reset previous tokens/gutter on reconnect or a new raw-source response.
      code.textContent = raw;
      code.parentElement.classList.add('line-numbers');
      Prism.highlightElement(code);
      // Prism normalizes NBSP. Preserve authored whitespace even for that case:
      // fall back to literal text and invoke the official numbering hook only.
      if (code.textContent !== raw) {
        code.textContent = raw;
        Prism.hooks.run('complete', { element: code, code: raw });
      }
    }
  }

  connectedCallback() {
    super.connectedCallback();
    queueMicrotask(() => {
      if (this.isConnected) this.highlight();
    });
  }
}
CodeExample.define('code-example');
