import { Adapter } from "../_lib/adapter.bundle.js";
import { typography } from "../_tokens/primitives/typography.js";
import { tokens } from "../tokens.js";

export type ComponentChild = Node | string;

export type CreateOptions<Data> = {
  data?: Data;
  children?: Iterable<ComponentChild>;
};

type ComponentClass<Data, Element extends Base<Data>> = {
  new (): Element;
  readonly name: string;
  readonly tagName?: string;
  validateData(data: unknown): Data;
};

/** Shared Adapter baseline and creation contract for catalog components. */
export class Base<Data = unknown> extends Adapter {
  static {
    this.css = `
      box-sizing: border-box;
      font-family: ${typography.family};
      line-height: ${typography.lineHeight};
      color: ${tokens.text};
    `;
  }

  /**
   * Override to validate and normalize creation input, which may be undefined.
   * Return the data expected by applyData(), or throw to abort create().
   * The base implementation passes input through without validation.
   */
  static validateData(data: unknown): unknown {
    return data;
  }

  /**
   * Requires define(tagName) registration. Constructs a detached element, then
   * validates input, applies data, and appends supplied children in that order.
   * Validation errors propagate; construction has already occurred at that point.
   */
  static create<Data, Element extends Base<Data>>(
    this: ComponentClass<Data, Element>,
    options: CreateOptions<Data> = {},
  ): Element {
    if (!this.tagName) {
      throw new Error(
        `${this.name} must be registered with .define(tagName) before .create()`,
      );
    }

    const element = new this();
    element.applyData(this.validateData(options.data));
    element.append(...(options.children ?? []));
    return element;
  }

  /**
   * Override to apply normalized data; the base hook does nothing.
   * create() calls this before attachment and before appending supplied children.
   * Direct callers must validate first; this hook does not run validateData().
   */
  applyData(_data: Data): void {}
}
