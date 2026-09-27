import { Base, tokens } from "/lib/adaptive-ui.js";

// The saved artifact stays durable without adding a preset artifact to this surface.
export class WorkSurface extends Base {
  static {
    this.css = `
      display:flex;
      flex:1;
      min-width:0;
      min-height:0;
      background:${tokens.surface};
      section {
        width:100%;
        min-width:0;
        min-height:100%;
      }
    `;
  }

  constructor() {
    super();
    this.innerHTML = `<section aria-label="Workspace surface"></section>`;
  }
}

WorkSurface.define("wsp-surface");
