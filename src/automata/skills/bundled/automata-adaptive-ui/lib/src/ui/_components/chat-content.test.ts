import { ChatContractError, cloneChatJSON, validateChatContent, type ChatRegistry } from "./chat-content.ts";
import { validateChatSnapshot } from "./chat-state.ts";
import { defineField, Model } from "../_lib/edictor.bundle.ts";
import { testChatModel } from "./chat-content.ts";

function equal(a: unknown, b: unknown): void {
  if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`${JSON.stringify(a)} != ${JSON.stringify(b)}`);
}
function rejects(fn: () => unknown): ChatContractError {
  try { fn(); } catch (error) {
    if (error instanceof ChatContractError) return error;
    throw error;
  }
  throw new Error("Expected contract rejection");
}
class ExampleModel extends Model {}
ExampleModel.define({ title: defineField({ required: true }).instance("string") });
const registry: ChatRegistry = {
  example: { contract: "ExampleModel {title:string}",
    validate: (value) => testChatModel(ExampleModel, value, "ExampleModel", { title: "Expected text" }),
    validateState: (_props, state) => cloneChatJSON(state),
    create: () => { throw new Error("Not needed in schema test"); },
  },
};

Deno.test("Chat content validates literal text, JSON and unambiguous legacy replies", () => {
  equal(validateChatContent({ text: "<script>literal</script>" }), { type: "text", data: "<script>literal</script>" });
  equal(validateChatContent({ type: "json", data: { values: [1, null, true] } }), { type: "json", data: { values: [1, null, true] } });
  rejects(() => validateChatContent({ type: "html", data: "code" }));
  rejects(() => validateChatContent({ type: "text", data: 4 }));
  rejects(() => validateChatContent({ type: "text", data: "ok", text: "ambiguous" }));
  rejects(() => validateChatContent({ type: "json", data: { x: undefined } }));
  rejects(() => cloneChatJSON({ x: Number.NaN }));
});

Deno.test("Chat only uses trusted registrations and reports safe Edictor field feedback", () => {
  equal(validateChatContent({ type: "component", data: { name: "example", props: { title: "Good" } } }, registry),
    { type: "component", data: { name: "example", props: { title: "Good" } } });
  rejects(() => validateChatContent({ type: "component", data: { name: "constructor", props: {} } }, registry));
  const error = rejects(() => validateChatContent({ type: "component", data: { name: "example", props: { title: { secret: "DO NOT ECHO" } } } }, registry));
  if (error.message.includes("DO NOT ECHO") || error.fields.title !== "Expected text") throw new Error("Unsafe feedback");
});

Deno.test("Chat snapshot preserves drafts and pending display without capabilities", () => {
  const snapshot = validateChatSnapshot({ version: 1, settings: {}, composer: "unfinished", pending: true,
    messages: [{ id: "m1", role: "agent", content: { type: "component", data: { name: "example", props: { title: "Draft" } } } }],
    componentStates: { m1: { draft: "retained" } },
  }, registry);
  equal(snapshot.componentStates, { m1: { draft: "retained" } });
  equal(snapshot.composer, "unfinished");
  equal(snapshot.pending, true);
  rejects(() => validateChatSnapshot({ ...snapshot, version: 2 }, registry));
  rejects(() => validateChatSnapshot({ ...snapshot, token: "no" }, registry));
  rejects(() => validateChatSnapshot({ ...snapshot, componentStates: { unknown: {} } }, registry));
});
