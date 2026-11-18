import { Base } from "./base";
import type { ResolvedTheme } from "../_theme/index";
import { buttonStyle, buttonTheme } from "./button.style";
import { registerSharedComponent } from "./create";
import { booleanData, stringData } from "./descriptor-data";

type ButtonData = { text?: string; disabled?: boolean; type?: "button" | "submit" | "reset" };

/** Native button in light DOM. Set text/children before connection or use control. */
export class Button extends Base {
  static get create() { return createButton; }
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
const createButton = registerSharedComponent("ui-button", Button,
  (element, data: ButtonData | undefined, children) => {
    const type = stringData(data, "type");
    if (type === "button" || type === "submit" || type === "reset") element.type = type;
    element.disabled = booleanData(data, "disabled") ?? false;
    element.append(stringData(data, "text") ?? "", ...children);
  });
