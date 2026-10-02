import { defineField, Model } from "../_lib/edictor.bundle.js";

export type ChatContent =
  | { type: "text"; data: string }
  | { type: "json"; data: unknown }
  | { type: "component"; data: { name: string; props: unknown } };
export type ChatMessageRole = "user" | "agent";
export type ChatMessage = { id: string; role: ChatMessageRole; content: ChatContent };
export type ChatComponentHandle = {
  element: HTMLElement;
  snapshot?: () => unknown;
  dispose?: () => void;
};
/** Only application-authored definitions belong here. No strings are evaluated. */
export type ChatComponentDefinition = {
  contract: string;
  validate: (props: unknown) => unknown;
  validateState?: (props: unknown, state: unknown) => unknown;
  create: (props: unknown, context: {
    messageId: string;
    state: unknown;
    changed: () => void;
  }) => ChatComponentHandle;
};
export type ChatRegistry = Readonly<Record<string, ChatComponentDefinition>>;

/** Deliberately excludes rejected values, stack traces and arbitrary exception text. */
export class ChatContractError extends Error {
  constructor(public contract: string, public fields: Record<string, string>) {
    super(`Contract: ${contract}\n${Object.entries(fields).map(([key, hint]) => `${key}: ${hint}`).join("\n")}`);
  }
}

export function testChatModel(
  model: typeof Model,
  value: unknown,
  contract: string,
  hints: Record<string, string>,
): Record<string, unknown> {
  if (!isRecord(value)) throw new ChatContractError(contract, { "$": "Expected an object" });
  const result = model.test(value);
  const errors = Object.keys(result.error);
  if (errors.length) {
    throw new ChatContractError(contract, Object.fromEntries(errors.map((key) =>
      [key in hints ? key : "$", hints[key] ?? "Unknown field; consult the contract"]
    )));
  }
  return result.valid as Record<string, unknown>;
}

class ContentModel extends Model {}
ContentModel.define({
  type: defineField({ required: true }).assert((v: unknown) =>
    ["text", "json", "component"].includes(v as string), "Known content type required"),
  data: defineField({ required: true }),
});
class ComponentModel extends Model {}
ComponentModel.define({
  name: defineField({ required: true }).assert((v: unknown) => typeof v === "string" && !!v, "Name required"),
  props: defineField({ required: true }),
});
export const chatContentContract = "{type:'text',data:string} | {type:'json',data:JSON} | {type:'component',data:{name:trusted registry name,props:component data}}";

/** Validates complete literal content before applying it. Legacy {text} is unambiguous only without type/data. */
export function validateChatContent(value: unknown, registry: ChatRegistry = {}): ChatContent {
  if (isRecord(value) && !("type" in value) && !("data" in value) && typeof value.text === "string") {
    value = { type: "text", data: value.text };
  }
  const content = testChatModel(ContentModel, value, chatContentContract, {
    type: "Expected text, json or component", data: "Required content data",
  });
  if (content.type === "text") {
    if (typeof content.data !== "string") throw new ChatContractError(chatContentContract, { data: "Expected literal text" });
    return { type: "text", data: content.data };
  }
  if (content.type === "json") {
    return { type: "json", data: cloneChatJSON(content.data) };
  }
  const data = testChatModel(ComponentModel, content.data, chatContentContract, {
    name: "Expected a registered component name", props: "Required component props",
  });
  const name = data.name as string;
  if (!Object.hasOwn(registry, name)) throw new ChatContractError(chatContentContract, { "data.name": "Unknown trusted component; consult the registry" });
  const definition = registry[name];
  let props: unknown;
  try { props = definition.validate(data.props); }
  catch (error) {
    if (error instanceof ChatContractError) throw error;
    throw new ChatContractError(definition.contract, { "props": "Component validation failed; consult its canonical model" });
  }
  return { type: "component", data: { name, props: cloneChatJSON(props) } };
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value) &&
    [Object.prototype, null].includes(Object.getPrototypeOf(value));
}

/** Rejects lossy/non-JSON state (undefined, cycles, nonfinite numbers, handles). */
export function cloneChatJSON(value: unknown): unknown {
  const seen = new Set<object>();
  function check(v: unknown, depth: number): void {
    if (depth > 64) throw new Error("depth");
    if (v === null || typeof v === "string" || typeof v === "boolean") return;
    if (typeof v === "number" && Number.isFinite(v)) return;
    if (typeof v !== "object" || !v || seen.has(v)) throw new Error("json");
    if (!Array.isArray(v) && !isRecord(v)) throw new Error("object");
    seen.add(v);
    for (const item of Array.isArray(v) ? v : Object.values(v)) check(item, depth + 1);
    seen.delete(v);
  }
  try { check(value, 0); return JSON.parse(JSON.stringify(value)); }
  catch { throw new ChatContractError("Serializable JSON (depth <=64)", { data: "Expected JSON without cycles, undefined or live objects" }); }
}
