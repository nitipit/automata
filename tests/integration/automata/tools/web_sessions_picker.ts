// Offline Pi provider for native browser/persistence tests. No network calls.
import { createAssistantMessageEventStream } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.registerProvider("picker-fixture", {
    api: "openai-responses",
    baseUrl: "http://unused.invalid",
    apiKey: "offline-fixture-only",
    models: [{
      id: "fixture", name: "Sessions fixture", reasoning: false, input: ["text"],
      contextWindow: 16000, maxTokens: 256,
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    }],
    streamSimple(model, context) {
      const messages = context.messages.flatMap(message => message.role === "user"
        ? [typeof message.content === "string" ? message.content
          : message.content.map(part => part.type === "text" ? part.text : "").join("")]
        : []);
      const reply = {
        role: "assistant", content: [{ type: "text", text: `Offline history: ${messages.join(" | ")}` }],
        api: model.api, provider: model.provider, model: model.id,
        usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        stopReason: "stop", timestamp: Date.now(),
      } as const;
      const stream = createAssistantMessageEventStream();
      setTimeout(() => {
        stream.push({ type: "done", reason: "stop", message: reply });
        stream.end(reply);
      }, messages.at(-1) === "A continues" ? 800 : 10);
      return stream;
    },
  });
}
