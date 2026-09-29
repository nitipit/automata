import { Base } from "/lib/adaptive-ui.js";
import { noteCss } from "./example-note.css.js";

// Internal to the example website, not part of the external Adaptive UI catalog.
export class ExampleNote extends Base {
  static {
    this.css = noteCss;
  }
}
