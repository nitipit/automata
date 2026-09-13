import { validateChatData } from "./chat.schema.ts";

Deno.test("Chat schema fills readable defaults and accepts configurable labels", () => {
  const data = validateChatData({
    title: "Conversation",
    agentLabel: "Assistant",
    userLabel: "Visitor",
  });
  if (
    data.title !== "Conversation" || data.agentLabel !== "Assistant" ||
    data.userLabel !== "Visitor" || data.inputLabel !== "Your message" ||
    data.sendLabel !== "Send"
  ) {
    throw new Error("Chat labels or defaults are incorrect");
  }
});

Deno.test("Chat schema rejects blank labels and unknown data", () => {
  for (const value of [
    { agentLabel: " " },
    { sendLabel: "" },
    { unknown: true },
  ]) {
    let rejected = false;
    try {
      validateChatData(value);
    } catch {
      rejected = true;
    }
    if (!rejected) throw new Error("Invalid Chat data was accepted");
  }
});
