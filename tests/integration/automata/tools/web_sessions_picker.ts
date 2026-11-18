// Offline Pi provider for native browser/persistence tests. No network calls.
import { createAssistantMessageEventStream, type AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.registerProvider("picker-fixture", {
    api: "openai-responses",
    baseUrl: "http://unused.invalid",
    apiKey: "offline-fixture-only",
    models: [
      { id: "fixture", name: "Sessions fixture", reasoning: true },
      { id: "plain", name: "Plain fixture", reasoning: false },
      { id: "unpinned", name: "Unpinned fixture", reasoning: true },
    ].map(item => ({
      ...item, input: ["text" as const], contextWindow: 16000, maxTokens: 256,
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    })),
    streamSimple(model, context, options) {
      const messages = context.messages.flatMap(message => message.role === "user"
        ? [typeof message.content === "string" ? message.content
          : message.content.map(part => part.type === "text" ? part.text : "").join("")]
        : []);
      const latest = messages.at(-1) ?? "";
      const stream = createAssistantMessageEventStream();
      const text = (text: string) => ({ type: "text" as const, text });
      const makeReply = (content: AssistantMessage["content"], stopReason: AssistantMessage["stopReason"] = "stop"): AssistantMessage => ({
        role: "assistant", content, api: model.api, provider: model.provider, model: model.id,
        usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        stopReason, timestamp: Date.now(),
      });
      const finish = (reply: AssistantMessage) => {
        stream.push({ type: "done", reason: reply.stopReason as "stop" | "toolUse", message: reply });
        stream.end(reply);
      };
      const tool = (name: string, args: Record<string, unknown>) => finish(makeReply([
        {type: "toolCall", id: `shared-fixture-${name}`, name, arguments: args},
      ], "toolUse"));
      if (latest === "Fixture runtime settings") {
        finish(makeReply([text(`Native next message: ${model.id} / ${options?.reasoning ?? "off"}`)]));
        return stream;
      }
      // Actual native web UI tools with intentionally identical tool/event IDs
      // across two native sessions. The response displays the RECEIVED value.
      if (/^UI [AB]$/.test(latest)) {
        const label = latest.at(-1)!;
        const turn = context.messages.slice(context.messages.findLastIndex(message => message.role === "user") + 1);
        const value = (name: string) => {
          const message = turn.find(message => message.role === "toolResult" && message.toolName === name);
          if (message?.role !== "toolResult") return undefined;
          const first = message.content[0];
          return first?.type === "text" ? JSON.parse(first.text) : undefined;
        };
        const sub = value("web_ui_subscribe");
        const execute = value("web_ui_execute");
        const input = value("web_ui_wait_event");
        const release = value("web_ui_unsubscribe");
        if ([sub, execute, input, release].some(result => result && !result.ok)) {
          finish(makeReply([text(`Offline UI ${label} failed: ${JSON.stringify({sub, execute, input, release})}`)]));
        } else if (!sub) tool("web_ui_subscribe", { name: "shared-fixture-choice", correlationId: "same" });
        else if (!execute) tool("web_ui_execute", { code: `
          const button = document.createElement('button');
          button.id = 'fixture-choice'; button.textContent = 'Choose ${label}';
          button.addEventListener('click', () => bridge.emit('shared-fixture-choice',
            {blockId: ui.blockId, correlationId: 'same', value: '${label}'}), {once:true});
          ui.root.append(button);
          return ui.blockId;
        ` });
        else if (!input) tool("web_ui_wait_event", { subscriptionId: sub.subscriptionId, timeoutMs: 20000 });
        else if (!release) tool("web_ui_unsubscribe", { subscriptionId: sub.subscriptionId });
        else finish(makeReply([text(`Input received by Pi ${label}: ${input.event.value}`)]));
        return stream;
      }
      const slow = /^Parallel [AB]$/.test(latest);
      const partial = makeReply([text(`Partial ${latest}`)]);
      if (slow) {
        stream.push({ type: "start", partial: makeReply([]) });
        stream.push({ type: "text_start", contentIndex: 0, partial: makeReply([text("")]) });
        stream.push({ type: "text_delta", contentIndex: 0, delta: `Partial ${latest}`, partial });
      }
      const onAbort = () => {
        clearTimeout(timer);
        const reply = { ...partial, stopReason: "aborted" as const, errorMessage: "Offline fixture aborted" };
        stream.push({ type: "error", reason: "aborted", error: reply });
        stream.end(reply);
      };
      const timer = setTimeout(() => {
        options?.signal?.removeEventListener("abort", onAbort);
        finish(makeReply([text(`Offline history: ${messages.join(" | ")}`)]));
      }, latest === "Parallel B" ? 15000 : latest === "Parallel A" ? 5000 : latest === "A continues" ? 800 : 10);
      if (options?.signal?.aborted) onAbort();
      else options?.signal?.addEventListener("abort", onAbort, {once:true});
      return stream;
    },
  });
}
