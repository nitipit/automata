export type ComponentDescriptor<Data = unknown> = {
  readonly _class: string;
  readonly _data?: Data;
  readonly _children?: readonly ComponentDescriptor[];
};

export type NamedComponentDescriptor<Data = unknown> =
  Omit<ComponentDescriptor<Data>, "_class"> & { readonly _class?: string };

type Build = (data: unknown, children: readonly HTMLElement[]) => HTMLElement;
const descriptorKeys = new Set<PropertyKey>(["_class", "_data", "_children"]);

function descriptorFields(input: unknown, path: string) {
  if (input === null || typeof input !== "object") {
    throw new TypeError(`${path} must be a component descriptor object`);
  }
  const prototype = Object.getPrototypeOf(input);
  if (prototype !== null && prototype !== Object.prototype) {
    throw new TypeError(`${path} must be a plain component descriptor object`);
  }
  const fields = Object.getOwnPropertyDescriptors(input);
  for (const key of Reflect.ownKeys(fields)) {
    if (!descriptorKeys.has(key)) throw new TypeError(`${path}: unknown descriptor key ${String(key)}`);
    if (!("value" in fields[key as string])) throw new TypeError(`${path}.${String(key)} must be a value, not an accessor`);
  }
  return fields;
}

function makeRegistry(shared?: (tag: string) => Build | undefined) {
  const entries = new Map<string, Build>();
  const find = (tag: string) => entries.get(tag) ?? shared?.(tag);

  function build(input: unknown, path: string, active: Set<unknown>, expected?: string): HTMLElement {
    const fields = descriptorFields(input, path);
    const tag: unknown = Object.hasOwn(fields, "_class") ? fields._class.value : expected;
    if (typeof tag !== "string" || tag.length === 0) throw new TypeError(`${path}._class must be a custom element tag name`);
    if (expected !== undefined && tag !== expected) {
      throw new TypeError(`${path}._class ${JSON.stringify(tag)} does not match named factory ${JSON.stringify(expected)}`);
    }
    const initialize = find(tag);
    if (!initialize) throw new TypeError(`${path}: unknown component tag ${JSON.stringify(tag)}`);
    const descriptions: unknown = Object.hasOwn(fields, "_children") ? fields._children.value : undefined;
    if (descriptions !== undefined && !Array.isArray(descriptions)) throw new TypeError(`${path}._children must be an array of descriptors`);
    if (active.has(input)) throw new TypeError(`${path}: cyclic component descriptor`);

    active.add(input);
    try {
      const children: HTMLElement[] = [];
      if (descriptions !== undefined) {
        for (let index = 0; index < descriptions.length; index++) {
          const childPath = `${path}._children[${index}]`;
          const child = Object.getOwnPropertyDescriptor(descriptions, index);
          if (!child || !("value" in child)) throw new TypeError(`${childPath} must contain a component descriptor value`);
          children.push(build(child.value, childPath, active));
        }
      }
      return initialize(Object.hasOwn(fields, "_data") ? fields._data.value : undefined, children);
    } finally {
      active.delete(input);
    }
  }

  return {
    find,
    create(descriptor: ComponentDescriptor): HTMLElement {
      return build(descriptor, "descriptor", new Set());
    },
    register<Element extends HTMLElement, Data = unknown>(
      tag: string,
      constructor: new () => Element,
      initialize: (element: Element, data: Data | undefined, children: readonly HTMLElement[]) => void,
    ): (descriptor?: NamedComponentDescriptor<Data>) => Element {
      if (customElements.get(tag) !== constructor) throw new TypeError(`${JSON.stringify(tag)} is not defined for that component class`);
      if (find(tag)) throw new TypeError(`Component tag ${JSON.stringify(tag)} is already registered in this scope`);
      entries.set(tag, (data, children) => {
        const element = new constructor();
        // Only the registered component interprets data and chooses where to put children.
        initialize(element, data as Data | undefined, children);
        return element;
      });
      return (descriptor = {}) => build(descriptor, "descriptor", new Set(), tag) as Element;
    },
  };
}

const shared = makeRegistry();
export const createComponent = shared.create;
export const registerSharedComponent = shared.register;

/** Private app scopes see shared widgets. Shared and sibling scopes cannot see their local tags. */
export function createComponentRegistry() {
  const { create, register } = makeRegistry(shared.find);
  return { create, register };
}
