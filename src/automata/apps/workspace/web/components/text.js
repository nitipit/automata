import { Base } from "/lib/adaptive-ui.js";

export class TextComponent extends Base {
  static { this.css = "display:block; white-space:pre-wrap; overflow-wrap:anywhere;"; }
  static validateData(data) {
    if (!data || typeof data.text !== "string" || data.text.length > 6000) {
      throw new Error("Text must contain at most 6000 characters");
    }
    return { text: data.text };
  }
  applyData(data) { this.textContent = data.text; }
}
TextComponent.define("wsp-text");
