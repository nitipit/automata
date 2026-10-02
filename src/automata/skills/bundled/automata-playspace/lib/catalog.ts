/** Descriptive publication, not a second schema system. Canonical owners admit examples. */
import { builtins } from "./registry.js";
import { chatDefinition } from "./chat.schema.js";
import { cloneJSON, component, event, selector, validateComponent, validateEvent,
  componentContract, eventContract } from "./contracts.js";
import type { ComponentDefinition, DefinitionCatalog, Instance } from "./types.js";

export const roots = Object.freeze({ "ps-chat": chatDefinition });

export function generateCatalog() {
  const definitions = { ...builtins, ...roots };
  const knownContracts = new Set(Object.values(definitions).map(item => item.contract));
  const entries = Object.entries(definitions).map(([name, definition]) => {
    const catalog: DefinitionCatalog = definition.catalog;
    if (!catalog) throw new Error(`Missing descriptive metadata for ${name}`);
    const id = `example-${name}`;
    const renderable = Object.hasOwn(builtins, name);
    const props = renderable ? validateComponent(component(name, catalog.propsExample, id), builtins).data.props :
      cloneJSON(definition.validate(catalog.propsExample));
    const supportedEvents = Object.keys(definition.events ?? {}).sort();
    if (Object.keys(catalog.eventExamples ?? {}).sort().join() !== supportedEvents.join())
      throw new Error(`Every supported event requires a canonical example: ${name}`);
    const eventExamples = supportedEvents.map(eventName => {
      const example = catalog.eventExamples[eventName];
      const componentDefinition = definition as ComponentDefinition;
      const state = example.state === undefined ? undefined :
        componentDefinition.validateState?.(props, example.state);
      if (example.state !== undefined && state === undefined) throw new Error(`Missing state validator: ${name}`);
      const instance: Instance = { name, props, state, contracts: knownContracts };
      const payload = validateEvent(event(eventName, selector(name, id), example.detail), definitions,
        new Map([[id, instance]]));
      return { payload, ...(state === undefined ? {} : { prerequisiteState: cloneJSON(state) }) };
    });
    return { name, kind: renderable ? "component" : "root", renderable,
      description: catalog.description, contract: definition.contract, sources: catalog.sources,
      supportedEvents,
      example: renderable ? component(name, props, id) : { id, settings: props }, eventExamples };
  });
  return cloneJSON({ version: 1,
    authority: "Descriptive examples only; canonical module validators own acceptance. Catalog grants no permissions.",
    envelopes: { component: componentContract, event: eventContract, source: "./lib/contracts.js" },
    entries });
}
