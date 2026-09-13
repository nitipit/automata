const globals = globalThis as unknown as Record<string, unknown>;
const originalHTMLElement = globals.HTMLElement;
const originalCSSStyleSheet = globals.CSSStyleSheet;

globals.HTMLElement = class {};
globals.CSSStyleSheet = class {
  cssRules: CSSRule[] = [];
  replaceSync(_css: string): void {}
};

const { Base } = await import("./base.ts");

restoreGlobal("HTMLElement", originalHTMLElement);
restoreGlobal("CSSStyleSheet", originalCSSStyleSheet);

type TestData = { label: string };
type TestComponentConstructor = {
  new (): TestComponent;
  readonly name: string;
  readonly tagName?: string;
  validateData(data: unknown): TestData;
};
type CreateForTest = (
  this: TestComponentConstructor,
  options?: { data?: unknown; children?: Iterable<Node | string> },
) => TestComponent;

const create = Base.create as unknown as CreateForTest;

Deno.test("Base.create requires registration before construction", () => {
  class UnregisteredComponent extends TestComponent {
    static override tagName = undefined;
  }

  let message = "";
  try {
    create.call(UnregisteredComponent);
  } catch (error) {
    message = error instanceof Error ? error.message : String(error);
  }

  assert(message.includes(".define(tagName) before .create()"));
});

Deno.test("Base.create validates data and appends children", () => {
  const element = create.call(TestComponent, {
    data: { label: "preview" },
    children: ["first", "second"],
  });

  assert(element.data?.label === "PREVIEW");
  assert(element.children.join(",") === "first,second");
  assert(element.events.join(",") === "data,children");
});

class TestComponent {
  static tagName: string | undefined = "test-component";
  data?: TestData;
  children: Array<Node | string> = [];
  events: string[] = [];

  static validateData(data: unknown): TestData {
    const label = (data as { label?: unknown } | undefined)?.label;
    if (typeof label !== "string") {
      throw new Error("label must be a string");
    }
    return { label: label.toUpperCase() };
  }

  applyData(data: TestData): void {
    this.data = data;
    this.events.push("data");
  }

  append(...children: Array<Node | string>): void {
    this.children.push(...children);
    this.events.push("children");
  }
}

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
