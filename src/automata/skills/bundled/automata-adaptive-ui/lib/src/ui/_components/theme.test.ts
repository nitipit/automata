import { buttonThemeStyles } from "./button.tokens.ts";
import { cardThemeStyles } from "./card.tokens.ts";
import { resolveThemeColors } from "../theme.tokens.ts";

const globals = globalThis as unknown as Record<string, unknown>;
const names = ["HTMLElement", "Document", "CSSStyleSheet"];
const originals = names.map(name => globals[name]);
class FakeSheet {
  text = "";
  replacements = 0;
  replaceSync(text: string): void { this.text = text; this.replacements++; }
}
class FakeDocument { adoptedStyleSheets: FakeSheet[] = []; }
const root = new FakeDocument();
class FakeElement {
  attributes = new Map<string, string>();
  parentElement = null;
  getRootNode(): FakeDocument { return root; }
  getAttribute(name: string): string | null { return this.attributes.get(name) ?? null; }
  setAttribute(name: string, value: string): void {
    const previous = this.getAttribute(name);
    this.attributes.set(name, value);
    (this as unknown as { attributeChangedCallback(name: string, a: string | null, b: string): void })
      .attributeChangedCallback(name, previous, value);
  }
}
install();
const { Theme } = await import("./theme.ts");
restore();

Deno.test("Theme replaces one scoped concrete sheet and cleans up only its own sheet", () => {
  install();
  const unrelated = new FakeSheet();
  root.adoptedStyleSheets = [unrelated];
  try {
    const theme = new Theme();
    theme.setStyleFactories([
      (scope, colors) => buttonThemeStyles(scope, colors, "ui-button"),
      (scope, colors) => cardThemeStyles(scope, colors, "ui-card"),
    ]);
    theme.connectedCallback();
    const sheet = root.adoptedStyleSheets[1];
    const initial = sheet.text;
    const scope = `[data-aui-theme-scope="${theme.getAttribute("data-aui-theme-scope")}"]`;
    assert(initial.includes(`${scope} ui-button button`));
    assert(initial.includes(`${scope} ui-card`));
    assert(!initial.includes("var(") && !/--[a-z-]+\s*:/.test(initial));
    theme.mode = "dark";
    assert(root.adoptedStyleSheets.length === 2 && root.adoptedStyleSheets[1] === sheet);
    assert(sheet.text !== initial && sheet.text.includes(resolveThemeColors("dark").surface));
    theme.mode = "light";
    assert(sheet.text === initial && sheet.replacements === 3);
    theme.disconnectedCallback();
    assert(root.adoptedStyleSheets.length === 1 && root.adoptedStyleSheets[0] === unrelated);
    theme.connectedCallback();
    assert(root.adoptedStyleSheets[1] === sheet);
    theme.disconnectedCallback();
    let rejected = false;
    try { resolveThemeColors("sepia" as "light"); } catch { rejected = true; }
    assert(rejected);
  } finally {
    root.adoptedStyleSheets = [];
    restore();
  }
});

function assert(value: unknown): void {
  if (!value) throw new Error("Theme lifecycle/scoping contract failed");
}
function install(): void {
  globals.HTMLElement = FakeElement;
  globals.Document = FakeDocument;
  globals.CSSStyleSheet = FakeSheet;
}
function restore(): void {
  names.forEach((name, index) => {
    if (originals[index] === undefined) delete globals[name];
    else globals[name] = originals[index];
  });
}
