import { Base } from '/lib/adaptive-ui.js';
class CodeExample extends Base {
  static { this.css = `display:block; min-width:0; margin:.8rem 0;
    pre { margin:0; padding:1rem; border:1px solid var(--aui-border); border-radius:.4rem;
      background:var(--anatomy-bg); color:var(--aui-text); overflow:auto; font: .82rem/1.65 ui-monospace,monospace; tab-size:2; }
    code {white-space:pre;overflow-wrap:normal;}
  `; }
}
CodeExample.define('code-example');
