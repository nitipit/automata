import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import path from "node:path";
assert.ok(process.env.PLAYSPACE_LIB, "Set PLAYSPACE_LIB to the compiled public lib directory (builder --validate does this)");
export const load = name => import(pathToFileURL(path.join(process.env.PLAYSPACE_LIB, name)));

/** Narrow DOM fake for component admission/lifecycle, not browser rendering evidence. */
export class FakeNode {
  children = []; parentNode = null; listeners = new Map(); attributes = new Map();
  className = ""; id = ""; value = ""; textContent = ""; isConnected = true; adoptedStyleSheets = [];
  constructor(tagName = "div") { this.tagName = tagName; }
  append(...nodes) { for (const node of nodes) { node.parentNode = this; this.children.push(node); } }
  remove() { if (this.parentNode) this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null; }
  replaceChildren(...nodes) { for (const child of this.children) child.parentNode = null; this.children = []; this.append(...nodes); }
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
export function installDOM() {
  globalThis.HTMLElement = FakeNode;
  globalThis.CustomEvent = FakeEvent;
  globalThis.CSSStyleSheet = class { cssRules = []; replaceSync() {} };
  globalThis.MutationObserver = class { observe() {} disconnect() {} };
  globalThis.document = Object.assign(new FakeNode("document"), { adoptedStyleSheets: [], createElement: tag => new FakeNode(tag) });
  const definitions = new Map();
  globalThis.customElements = { get: tag => definitions.get(tag), define: (tag, value) => definitions.set(tag, value) };
}
