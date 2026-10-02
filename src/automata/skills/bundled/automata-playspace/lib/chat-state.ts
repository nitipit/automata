import { validateChatData, chatDefinition, chatContract } from "./chat.schema.js";
import type { Registry, Message, JSONValue, Instance, ChatSnapshot } from "./types.js";
import { ContractError, cloneJSON, isRecord, safeId, validateComponent, validateEvent, componentContract, eventContract } from "./contracts.js";

/** Root instance is a contract record, not cached executable code or a DOM capability. */
export function chatInstances(id: string, messages: Message[], componentStates: Record<string, JSONValue>, registry: Registry): Map<string, Instance> {
  const instances = new Map<string, Instance>([[id, { name: "ps-chat", props: {}, contracts: new Set([
    chatContract, componentContract, eventContract, "Playspace Serializable JSON (depth <=64)",
    "automata-playspace/lib/chat-state.js: ChatSnapshot v2",
    "automata-playspace/lib/state.js: PlayspaceChatSnapshot v2", ...Object.values(registry).map(definition => definition.contract),
  ]) }]]);
  for (const { content } of messages) {
    const { id: componentId, name, props } = content.data;
    if (instances.has(componentId)) throw new ContractError(componentContract, { "data.id": "Component IDs must be unique including ps-chat" });
    instances.set(componentId, { name, props, state: componentStates[componentId] });
  }
  return instances;
}
/** Validate the entire candidate, including linked history, before constructing any element. */
export function validateChatSnapshot(value: unknown, registry: Registry): ChatSnapshot {
  const contract = "automata-playspace/lib/chat-state.js: ChatSnapshot v2";
  const fail = (field: string, hint: string): never => { throw new ContractError(contract, { [field]: hint }); };
  if (!isRecord(value) || Object.keys(value).some(key => !["version", "id", "settings", "messages", "events", "composer", "pending", "componentStates"].includes(key))) return fail("$", "Expected v2 snapshot fields only");
  if (value.version !== 2 || !safeId(value.id)) fail("version/id", "Version 2 and safe ps-chat ID required");
  if (typeof value.composer !== "string" || typeof value.pending !== "boolean") fail("composer/pending", "String/boolean required");
  if (!Array.isArray(value.messages) || !Array.isArray(value.events) || !isRecord(value.componentStates)) fail("messages/events/componentStates", "History array, inert events array and state map required");
  const settings = validateChatData(value.settings);
  const ids = new Set();
  const messages = value.messages.map(item => {
    if (!isRecord(item) || Object.keys(item).some(key => !["id", "role", "content"].includes(key)) ||
      typeof item.id !== "string" || !item.id || ids.has(item.id) || !["user", "agent"].includes(item.role)) fail("messages", "Unique history IDs and user/agent roles required");
    ids.add(item.id);
    return { id: item.id, role: item.role, content: validateComponent(item.content, registry) };
  });
  const componentStates: Record<string, JSONValue> = Object.create(null);
  for (const [id, state] of Object.entries(value.componentStates)) {
    const content = messages.find(item => item.content.data.id === id)?.content;
    if (!content || !registry[content.data.name].validateState) fail("componentStates", "State requires its originating restorable component ID");
    try { componentStates[id] = cloneJSON(registry[content.data.name].validateState(content.data.props, state)); }
    catch (error) {
      if (error instanceof ContractError) throw error;
      fail("componentStates", "Component-owned state validation failed");
    }
  }
  const history = { messages, componentStates };
  for (const definition of new Set(Object.values(registry))) definition.validateHistory?.(history);
  const instances = chatInstances(value.id, messages, componentStates, registry);
  const events = value.events.map(record => validateEvent(record, { ...registry, "ps-chat": chatDefinition }, instances));
  return { version: 2, id: value.id, settings, messages, events, composer: value.composer, pending: value.pending, componentStates };
}
