const globals = globalThis as unknown as Record<string, unknown>;
const originalHTMLElement = globals.HTMLElement;
const originalCSSStyleSheet = globals.CSSStyleSheet;

globals.HTMLElement = class {};
globals.CSSStyleSheet = class {
  cssRules: CSSRule[] = [];
  replaceSync(_css: string): void {}
};

const ui = await import("./adaptive-ui.ts");

restoreGlobal("HTMLElement", originalHTMLElement);
restoreGlobal("CSSStyleSheet", originalCSSStyleSheet);

Deno.test("Adaptive UI exports Chat and Arrow reactive primitives", () => {
  assert(typeof ui.Chat === "function");
  assert(typeof ui.validateChatData === "function");
  for (
    const primitive of [
      ui.component,
      ui.html,
      ui.nextTick,
      ui.onCleanup,
      ui.reactive,
    ]
  ) {
    assert(typeof primitive === "function");
  }

  const state = ui.reactive({ count: 0 });
  state.count++;
  assert(state.count === 1);
});

function restoreGlobal(name: string, original: unknown): void {
  if (original === undefined) {
    delete globals[name];
  } else {
    globals[name] = original;
  }
}

function assert(
  condition: unknown,
  message = "Assertion failed",
): asserts condition {
  if (!condition) {
    throw new Error(message);
  }
}
