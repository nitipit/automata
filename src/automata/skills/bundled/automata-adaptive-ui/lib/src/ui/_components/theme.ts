import { resolveThemeColors, themeTypography, validateThemeMode,
  type ThemeMode, type ThemeStyleFactory } from "../theme.tokens.js";

let nextThemeScope = 0;

/**
 * One application wrapper in document light DOM. Nested themes/ShadowRoots are
 * not supported. Owns a scoped sheet, not Base.css or component instances.
 * Bootstrap explicitly supplies paint factories for supported tag registrations.
 * Scope+tag rules beat legacy tag styles; stronger app/inline/!important rules
 * can still win. A mode change replaces this sheet and never recreates children.
 */
export class Theme extends HTMLElement {
  static get observedAttributes(): string[] { return ["mode"]; }
  static define(tagName: string): void { customElements.define(tagName, this); }
  #scope = `aui-theme-${++nextThemeScope}`;
  #sheet: CSSStyleSheet | null = null;
  #root: Document | null = null;
  #factories: readonly ThemeStyleFactory[] = [];

  get mode(): ThemeMode { return validateThemeMode(this.getAttribute("mode") ?? "light"); }
  set mode(value: ThemeMode) { this.setAttribute("mode", validateThemeMode(value)); }

  /** Replace the complete trusted factory list; no append-only mode accumulation. */
  setStyleFactories(factories: readonly ThemeStyleFactory[]): void {
    this.#factories = [...factories];
    this.#render();
  }

  connectedCallback(): void {
    const root = this.getRootNode();
    if (!(root instanceof Document) || this.parentElement?.closest("[data-aui-theme-scope]")) {
      throw new Error("Theme supports one document light-DOM application wrapper, not nested/Shadow themes");
    }
    this.#root = root;
    this.setAttribute("data-aui-theme-scope", this.#scope);
    this.#sheet ??= new CSSStyleSheet();
    this.#render();
    if (!root.adoptedStyleSheets.includes(this.#sheet)) {
      root.adoptedStyleSheets = [...root.adoptedStyleSheets, this.#sheet];
    }
  }

  disconnectedCallback(): void {
    if (this.#root && this.#sheet) {
      this.#root.adoptedStyleSheets = this.#root.adoptedStyleSheets.filter(sheet => sheet !== this.#sheet);
    }
    this.#root = null;
  }

  attributeChangedCallback(name: string, previous: string | null, next: string | null): void {
    if (name === "mode" && previous !== next) this.#render();
  }

  #render(): void {
    if (!this.#sheet) return;
    const colors = resolveThemeColors(this.mode);
    const scope = `[data-aui-theme-scope="${this.#scope}"]`;
    this.#sheet.replaceSync(`
      ${scope} {
        display: block;
        min-height: 100vh;
        color-scheme: ${this.mode};
        color: ${colors.text};
        background: ${colors.background};
        font-size: ${themeTypography.body};
      }
      ${this.#factories.map(factory => factory(scope, colors)).join("\n")}
    `);
  }
}
