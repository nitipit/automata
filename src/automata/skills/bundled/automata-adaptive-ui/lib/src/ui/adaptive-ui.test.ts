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

Deno.test("public Button/Card/Form validators expose normalized contracts", () => {
  const button: import("./adaptive-ui.ts").ButtonData = ui.validateButtonData({ label: "Save" });
  const card: import("./adaptive-ui.ts").CardData = ui.validateCardData({});
  assert(button.disabled === false && button.tone === "primary");
  assert(card.variant === "surface" && card.padding === "md");
  assert(typeof ui.validateFormData === "function");
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
    "actionText", "danger", "focus", "status", "messageAgentSurface",
    "messageAgentText", "messageUserSurface", "messageUserText",
  ] as const) {
    assert(ui.tokens[role].startsWith("var(--aui-"));
    assert(ui.tokens[role].includes(", "));
  }
  assert(ui.tokens.action === "var(--aui-action, #1c71d8)");
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
