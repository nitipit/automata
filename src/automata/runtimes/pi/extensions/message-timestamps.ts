import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

/** Model-facing copies only. Original Pi timestamps are milliseconds since epoch.
 * UTC makes annotations independent of current time, timezone, reload and branch.
 * A timestamp describes message creation, not delivery, completion or active work.
 */
export function annotateMessage<T extends { role: string; timestamp?: number; content?: unknown;
  customType?: string }>(message: T): T {
  const content = message.content;
  const conversational = message.role === "user" ||
    (message.role === "custom" && message.customType === "browser-context") ||
    (message.role === "assistant" && Array.isArray(content) &&
      content.some(block => block?.type === "text" && typeof block.text === "string" && block.text.trim()));
  if (!conversational || typeof message.timestamp !== "number" ||
      !Number.isFinite(message.timestamp)) return message;
  const date = new Date(message.timestamp);
  if (!Number.isFinite(date.getTime())) return message;
  const label = `[Runtime message timestamp: ${date.toISOString()}]`;
  if (typeof content === "string") {
    if (content.startsWith(label + "\n")) return message;
    return { ...message, content: `${label}\n${content}` };
  }
  if (Array.isArray(content)) {
    if (content[0]?.type === "text" && content[0].text === label) return message;
    // Keep image, signed text/thinking and tool-call blocks intact and in order.
    return { ...message, content: [{ type: "text", text: label }, ...content] };
  }
  return message;
}

export default function (pi: ExtensionAPI) {
  pi.on("context", event => ({ messages: event.messages.map(annotateMessage) }));
}
