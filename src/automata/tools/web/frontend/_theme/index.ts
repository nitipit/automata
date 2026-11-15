import { reactive, watch } from "@arrow-js/core";
import { clampGamut, formatHex, parse, toGamut } from "culori";
import { palette } from "../_tokens/color";
import { semanticRoles, type ResolvedTheme, type SemanticRoles, type ThemeOverrides } from "./roles";
export { semanticRoles } from "./roles";
export type { ThemeMode, ThemeOverrides, ResolvedTheme, SemanticRoles } from "./roles";

const media = typeof matchMedia === "function" ? matchMedia("(prefers-color-scheme: dark)") : undefined;
const system = reactive({ dark: media?.matches ?? false });
media?.addEventListener("change", event => { system.dark = event.matches; });
const mapColor = toGamut("rgb"), clamp = clampGamut("rgb");
function normalize(overrides: ThemeOverrides): ThemeOverrides {
  if (overrides.mode !== undefined && !["light", "dark", "system"].includes(overrides.mode)) throw new TypeError("Invalid theme mode");
  if (overrides.accent !== undefined && !Object.hasOwn(palette, overrides.accent)) throw new TypeError("Invalid theme accent");
  const roles: Partial<SemanticRoles> = {};
  for (const [key, value] of Object.entries(overrides.roles ?? {})) {
    if (value === undefined) continue;
    if (!Object.hasOwn(semanticRoles("light", "green"), key)) throw new TypeError(`Unknown semantic role: ${key}`);
    const color = typeof value === "string" ? parse(value) : undefined;
    if (!color || (color.alpha !== undefined && color.alpha !== 1)) throw new TypeError(`Role ${key} requires an opaque literal color`);
    roles[key as keyof SemanticRoles] = formatHex(clamp(mapColor(color)))!;
  }
  return { mode: overrides.mode, accent: overrides.accent, roles };
}

/** ArrowJS-backed reference. set() replaces overrides; omitted keys restore inheritance. */
export class ThemeRef {
  private revision = reactive({ value: 0 });
  private overrides: ThemeOverrides;
  private parent?: ThemeRef;
  constructor(overrides: ThemeOverrides = {}, parent?: ThemeRef) {
    this.overrides = normalize(overrides);
    this.parent = parent;
  }
  set(overrides: ThemeOverrides = {}) { this.overrides = normalize(overrides); this.revision.value++; }
  /** Scope infrastructure updates ancestry; normal callers use createTheme/setTheme. */
  setParent(parent?: ThemeRef) {
    for (let ref = parent; ref; ref = ref.parent) if (ref === this) throw new TypeError("Cyclic theme inheritance");
    if (parent !== this.parent) { this.parent = parent; this.revision.value++; }
  }
  private get inputs(): Required<ThemeOverrides> {
    this.revision.value;
    const parent = this.parent?.inputs ?? { mode: "system", accent: "green", roles: {} };
    return {
      mode: this.overrides.mode ?? parent.mode,
      accent: this.overrides.accent ?? parent.accent,
      roles: { ...parent.roles, ...this.overrides.roles },
    };
  }
  get value(): ResolvedTheme {
    const { mode, accent, roles } = this.inputs;
    const resolvedMode = mode === "system" ? (system.dark ? "dark" : "light") : mode;
    return { mode: resolvedMode, accent, roles: { ...semanticRoles(resolvedMode, accent), ...roles } };
  }
}
export const appTheme = new ThemeRef();
export function createTheme(overrides: ThemeOverrides = {}, parent: ThemeRef = appTheme) { return new ThemeRef(overrides, parent); }

