import test from "node:test";
import assert from "node:assert/strict";
import { load, installDOM, FakeNode } from "./runtime.mjs";
installDOM();
const { Chat, registerPlayspace, text, component, event, ContractError, formContracts } = await load("playspace.js");
registerPlayspace();
const ready = () => { const chat = new Chat(); chat.id = "chat-root"; chat.connectedCallback(); chat.setConnection(true); chat.setAgentBusy(false); return chat; };

test("composer emits one component path; invalid revision rejected pre-construction; safe explicit feedback once", () => {
  const chat = ready();
  const outgoing = [];
  chat.addEventListener("agent-message", value => outgoing.push(value.detail));
  const textarea = chat.querySelector("textarea");
  textarea.value = "<b>literal</b>";
  chat.querySelector("form").emit("submit");
  assert.equal(outgoing[0].type, "component");
  assert.equal(outgoing[0].data.name, "ps-text");
  const stableId = outgoing[0].data.id;
  chat.markSent();
  assert.equal(chat.snapshot().messages[0].content.data.id, stableId);
  chat.receiveMessage(text("reply", "reply-1"));
  const before = chat.snapshot();
  const bad = formContracts.validateProps({ fields: [{ name: "goal", label: "Goal", kind: "text", required: true }],
    revision: { originComponentId: "missing", previousSubmissionId: "missing" } });
  assert.equal(chat.receiveMessage(component("ps-form", bad, "invalid-form")), false);
  assert.deepEqual(chat.snapshot().messages, before.messages);
  assert.equal(chat.querySelector(".validation-send").hidden, false);
  chat.querySelector(".validation-send").emit("click");
  assert.equal(outgoing.length, 2);
  assert.equal(outgoing[1].type, "event");
  assert.equal(outgoing[1].data.name, "validation-feedback");
  assert.equal(outgoing[1].data.target, "ps-chat#chat-root");
  assert.equal(outgoing[1].data.detail.contract, formContracts.pointer);
  chat.querySelector(".validation-send").emit("click");
  assert.equal(outgoing.length, 2);
  const snapshot = chat.snapshot();
  assert.equal(snapshot.events.length, 1);
  assert.equal(chat.restore(snapshot), true);
  assert.equal(outgoing.length, 2); // restored events/pending have no replay
  assert.equal(chat.canSend(), false); // root restore disconnects
  assert.equal(chat.snapshot().pending, false);
  assert.equal(chat.snapshot().events.length, 1);
  assert.equal(chat.receiveMessage(event("execute", "ps-chat#chat-root", {})), false);
  assert.equal(chat.snapshot().events.length, 1);
  const foreign = structuredClone(snapshot);
  foreign.events.push(event("form-submit", "ps-form#foreign", {}));
  assert.equal(chat.restore(foreign), false);
  assert.deepEqual(chat.snapshot().messages, snapshot.messages);
  assert.equal(outgoing.length, 2);
  assert.equal(chat.snapshot().events.length, 1);
  chat.dispose();
  assert.equal(chat.receiveMessage(text("late", "late-1")), false);
});

test("retired handles cannot change history/send/revise; duplicate IDs fail before create", () => {
  const chat = ready();
  let creates = 0, disposed = 0, context;
  const registry = { "ps-probe": { contract: "probe", validate: value => value,
    create(_props, value) { creates++; context = value; return { element: new FakeNode("ps-probe"), dispose: () => { disposed++; } }; },
  } };
  chat.setRegistry(registry);
  chat.addMessage("agent", component("ps-probe", {}, "probe-1"));
  assert.throws(() => chat.addMessage("agent", component("ps-probe", {}, "probe-1")), ContractError);
  assert.equal(creates, 1);
  let changes = 0;
  chat.addEventListener("chat-change", () => changes++);
  const retired = context;
  assert.equal(chat.restore(chat.snapshot()), true);
  assert.equal(disposed, 1);
  retired.changed();
  assert.equal(changes, 0);
  assert.equal(retired.canSend(), false);
  retired.appendRevision({});
  assert.equal(chat.snapshot().messages.length, 1);
  chat.dispose();
  context.changed();
  assert.equal(changes, 0);
  assert.equal(disposed, 2);
});
