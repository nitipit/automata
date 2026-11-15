import { Base } from "./base";
import type { ResolvedTheme } from "../_theme/index";
import { buttonStyle, buttonTheme } from "./button.style";

/** Native button in light DOM. Set text/children before connection or use control. */
export class Button extends Base {
  static get observedAttributes(): string[] { return ["disabled", "type"]; }
  readonly control = document.createElement("button");

  connectedCallback(): void {
    if (this.control.parentNode !== this) {
      while (this.firstChild) this.control.append(this.firstChild);
      this.append(this.control);
    }
    this.sync();
    super.connectedCallback();
  }

  attributeChangedCallback(): void { this.sync(); }
  get disabled(): boolean { return this.hasAttribute("disabled"); }
  set disabled(value: boolean) { this.toggleAttribute("disabled", value); }
  get type(): string { return this.control.type; }
  set type(value: string) { this.setAttribute("type", value); }
  override focus(options?: FocusOptions): void { this.control.focus(options); }

  private sync(): void {
    this.control.disabled = this.disabled;
    const type = this.getAttribute("type");
    this.control.type = type === "submit" || type === "reset" ? type : "button";
  }
  protected themedStyle(theme: ResolvedTheme): string { return buttonTheme(theme); }
}
Button.css = buttonStyle;
Button.define("ui-button");