type Scope = { ref: ThemeRef; automatic: boolean };
const scopes = new WeakMap<Element, Scope>();
/** Composed ancestry includes slots and crosses closed/open ShadowRoot boundaries from inside. */
function parentOf(node: Node): Node | null {
  if (node instanceof Element && node.assignedSlot) return node.assignedSlot;
  return node.parentNode ?? (node instanceof ShadowRoot ? node.host : null);
}
function ancestry(host: Element): Node[] {
  const nodes: Node[] = [];
  for (let node: Node | null = host; node; node = parentOf(node)) nodes.push(node);
  return nodes;
}
function resolveNearest(host: Element): ThemeRef {
  const nodes = ancestry(host).reverse();
  let parent = appTheme;
  for (const node of nodes) {
    if (!(node instanceof Element)) continue;
    const scope = scopes.get(node);
    if (scope) {
      if (scope.automatic) scope.ref.setParent(parent);
      parent = scope.ref;
    }
  }
  return parent;
}
export function nearestTheme(host: Element): ThemeRef { return resolveNearest(host); }

type Binding = { host: Element; callback: (theme: ResolvedTheme) => void; explicit?: ThemeRef; ref?: ThemeRef; stop?: () => void };
const bindings = new Set<Binding>();
const observers = new Map<Document | ShadowRoot, MutationObserver>();
let queued = false;
function scheduleRefresh() {
  if (queued) return;
  queued = true;
  queueMicrotask(() => { queued = false; refreshBindings(); });
}
function syncObservers() {
  const roots = new Set<Document | ShadowRoot>();
  for (const binding of bindings) {
    if (binding.explicit) continue;
    for (const node of ancestry(binding.host)) {
      const root = node.getRootNode();
      if (root instanceof Document || root instanceof ShadowRoot) roots.add(root);
    }
  }
  for (const [root, observer] of observers) if (!roots.has(root)) {
    observer.disconnect(); root.removeEventListener("slotchange", scheduleRefresh); observers.delete(root);
  }
  for (const root of roots) if (!observers.has(root)) {
    const observer = new MutationObserver(scheduleRefresh);
    observer.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ["slot", "name"] });
    root.addEventListener("slotchange", scheduleRefresh);
    observers.set(root, observer);
  }
}
function refreshBinding(binding: Binding) {
  const ref = binding.explicit ?? resolveNearest(binding.host);
  if (binding.ref === ref) return;
  binding.stop?.();
  binding.ref = ref;
  // ArrowJS1.0.6 stop() does not cancel an already queued effect. A disposed
  // effect must read no reactive inputs, or it can re-register null listeners.
  let active = true;
  const [, stop] = watch(() => active ? ref.value : undefined, value => {
    if (active && value) binding.callback(value);
  });
  binding.stop = () => { active = false; stop(); };
}
function refreshBindings() {
  for (const binding of bindings) refreshBinding(binding);
  syncObservers();
}
/** Apply a local partial scope, or an existing explicit reference. Scope removal restores nearest inheritance. */
export function setTheme(host: Element, theme: ThemeOverrides | ThemeRef): ThemeRef {
  let scope = scopes.get(host);
  if (theme instanceof ThemeRef) scope = { ref: theme, automatic: false };
  else if (scope?.automatic) scope.ref.set(theme);
  else scope = { ref: createTheme(theme), automatic: true };
  scopes.set(host, scope!);
  resolveNearest(host);
  refreshBindings();
  return scope!.ref;
}
export function clearTheme(host: Element) { scopes.delete(host); refreshBindings(); }
/** Caller owns the returned cleanup; Base supplies automatic connect/disconnect ownership. */
export function bindTheme(host: Element, callback: (theme: ResolvedTheme) => void, explicit?: ThemeRef): () => void {
  const binding: Binding = { host, callback, explicit };
  bindings.add(binding);
  try { refreshBinding(binding); syncObservers(); }
  catch (error) { bindings.delete(binding); binding.stop?.(); syncObservers(); throw error; }
  return () => { binding.stop?.(); bindings.delete(binding); syncObservers(); };
}
/** Diagnostics for focused lifecycle tests; no observer handles or retained DOM exposed. */
export function themeDiagnostics() { return { bindings: bindings.size, observedRoots: observers.size }; }
