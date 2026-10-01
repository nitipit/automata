import test from "node:test";
import assert from "node:assert/strict";
import { load, installDOM } from "./runtime.mjs";
installDOM();
const { ContractError, component, text, event, validateComponent, validateEvent } = await load("contracts.js");
const { formContracts: forms } = await load("form.schema.js");
const { builtins } = await load("registry.js");
const { chatInstances, validateChatSnapshot } = await load("chat-state.js");
const { chatDefinition } = await load("chat.schema.js");
const { validateStarterSnapshot } = await load("state.js");
const reject = fn => assert.throws(fn, ContractError);
const props = forms.validateProps({ fields: [
  { name: "goal", label: "Goal", kind: "text", required: true, minLength: 2 },
  { name: "pace", label: "Pace", kind: "choice", required: true, choices: [{ value: "quick", label: "Quick" }, { value: "careful", label: "Careful" }] },
  { name: "notes", label: "Notes", kind: "text", required: false },
] });
const answers = { goal: "Explore", pace: "quick", notes: "" };
const message = (id, content) => ({ id, role: "agent", content });
function linked() {
  const first = forms.submit(props, answers, "submit-1");
  const revision = forms.revise(props, first, "form-1");
  const corrected = forms.submit(revision, { ...answers, pace: "careful" }, "submit-2");
  return { version: 2, id: "chat-root", settings: {}, composer: "draft", pending: true,
    messages: [message("history-1", component("ps-form", props, "form-1")), message("history-2", component("ps-form", revision, "form-2"))],
    componentStates: { "form-1": { values: answers, submission: first }, "form-2": { values: corrected.values, submission: corrected } },
    events: [event("form-submit", "ps-form#form-1", first), event("form-submit", "ps-form#form-2", corrected)],
  };
}

test("single component contract validates props, safe stable IDs and uniqueness", () => {
  assert.deepEqual(validateComponent(text("<b>literal</b>", "text-1"), builtins).data.props, { text: "<b>literal</b>" });
  reject(() => validateComponent({ type: "text", data: "removed" }, builtins));
  reject(() => validateComponent(component("ps-text", { text: 7 }, "text-1"), builtins));
  reject(() => validateComponent(component("ps-unknown", {}, "test-1"), builtins));
  reject(() => validateComponent(text("x", "a#b"), builtins));
  reject(() => validateComponent(text("x", "__proto__"), builtins));
  const duplicate = linked();
  duplicate.messages.push(message("history-3", text("collision", "form-1")));
  reject(() => validateChatSnapshot(duplicate, builtins));
  duplicate.messages.pop();
  duplicate.id = "form-1";
  reject(() => validateChatSnapshot(duplicate, builtins));
  reject(() => validateComponent({ ...text("x"), ...JSON.parse('{"__proto__":"bad"}') }, builtins));
});

test("event ownership rejects unknown name, arbitrary selector, target and partial detail", () => {
  const history = validateChatSnapshot(linked(), builtins);
  const instances = chatInstances(history.id, history.messages, history.componentStates, builtins);
  const registry = { ...builtins, "ps-chat": chatDefinition };
  assert.deepEqual(validateEvent(history.events[0], registry, instances), history.events[0]);
  for (const target of ["body", "ps-form#form-1 input", "ps-form#form-1#other", "ps-form#missing", "ps-text#form-1"]) {
    reject(() => validateEvent(event("form-submit", target, history.events[0].data.detail), registry, instances));
  }
  reject(() => validateEvent(event("execute", "ps-form#form-1", {}), registry, instances));
  reject(() => validateEvent(event("form-submit", "ps-form#form-1", { ...history.events[0].data.detail, values: { goal: "partial" } }), registry, instances));
  reject(() => validateEvent(event("form-submit", "ps-text#text-1", {}), registry, new Map([["text-1", { name: "ps-text", props: { text: "inert" } }]])));
});

test("complete explicit revision retains full fields/answers and readonly prior state", () => {
  const history = validateChatSnapshot(linked(), builtins);
  const revised = history.messages[1].content.data.props;
  assert.deepEqual(revised.initialValues, answers);
  assert.equal(revised.revision.originComponentId, "form-1");
  assert.deepEqual(Object.keys(history.events[1].data.detail), ["submissionId", "previousSubmissionId", "values"]);
  assert.equal(history.events[1].data.detail.previousSubmissionId, "submit-1");
  assert.equal(history.componentStates["form-1"].values.pace, "quick");
  reject(() => forms.validateAnswers(props, { goal: "ok", pace: "quick" }));
  reject(() => forms.validateState(props, { values: { ...answers, pace: "careful" }, submission: history.events[0].data.detail }));
  const broken = linked();
  broken.messages[1].content.data.props.initialValues.goal = "silent patch";
  reject(() => validateChatSnapshot(broken, builtins));
  const foreign = linked();
  foreign.messages[1].content.data.props.revision.originComponentId = "foreign";
  reject(() => validateChatSnapshot(foreign, builtins));
});

test("v2 keeps inert event records and safe feedback; rejects old version/capabilities", () => {
  const saved = validateStarterSnapshot({ version: 2, mode: "live", chat: linked() });
  assert.equal(saved.chat.pending, true); // evidence, not an outbox
  assert.equal(saved.chat.events.length, 2);
  reject(() => validateStarterSnapshot({ ...saved, version: 1 }));
  reject(() => validateStarterSnapshot({ ...saved, credentials: {} }));
  reject(() => validateChatSnapshot({ ...saved.chat, version: 1 }, builtins));
  const instances = chatInstances(saved.chat.id, saved.chat.messages, saved.chat.componentStates, builtins);
  const registry = { ...builtins, "ps-chat": chatDefinition };
  validateEvent(event("validation-feedback", "ps-chat#chat-root", { contract: forms.pointer, fields: { revision: "Canonical revision link required" } }), registry, instances);
  reject(() => validateEvent(event("validation-feedback", "ps-chat#chat-root", { contract: "arbitrary exception text", fields: {} }), registry, instances));
  try { forms.validateAnswers(props, { ...answers, goal: { secret: "DO-NOT-ECHO" } }); }
  catch (error) { assert.ok(!error.message.includes("DO-NOT-ECHO")); assert.equal(error.contract, forms.pointer); }
});
