import { Base } from '../lib/adaptive-ui.js';

// Render only the authored Mermaid block embedded by the Markdown build.
// No URL, API, router payload or interactive input supplies diagram source.
class ProtocolDiagram extends Base {
  static {
    this.css = `
      display: block;
      margin: 1rem 0;
      border: 1px solid var(--aui-border);
      border-radius: .4rem;
      background: var(--webref-bg);
      color: var(--aui-text);
      padding: 1rem;
      min-width: 0;
      figure { margin: 0; }
      .diagram-stage { overflow: auto; max-width: 100%; }
      svg { display: block; margin: auto; max-width: 100%; height: auto; }
      .sequence svg { min-width: 620px; }
      figcaption {
        font: .8rem/1.5 system-ui;
        color: var(--aui-muted-text);
        margin-top: .5rem;
      }
    `;
  }

  #version = 0;
  #source = '';
  #themeChanged = () => this.render();

  connectedCallback() {
    super.connectedCallback();
    // Capture once before rendering replaces children; retain for theme/reconnect.
    this.#source ||= this.querySelector('.diagram-source')?.textContent.trim() || '';
    document.addEventListener('webref-theme-change', this.#themeChanged);
    this.render();
  }

  disconnectedCallback() {
    this.#version++;
    document.removeEventListener('webref-theme-change', this.#themeChanged);
    super.disconnectedCallback?.();
  }

  async render() {
    const version = ++this.#version;
    let source = this.#source;
    if (!source) return;
    if (matchMedia('(max-width: 600px)').matches) {
      source = source.replace('flowchart LR', 'flowchart TB');
    }
    try {
      await library;
      const css = getComputedStyle(this);
      const token = name => css.getPropertyValue(name).trim();
      const surface = token('--aui-surface');
      const text = token('--aui-text');
      const border = token('--aui-border');
      globalThis.mermaid.initialize({
        startOnLoad: false, securityLevel: 'strict', theme: 'base', htmlLabels: false,
        flowchart: { htmlLabels: false }, sequence: { useMaxWidth: true },
        themeVariables: {
          fontFamily: 'system-ui, sans-serif', fontSize: '16px',
          primaryColor: surface, primaryTextColor: text, primaryBorderColor: border,
          lineColor: text, textColor: text, actorBkg: surface, actorTextColor: text,
          actorBorder: border, signalColor: text, signalTextColor: text,
          noteBkgColor: token('--webref-accent-soft'), noteTextColor: text,
          noteBorderColor: border, edgeLabelBackground: surface,
        },
      });
      const { svg } = await globalThis.mermaid.render(`protocol-${++sequence}`, source);
      if (version !== this.#version || !this.isConnected) return;
      const figure = document.createElement('figure');
      const stage = document.createElement('div');
      stage.className = 'diagram-stage' + (source.startsWith('sequenceDiagram') ? ' sequence' : '');
      stage.tabIndex = 0;
      stage.setAttribute('role', 'img');
      stage.setAttribute('aria-label', this.getAttribute('aria-label'));
      // Mermaid strict mode sanitizes source from the trusted, built Markdown.
      stage.innerHTML = svg;
      const caption = document.createElement('figcaption');
      caption.textContent = this.getAttribute('aria-label')
        + ' Scroll the diagram horizontally if needed.';
      figure.append(stage, caption);
      this.replaceChildren(figure);
    } catch {
      this.textContent = 'Diagram unavailable. The explanation and code below describe the same flow.';
    }
  }
}

let sequence = 0;
const library = new Promise((resolve, reject) => {
  const script = document.createElement('script');
  script.src = new URL('../lib/mermaid.js', import.meta.url).href;
  script.onload = resolve;
  script.onerror = reject;
  document.head.append(script);
});
ProtocolDiagram.define('protocol-diagram');
