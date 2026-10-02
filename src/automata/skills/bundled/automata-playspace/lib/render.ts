import { cloneJSON, ContractError } from "./contracts.js";
import { validateDefinition } from "./definitions.js";
import { validateSnapshot } from "./state.js";
import type { ComponentDefinition, ComponentEvent, ComponentHandle, DefinitionSource,
  DraftInstance, DraftSnapshot } from "./types.js";

type Mounted = {
  record: DraftInstance;
  definition: ComponentDefinition;
  handle: ComponentHandle;
  active: boolean;
};

/** An owned flat component surface, independent of Cache API and Router. */
export function createPlayspace({ root, loadDefinition, onEvent = () => {},
  onChange = () => {}, onError = () => {} }: {
  root: HTMLElement;
  loadDefinition(record: DefinitionSource): ComponentDefinition;
  onEvent?: (event: ComponentEvent) => void;
  onChange?: () => void;
  onError?: (error: ContractError) => void;
}) {
  let alive = true;
  let sources: DefinitionSource[] = [];
  let mounted: Mounted[] = [];
  // Exact revision reuse avoids re-registering custom elements on restore/update.
  const definitions = new Map<string, ComponentDefinition>();
  const report = (contract: string, hint: string) => {
    try { onError(new ContractError(contract, hint)); } catch { /* observer only */ }
  };
  const changed = () => {
    try { onChange(); } catch { report("Page callback", "Change observer failed"); }
  };
  const ensureAlive = () => {
    if (!alive) throw new ContractError("Playspace", "Runtime is disposed");
  };
  function release(item: Mounted) {
    item.active = false;
    try { item.handle.dispose(); }
    catch { report("Component lifecycle", "Dispose failed; remaining cleanup continues"); }
  }
  function normalize(record: DraftInstance, definition: ComponentDefinition): DraftInstance {
    const props = cloneJSON(definition.validateProps(cloneJSON(record.props)));
    const state = cloneJSON(definition.validateState(cloneJSON(props), cloneJSON(record.state)));
    return { ...record, props, state };
  }
  function readState(item: Mounted) {
    return cloneJSON(item.definition.validateState(cloneJSON(item.record.props),
      cloneJSON(item.handle.snapshot())));
  }
  function stage(record: DraftInstance, definition: ComponentDefinition): Mounted {
    const item: Mounted = { record, definition, handle: undefined!, active: false };
    const current = () => alive && item.active;
    const handle = definition.create(cloneJSON(record.props), {
      id: record.id, state: cloneJSON(record.state),
      emit(name, value) {
        if (!current()) return;
        try {
          if (!Object.hasOwn(definition.events, name)) {
            throw new ContractError("Component event", "Unsupported event name");
          }
          const payload = cloneJSON(definition.events[name](cloneJSON(value)));
          onEvent({ id: record.id, name, payload, isCurrent: current });
        } catch { report("Component event", "Event validation or page callback failed"); }
      },
      changed() { if (current()) changed(); },
    });
    // A factory owns cleanup until it returns. After return, even invalid handles
    // with a disposer are released before admission fails.
    if (!handle || !(handle.element instanceof HTMLElement) ||
        typeof handle.snapshot !== "function" || typeof handle.dispose !== "function") {
      try { handle?.dispose?.(); } catch { report("Component lifecycle", "Invalid handle cleanup failed"); }
      throw new ContractError("Component handle", "Element, snapshot and dispose required");
    }
    item.handle = handle;
    try { readState(item); }
    catch (error) { release(item); throw error; }
    return item;
  }
  function replace(value: unknown) {
    ensureAlive();
    const candidate = validateSnapshot(value); // before any executable loading
    const registry = new Map<string, ComponentDefinition>();
    for (const source of candidate.definitions) {
      const key = JSON.stringify(source);
      let definition = definitions.get(key);
      if (!definition) {
        definition = validateDefinition(loadDefinition({ ...source }));
        definitions.set(key, definition);
      }
      registry.set(source.id, definition);
    }
    // Admit every instance before constructing any instance.
    const records = candidate.layout.map(record => normalize(record, registry.get(record.definition)!));
    const staged: Mounted[] = [];
    try {
      for (const record of records) staged.push(stage(record, registry.get(record.definition)!));
    } catch (error) {
      staged.forEach(release);
      throw error;
    }
    const previous = mounted;
    previous.forEach(item => { item.active = false; });
    try { root.replaceChildren(...staged.map(item => item.handle.element)); }
    catch (error) {
      previous.forEach(item => { item.active = true; });
      staged.forEach(release);
      throw error;
    }
    mounted = staged;
    sources = candidate.definitions;
    staged.forEach(item => { item.active = true; });
    previous.forEach(release);
    changed();
  }
  function update(id: string, value: unknown) {
    ensureAlive();
    const index = mounted.findIndex(item => item.record.id === id);
    if (index < 0) throw new ContractError("Component update", "Unknown instance");
    const previous = mounted[index];
    const state = previous.definition.update(cloneJSON(previous.record.props),
      readState(previous), cloneJSON(value));
    const record = normalize({ ...previous.record, state }, previous.definition);
    const candidate = stage(record, previous.definition);
    previous.active = false;
    try { root.replaceChild(candidate.handle.element, previous.handle.element); }
    catch (error) { previous.active = true; release(candidate); throw error; }
    mounted[index] = candidate;
    candidate.active = true;
    release(previous);
    changed();
  }
  function snapshot(): DraftSnapshot {
    ensureAlive();
    return validateSnapshot({ version: 1, definitions: sources,
      layout: mounted.map(item => ({ ...item.record, state: readState(item) })) });
  }
  return {
    replace, update, snapshot,
    dispose() {
      if (!alive) return;
      alive = false;
      mounted.forEach(release);
      mounted = [];
      definitions.clear();
      root.replaceChildren();
    },
  };
}
