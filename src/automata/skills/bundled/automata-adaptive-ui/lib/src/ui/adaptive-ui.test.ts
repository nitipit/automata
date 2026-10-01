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

Deno.test("Adaptive UI exports catalog and Arrow primitives, not Playspace Chat", () => {
  assert(!("Chat" in ui));
  assert(!("validateChatData" in ui));
  assert(typeof ui.Base === "function");
  assert(typeof ui.Form === "function");
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

Deno.test("public Edictor exports validate custom component data", () => {
  class DraftDataModel extends ui.Model {}

  DraftDataModel.define({
    choice: ui.defineField({ initial: "keep" })
      .instance("string")
      .assert(
        (value: unknown) => value === "keep" || value === "revise",
        "Unsupported draft choice",
      ),
  });

  const defaults = DraftDataModel.validate({}) as { choice: string };
  const revised = DraftDataModel.validate({ choice: "revise" }) as {
    choice: string;
  };
  assert(defaults.choice === "keep");
  assert(revised.choice === "revise");
  const invalidInputs = [
    { choice: 1 },
    { choice: "unknown" },
    { extra: true },
  ];
  for (const invalid of invalidInputs) {
    let rejected = false;
    try {
      DraftDataModel.validate(invalid);
    } catch {
      rejected = true;
    }
    assert(rejected, "Custom data should reject invalid fields and values");
  }
});

Deno.test("public semantic tokens use overridable CSS values with defaults", () => {
  for (const role of [
    "surface", "text", "mutedText", "border", "action", "actionHover",
    "actionText", "danger", "focus", "status",
  ] as const) {
    assert(ui.tokens[role].startsWith("var(--aui-"));
    assert(ui.tokens[role].includes(", "));
  }
  assert(ui.tokens.action === "var(--aui-action, #2563eb)");
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
