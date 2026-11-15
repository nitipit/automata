import { Adapter } from "@devcapsule/adapter";
import { bindTheme, nearestTheme, type ThemeRef, type ResolvedTheme } from "../_theme/index";
import { baseStyle } from "./base.style";

/** Thin theme/lifecycle layer; descendants own their controls, DOM and event semantics. */
export class Base extends Adapter {
  private explicitTheme?: ThemeRef;
  private unbindTheme?: () => void;
  private styleRoot?: Document | ShadowRoot;

  get theme(): ThemeRef { return this.explicitTheme ?? nearestTheme(this); }
  set theme(reference: ThemeRef | undefined) {
    this.explicitTheme = reference;
    if (this.isConnected) this.connectTheme();
  }
  protected themedStyle(_theme: ResolvedTheme): string { return ""; }
  /** Reapply themed CSS after a component-local state change without replacing its DOM. */
  refreshTheme() {
    if (this.isConnected) this.applyTheme(this.theme.value);
  }
  private applyTheme(theme: ResolvedTheme) {
    this.css = `color: ${theme.roles.text}; color-scheme: ${theme.mode}; ${this.themedStyle(theme)}`;
  }
  private connectTheme() {
    this.unbindTheme?.();
    this.unbindTheme = bindTheme(this, theme => this.applyTheme(theme), this.explicitTheme);
  }
  override connectedCallback() {
    super.connectedCallback();
    this.styleRoot = this.getRootNode() as Document | ShadowRoot;
    this._adapter.cssObserve(true);
    this.connectTheme();
  }
  disconnectedCallback() {
    this.unbindTheme?.();
    this.unbindTheme = undefined;
    this._adapter.cssObserve(false);
    const root = this.styleRoot;
    if (root) root.adoptedStyleSheets = root.adoptedStyleSheets.filter(sheet => sheet !== this._adapter.cssStyleSheet);
    this.styleRoot = undefined;
  }
  /** Adapter4.remove() assumes a connected root and may splice(-1); native removal invokes our cleanup. */
  override remove() { HTMLElement.prototype.remove.call(this); }
}
Base.css = baseStyle;
