// @ts-types="./adaptive-ui.d.ts"
import { Model, defineField } from "./adaptive-ui.js";
import type { JSONValue, ComponentPayload, EventPayload, Registry, Instance } from "./types.js";

/** Canonical safe errors: never carry rejected values or exception text. */
export class ContractError extends Error {
  contract: string;
  fields: Record<string, string>;
  constructor(contract: string, fields: Record<string, string>) {
    super(`Contract: ${contract}\n${Object.entries(fields).map(([key, hint]) => `${key}: ${hint}`).join("\n")}`);
    this.contract = contract;
    this.fields = fields;
  }
}
export function isRecord(value: unknown): value is Record<string, any> {
  return !!value && typeof value === "object" && !Array.isArray(value) &&
    [Object.prototype, null].includes(Object.getPrototypeOf(value));
}
export function testModel(model: typeof Model, value: unknown, contract: string, hints: Record<string, string>): Record<string, any> {
  if (!isRecord(value)) throw new ContractError(contract, { $: "Expected an object" });
  if (Object.keys(value).some(key => !Object.hasOwn(hints, key))) {
    throw new ContractError(contract, { $: "Unknown field; consult the contract" });
  }
  const result = model.test(value);
  const errors = Object.keys(result.error);
  if (errors.length) throw new ContractError(contract, Object.fromEntries(errors.map(key =>
    [Object.hasOwn(hints, key) ? key : "$", hints[key] ?? "Unknown field"] )));
  return result.valid;
}
export function cloneJSON(value: unknown): JSONValue {
  const seen = new Set<object>();
  function check(v: unknown, depth: number): void {
    if (depth > 64) throw new Error("depth");
    if (v === null || typeof v === "string" || typeof v === "boolean") return;
    if (typeof v === "number" && Number.isFinite(v)) return;
    if (!v || typeof v !== "object" || seen.has(v) || (!Array.isArray(v) && !isRecord(v))) throw new Error("json");
    seen.add(v);
    for (const item of Array.isArray(v) ? v : Object.values(v)) check(item, depth + 1);
    seen.delete(v);
  }
  try { check(value, 0); return JSON.parse(JSON.stringify(value)); }
  catch { throw new ContractError("Playspace Serializable JSON (depth <=64)", { data: "JSON without cycles, undefined or live objects required" }); }
}

export const componentContract = "automata-playspace/lib/contracts.js: Component {type:'component',data:{name,id,props}}";
export const eventContract = "automata-playspace/lib/contracts.js: Event {type:'event',data:{name,target,detail}}";
export const safeId = (value: unknown): value is string => typeof value === "string" && /^[a-zA-Z][a-zA-Z0-9_-]{0,127}$/.test(value) && !["constructor", "prototype"].includes(value);
export const safeTag = (value: unknown): value is string => typeof value === "string" && /^ps-[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(value);
export const newId = (prefix: string): string => `${prefix}-${crypto.randomUUID()}`;
export function selector(name: string, id: string): string {
  if (!safeTag(name) || !safeId(id)) throw new ContractError(eventContract, { target: "Safe ps-tag#stable-id required" });
  return `${name}#${id}`;
}
export function parseTarget(value: unknown): { name: string; id: string } {
  if (typeof value !== "string") throw new ContractError(eventContract, { target: "Safe ps-tag#stable-id required" });
  const [name, id, extra] = value.split("#");
  if (extra !== undefined || !safeTag(name) || !safeId(id)) throw new ContractError(eventContract, { target: "Safe ps-tag#stable-id required; not arbitrary CSS" });
  return { name, id };
}
class EnvelopeModel extends Model {}
EnvelopeModel.define({ type: defineField({ required: true }), data: defineField({ required: true }) });
class ComponentModel extends Model {}
ComponentModel.define({ name: defineField({ required: true }), id: defineField({ required: true }), props: defineField({ required: true }) });
class EventModel extends Model {}
EventModel.define({ name: defineField({ required: true }), target: defineField({ required: true }), detail: defineField({ required: true }) });
export function validateComponent(value: unknown, registry: Registry): ComponentPayload {
  const envelope = testModel(EnvelopeModel, value, componentContract, { type: "component", data: "Required component data" });
  if (envelope.type !== "component") throw new ContractError(componentContract, { type: "Only component content is rendered" });
  const data = testModel(ComponentModel, envelope.data, componentContract, { name: "Trusted registered ps-tag", id: "Unique safe stable ID", props: "Component-owned props" });
  if (!safeTag(data.name) || !Object.hasOwn(registry, data.name)) throw new ContractError(componentContract, { "data.name": "Unknown trusted component" });
  if (!safeId(data.id)) throw new ContractError(componentContract, { "data.id": "Safe stable ID required" });
  const definition = registry[data.name];
  try { return { type: "component", data: { name: data.name, id: data.id, props: cloneJSON(definition.validate(data.props)) } }; }
  catch (error) {
    if (error instanceof ContractError) throw error;
    throw new ContractError(definition.contract, { props: "Component validation failed; consult canonical definition" });
  }
}
/** Resolve an inert convention through the supplied instance map, never querySelector/eval. */
export function validateEvent(value: unknown, registry: Record<string, Pick<Registry[string], "contract" | "events">>, instances: Map<string, Instance>): EventPayload {
  const envelope = testModel(EnvelopeModel, value, eventContract, { type: "event", data: "Required event data" });
  if (envelope.type !== "event") throw new ContractError(eventContract, { type: "Expected event" });
  const data = testModel(EventModel, envelope.data, eventContract, { name: "Component-owned event name", target: "Existing ps-tag#stable-id", detail: "Component-owned validated detail" });
  const { name, id } = parseTarget(data.target);
  const instance = instances.get(id);
  if (!instance || instance.name !== name || !Object.hasOwn(registry, name)) throw new ContractError(eventContract, { target: "Target must reference an existing registered instance" });
  const events = registry[name].events ?? {};
  if (typeof data.name !== "string" || !Object.hasOwn(events, data.name)) throw new ContractError(eventContract, { name: "Event unsupported by target component" });
  try { return { type: "event", data: { name: data.name, target: data.target, detail: cloneJSON(events[data.name](data.detail, instance)) } }; }
  catch (error) {
    if (error instanceof ContractError) throw error;
    throw new ContractError(registry[name].contract, { detail: "Component event validation failed" });
  }
}
export const component = (name: string, props: any, id = newId(name)): ComponentPayload => ({ type: "component", data: { name, id, props } });
export const text = (value: string, id?: string): ComponentPayload => component("ps-text", { text: value }, id);
export const json = (value: JSONValue, id?: string): ComponentPayload => component("ps-json", { value }, id);
export const event = (name: string, target: string, detail: any): EventPayload => ({ type: "event", data: { name, target, detail } });
export function emit(element: HTMLElement, payload: EventPayload): void {
  // Native event.target remains the emitting DOM element; wire target is separate.
  element.dispatchEvent(new CustomEvent("playspace-event", { bubbles: true, composed: true, detail: payload }));
}
