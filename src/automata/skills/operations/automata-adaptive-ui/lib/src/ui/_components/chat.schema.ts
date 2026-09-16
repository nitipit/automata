import { defineField, Model } from "../_lib/edictor.bundle.js";

export type ChatData = {
  title: string;
  agentLabel: string;
  userLabel: string;
  inputLabel: string;
  sendLabel: string;
  placeholder: string;
  emptyMessage: string;
};

class ChatDataModel extends Model {}

ChatDataModel.define({
  title: defineField({ initial: "Chat" })
    .instance("string")
    .assert(
      (value: unknown) => typeof value === "string" && value.trim().length > 0,
      "Chat title is required",
    ),
  agentLabel: defineField({ initial: "Agent" })
    .instance("string")
    .assert(
      (value: unknown) => typeof value === "string" && value.trim().length > 0,
      "Chat agent label is required",
    ),
  userLabel: defineField({ initial: "You" })
    .instance("string")
    .assert(
      (value: unknown) => typeof value === "string" && value.trim().length > 0,
      "Chat user label is required",
    ),
  inputLabel: defineField({ initial: "Your message" })
    .instance("string")
    .assert(
      (value: unknown) => typeof value === "string" && value.trim().length > 0,
      "Chat input label is required",
    ),
  sendLabel: defineField({ initial: "Send" })
    .instance("string")
    .assert(
      (value: unknown) => typeof value === "string" && value.trim().length > 0,
      "Chat send label is required",
    ),
  placeholder: defineField({ initial: "Write a message…" })
    .instance("string")
    .assert(
      (value: unknown) => typeof value === "string",
      "Chat placeholder must be text",
    ),
  emptyMessage: defineField({ initial: "Send a message to begin." })
    .instance("string")
    .assert(
      (value: unknown) => typeof value === "string",
      "Chat empty message must be text",
    ),
});

/** Validates Chat labels and fills the component's presentation defaults. */
export function validateChatData(data: unknown): ChatData {
  return ChatDataModel.validate(data ?? {}) as ChatData;
}
