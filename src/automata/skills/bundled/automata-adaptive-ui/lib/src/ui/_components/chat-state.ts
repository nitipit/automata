import { type ChatData, validateChatData } from "./chat.schema.js";
import {
  ChatContractError,
  type ChatMessage,
  type ChatRegistry,
  cloneChatJSON,
  isRecord,
  validateChatContent,
} from "./chat-content.js";

/** Display history only; not model context or a durable delivery/outbox log. */
export type ChatSnapshot = {
  version: 1;
  settings: ChatData;
  messages: ChatMessage[];
  composer: string;
  pending: boolean;
  componentStates: Record<string, unknown>;
};

/** Builds a candidate entirely before a caller replaces the last-good view. */
export function validateChatSnapshot(value: unknown, registry: ChatRegistry = {}): ChatSnapshot {
  const contract = "ChatSnapshot v1: {version:1,settings:ChatData,messages:[{id,role,content}],composer:string,pending:boolean,componentStates:{messageId:state}}";
  const fail = (field: string, hint: string): never => { throw new ChatContractError(contract, { [field]: hint }); };
  if (!isRecord(value)) return fail("$", "Expected a snapshot object");
  const keys = ["version", "settings", "messages", "composer", "pending", "componentStates"];
  if (Object.keys(value).some((key) => !keys.includes(key))) return fail("$", "Unknown snapshot field");
  if (value.version !== 1) return fail("version", "Unsupported version; expected 1");
  if (typeof value.composer !== "string" || typeof value.pending !== "boolean") return fail("composer/pending", "Expected string/boolean");
  if (!Array.isArray(value.messages) || !isRecord(value.componentStates)) return fail("messages/componentStates", "Expected array/state map");
  let settings: ChatData;
  try { settings = validateChatData(value.settings); }
  catch { return fail("settings", "Expected valid ChatData labels"); }
  const ids = new Set<string>();
  const messages = value.messages.map((item): ChatMessage => {
    if (!isRecord(item) || Object.keys(item).some((key) => !["id", "role", "content"].includes(key)) ||
      typeof item.id !== "string" || !item.id || ids.has(item.id) ||
      !["user", "agent"].includes(item.role as string)) return fail("messages", "Expected unique IDs and user/agent roles");
    ids.add(item.id);
    return { id: item.id, role: item.role as ChatMessage["role"], content: validateChatContent(item.content, registry) };
  });
  const states: Record<string, unknown> = {};
  for (const [id, state] of Object.entries(value.componentStates)) {
    const message = messages.find((item) => item.id === id);
    if (message?.content.type !== "component") return fail("componentStates", "State requires its originating component message");
    const { name, props } = message.content.data;
    const validate = registry[name].validateState;
    if (!validate) return fail("componentStates", "Component has no restoration contract");
    try { states[id] = cloneChatJSON(validate(props, state)); }
    catch (error) {
      if (error instanceof ChatContractError) throw error;
      return fail("componentStates", "Component state validation failed");
    }
  }
  return { version: 1, settings, messages, composer: value.composer, pending: value.pending, componentStates: states };
}
