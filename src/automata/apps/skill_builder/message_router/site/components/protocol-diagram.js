import { Base } from '../lib/adaptive-ui.js';
// Closed, authored diagrams only. No URL, API or user text enters Mermaid.
export const diagrams = Object.freeze({
  grants: `flowchart LR
    desk[desk · page] -->|may start| viewer[viewer · page]
    desk -->|may start| worker[worker · agent]
    worker -->|may start| reviewer[reviewer · agent]
    reviewer -->|may start| worker`,
  connections: `flowchart LR
    desk[desk · page] --- router[Router service]
    viewer[viewer · page] --- router
    router --- worker[worker · agent]
    router --- reviewer[reviewer · agent]`,
  discover: `flowchart LR
    desk[desk] -->|allowed · connected| viewer[viewer]
    desk -->|allowed · connected| worker[worker]`,
  initiate: `sequenceDiagram
    participant W as worker
    participant R as Router service
    participant V as reviewer
    W->>R: send reviewer, new payload
    R->>V: message, expectReply true
    R-->>W: accepted: forwarded
    Note over W,V: reviewer may also start independently (own grant)`,
  reply: `sequenceDiagram
    participant D as desk
    participant R as Router service
    participant W as worker
    D->>R: send worker (request.id)
    R->>W: message (message.id)
    R-->>D: forwarded (routeId = message.id)
    W->>R: respond(message.id, payload)
    R-->>D: response (requestId = request.id)
    Note over D,W: Return capability, not worker → desk initiation permission`,
  oneway: `sequenceDiagram
    participant D as desk
    participant R as Router service
    participant V as viewer
    D->>R: send viewer, expectReply false
    R->>V: message, no reply capability
    R-->>D: accepted: forwarded`,
  rejected: `sequenceDiagram
    participant W as worker
    participant R as Router service
    W->>R: send desk (no grant)
    R-->>W: rejected: forbidden
    Note over W,R: Nothing forwarded`,
  cancel: `sequenceDiagram
    participant D as desk
    participant R as Router service
    participant W as worker
    D->>R: send worker
    R->>W: message delivered
    R-->>D: forwarded
    D->>R: cancel(request.id) via client
    R-->>D: canceled
    Note over R,W: Capability removed, recipient effects are not undone`,
});
class ProtocolDiagram extends Base {
  static { this.css = `display:block; margin:1rem 0; border:1px solid var(--aui-border); border-radius:.4rem;
    background:var(--webref-bg); color:var(--aui-text); padding:1rem; min-width:0;
    .diagram-stage {overflow:auto; max-width:100%;}
    svg {display:block; margin:auto; max-width:100%; height:auto;}
    .sequence svg {min-width:620px;}
    figcaption {font:.8rem/1.5 system-ui; color:var(--aui-muted-text); margin-top:.5rem;}
  `; }
  #version = 0;
  #themeChanged = () => this.render();
  connectedCallback() {
    super.connectedCallback();
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
    let source = diagrams[this.dataset.diagram];
    if (!source) return;
    if (matchMedia('(max-width: 600px)').matches) source = source.replace('flowchart LR', 'flowchart TB');
    try {
      await library;
      const css = getComputedStyle(this);
      const token = name => css.getPropertyValue(name).trim();
      const surface = token('--aui-surface'), text = token('--aui-text'), border = token('--aui-border');
      globalThis.mermaid.initialize({
        startOnLoad:false, securityLevel:'strict', theme:'base', htmlLabels:false,
        flowchart:{htmlLabels:false}, sequence:{useMaxWidth:true},
        themeVariables:{fontFamily:'system-ui, sans-serif', fontSize:'16px',
          primaryColor:surface, primaryTextColor:text, primaryBorderColor:border,
          lineColor:text, textColor:text, actorBkg:surface, actorTextColor:text,
          actorBorder:border, signalColor:text, signalTextColor:text,
          noteBkgColor:token('--webref-accent-soft'), noteTextColor:text,
          noteBorderColor:border, edgeLabelBackground:surface}
      });
      const { svg } = await globalThis.mermaid.render(`protocol-${++sequence}`, source);
      if (version !== this.#version || !this.isConnected) return;
      const figure = document.createElement('figure'); figure.style.margin = '0';
      const stage = document.createElement('div');
      stage.className = 'diagram-stage' + (source.startsWith('sequenceDiagram') ? ' sequence' : '');
      stage.tabIndex = 0;
      stage.setAttribute('role', 'img');
      stage.setAttribute('aria-label', this.getAttribute('aria-label'));
      // Mermaid strict mode sanitizes a closed, compile-time source registry.
      stage.innerHTML = svg;
      const caption = document.createElement('figcaption');
      caption.textContent = this.getAttribute('aria-label') + ' Scroll the diagram horizontally if needed.';
      figure.append(stage, caption); this.replaceChildren(figure);
    } catch { this.textContent = 'Diagram unavailable. The explanation and code below describe the same flow.'; }
  }
}
let sequence = 0;
const library = new Promise((resolve, reject) => {
  const script = document.createElement('script');
  script.src = new URL('../lib/mermaid.js', import.meta.url).href;
  script.onload = resolve;
  script.onerror = reject; document.head.append(script);
});
ProtocolDiagram.define('protocol-diagram');
