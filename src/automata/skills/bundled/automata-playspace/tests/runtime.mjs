import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import path from "node:path";
assert.ok(process.env.PLAYSPACE_LIB, "Set PLAYSPACE_LIB to the compiled public lib directory (builder --validate does this)");
export const load = name => import(pathToFileURL(path.join(process.env.PLAYSPACE_LIB, name)));

/** Narrow DOM fake for component admission/lifecycle, not browser rendering evidence. */
export class FakeNode {
  children = []; parentNode = null; listeners = new Map(); attributes = new Map();
  className = ""; id = ""; value = ""; textContent = ""; isConnected = true; adoptedStyleSheets = [];
  style = {}; scrollHeight = 40;
  constructor(tagName = "div") { this.tagName = tagName; }
  append(...nodes) { for (const node of nodes) { node.parentNode = this; this.children.push(node); } }
  remove() { if (this.parentNode) this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null; }
  replaceChildren(...nodes) { for (const child of this.children) child.parentNode = null; this.children = []; this.append(...nodes); }
  replaceChild(next, previous) {
    const index = this.children.indexOf(previous);
    if (index < 0) throw new Error("Not a child");
    previous.parentNode = null;
    next.parentNode = this;
    this.children[index] = next;
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  querySelectorAll(selector) {
    const parts = selector.split(" ");
    if (parts.length > 1) return this.querySelectorAll(parts[0]).flatMap(node => node.querySelectorAll(parts.slice(1).join(" ")));
    const matches = node => selector.startsWith(".") ? node.className.split(" ").includes(selector.slice(1)) : node.tagName === selector;
    return this.children.flatMap(child => [...(matches(child) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] ?? null; }
  getRootNode() { return this.parentNode?.getRootNode() ?? this; }
  addEventListener(name, listener) { if (!this.listeners.has(name)) this.listeners.set(name, new Set()); this.listeners.get(name).add(listener); }
  removeEventListener(name, listener) { this.listeners.get(name)?.delete(listener); }
  dispatchEvent(event) {
    event.target ??= this;
    for (const listener of this.listeners.get(event.type) ?? []) listener(event);
    if (event.bubbles && !event.stopped) this.parentNode?.dispatchEvent(event);
    return true;
  }
  emit(type, detail, bubbles = false) { this.dispatchEvent(new FakeEvent(type, { detail, bubbles })); }
}
class FakeEvent {
  constructor(type, init = {}) { this.type = type; Object.assign(this, init); }
  preventDefault() {}
  stopPropagation() { this.stopped = true; }
}
export const layout = {observers: [], listeners: new Map()};
export function installDOM() {
  globalThis.getComputedStyle = () => ({borderTopWidth:"1px", borderBottomWidth:"1px"});
  globalThis.addEventListener = (name, fn) => {
    if (!layout.listeners.has(name)) layout.listeners.set(name, new Set());
    layout.listeners.get(name).add(fn);
  };
  globalThis.removeEventListener = (name, fn) => layout.listeners.get(name)?.delete(fn);
  globalThis.ResizeObserver = class {
    constructor(callback) { this.callback = callback; layout.observers.push(this); }
    observe(element) { this.element = element; }
    disconnect() { this.disconnected = true; }
    fire(width) { this.callback([{contentRect:{width}}]); }
  };
  globalThis.HTMLElement = FakeNode;
  globalThis.CustomEvent = FakeEvent;
  globalThis.CSSStyleSheet = class { cssRules = []; replaceSync() {} };
  globalThis.MutationObserver = class { observe() {} disconnect() {} };
  globalThis.document = Object.assign(new FakeNode("document"), { adoptedStyleSheets: [], createElement: tag => new FakeNode(tag) });
  const definitions = new Map();
  globalThis.customElements = { get: tag => definitions.get(tag), define(tag, value) {
    if (definitions.has(tag)) throw new Error("Duplicate registration");
    definitions.set(tag, value);
  } };
  return { definitions };
}
