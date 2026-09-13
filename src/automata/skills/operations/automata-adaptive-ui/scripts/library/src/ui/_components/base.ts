import { Adapter } from "../_lib/adapter.bundle.js";
import { typography } from "../_tokens/primitives/typography.js";

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
      color: inherit;
    `;
  }

  static validateData(data: unknown): unknown {
    return data;
  }

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

  applyData(_data: Data): void {}
}
