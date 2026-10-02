// @ts-types="./adaptive-ui.d.ts"
import { defineField, Model } from "./adaptive-ui.js";
import type { ChatData, Instance } from "./types.js";
import { testModel, isRecord, ContractError } from "./contracts.js";
class ChatDataModel extends Model {
}
ChatDataModel.define({
  title: defineField({ initial: "Chat" }).instance("string").assert(
    (value) => typeof value === "string" && value.trim().length > 0,
    "Chat title is required"
  ),
  agentLabel: defineField({ initial: "Agent" }).instance("string").assert(
    (value) => typeof value === "string" && value.trim().length > 0,
    "Chat agent label is required"
  ),
  userLabel: defineField({ initial: "You" }).instance("string").assert(
    (value) => typeof value === "string" && value.trim().length > 0,
    "Chat user label is required"
  ),
  inputLabel: defineField({ initial: "Your message" }).instance("string").assert(
    (value) => typeof value === "string" && value.trim().length > 0,
    "Chat input label is required"
  ),
  sendLabel: defineField({ initial: "Send" }).instance("string").assert(
    (value) => typeof value === "string" && value.trim().length > 0,
    "Chat send label is required"
  ),
  placeholder: defineField({ initial: "Write a message\u2026" }).instance("string").assert(
    (value) => typeof value === "string",
    "Chat placeholder must be text"
  ),
  emptyMessage: defineField({ initial: "Send a message to begin." }).instance("string").assert(
    (value) => typeof value === "string",
    "Chat empty message must be text"
  )
});
function validateChatData(data: unknown): ChatData {
  return testModel(ChatDataModel, data ?? {}, chatContract, {
    title: "Nonempty title", agentLabel: "Nonempty agent label", userLabel: "Nonempty user label",
    inputLabel: "Nonempty input label", sendLabel: "Nonempty send label",
    placeholder: "Text placeholder", emptyMessage: "Text empty message",
  }) as ChatData;
}
export const chatContract = "automata-playspace/lib/chat.schema.js: ps-chat labels / validation-feedback";
class FeedbackModel extends Model {}
FeedbackModel.define({ contract: defineField({ required: true }).instance("string"), fields: defineField({ required: true }) });
export function validateFeedback(value: unknown, instance: Instance) {
  const result = testModel(FeedbackModel, value, chatContract, { contract: "Canonical contract pointer", fields: "Safe field hints" });
  if (!instance.contracts?.has(result.contract) || !isRecord(result.fields) || !Object.keys(result.fields).length ||
    Object.entries(result.fields).some(([key, hint]) => !/^[a-zA-Z0-9_$.[\]/-]{1,128}$/.test(key) || typeof hint !== "string" || hint.length > 256)) {
    throw new ContractError(chatContract, { fields: "Known canonical contract and bounded safe field hints required" });
  }
  return result;
}
export const chatDefinition = {
  contract: chatContract, validate: validateChatData,
  catalog: {
    description: "Chat root settings and safe validation feedback; not renderable message content",
    sources: ["./lib/chat.schema.js", "./lib/chat.js"],
    propsExample: {},
    eventExamples: { "validation-feedback": { detail: {
      contract: chatContract, fields: { title: "Nonempty title required; consult root contract" },
    } } },
  },
  events: { "validation-feedback": validateFeedback },
};
export { validateChatData };
