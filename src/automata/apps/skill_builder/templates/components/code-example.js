import { Base } from '../lib/adaptive-ui.js';
import hljs from '../lib/highlight.js';

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
        font: .82rem/1.65 ui-monospace, monospace;
        tab-size: 2;
      }
      code { white-space: pre; overflow-wrap: normal; }
      .hljs-comment, .hljs-quote { color: var(--aui-muted-text); font-style: italic; }
      .hljs-keyword, .hljs-selector-tag, .hljs-meta {
        color: light-dark(#6d28d9, #c4b5fd);
      }
      .hljs-string, .hljs-regexp, .hljs-addition { color: light-dark(#166534, #86efac); }
      .hljs-number, .hljs-literal, .hljs-symbol, .hljs-bullet {
        color: light-dark(#9a3412, #fdba74);
      }
      .hljs-title, .hljs-built_in, .hljs-type { color: var(--aui-action); }
      .hljs-attr, .hljs-attribute, .hljs-variable, .hljs-template-variable {
        color: light-dark(#9d174d, #f9a8d4);
      }
      .hljs-emphasis { font-style: italic; }
      .hljs-strong { font-weight: 700; }
    `;
  }

  connectedCallback() {
    super.connectedCallback();
    // Let the current attachment finish; reconnect highlights from text, not old spans.
    queueMicrotask(() => {
      if (!this.isConnected) return;
      for (const code of this.querySelectorAll('pre > code')) {
        const language = [...code.classList].find(name => name.startsWith('language-'))
          ?.slice('language-'.length).toLowerCase();
        // No auto-detection: unknown/plain fences stay literal; Mermaid has its own owner.
        if (!language || language === 'mermaid' || !hljs.getLanguage(language)) continue;
        const raw = code.textContent;
        const fragment = document.createElement('template');
        fragment.innerHTML = hljs.highlight(raw, { language, ignoreIllegals: true }).value;
        // Highlight.js escapes source; insert only its output, never authored HTML.
        // Fail closed if a grammar ever changes the exact selection/copy text.
        if (fragment.content.textContent === raw) code.replaceChildren(fragment.content);
      }
    });
  }
}
CodeExample.define('code-example');
