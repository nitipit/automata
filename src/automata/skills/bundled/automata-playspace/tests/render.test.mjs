import test from "node:test";
import assert from "node:assert/strict";
import { load, installDOM, FakeNode } from "./runtime.mjs";
installDOM();
const { createPlayspace } = await load("playspace.js");
const draft = (count = 1) => ({ version: 1,
  definitions: [{ id: "demo", source: "trusted", css: "" }],
  layout: Array.from({ length: count }, (_, i) => ({
    id: `item${i}`, definition: "demo", props: { label: "demo" }, state: { text: "good" },
  })),
});
function harness() {
  const contexts = [], handles = [], events = [], errors = [];
  let loads = 0, creates = 0, changed = 0;
  const definition = {
    validateProps(value) { if (value.label !== "demo") throw Error(); return value; },
    validateState(_props, value) { if (typeof value.text !== "string") throw Error(); return value; },
    events: { request(value) { if (typeof value.text !== "string") throw Error(); return value; } },
    update(props, state, value) {
      props.label = "mutated reducer input";
      state.text = "mutated reducer input";
      if (value.fail) throw Error("invalid update");
      return { text: value.text };
    },
    create(props, context) {
      creates++;
      if (context.state.text === "throw") throw Error("construction");
      const handle = { element: new FakeNode(), disposed: false,
        snapshot: () => context.state,
        dispose() { handle.disposed = true; if (handle.throwDispose) throw Error(); },
      };
      contexts.push(context); handles.push(handle);
      context.emit("request", { text: "staging suppressed" });
      context.changed();
      return handle;
    },
  };
  const root = new FakeNode();
  const runtime = createPlayspace({ root,
    loadDefinition(record) { loads++; if (record.source !== "trusted") throw Error("untrusted"); return definition; },
    onEvent: event => events.push(event), onChange: () => changed++, onError: error => errors.push(error),
  });
  return { runtime, root, contexts, handles, events, errors, definition,
    get counts() { return { loads, creates, changed }; } };
}

test("event payloads stay component-owned; updates reuse definition and retire stale callbacks", () => {
  const h = harness();
  h.runtime.replace(draft(2));
  assert.equal(h.events.length, 0);
  h.contexts[0].emit("request", { text: "hello" });
  assert.deepEqual(h.events[0].payload, { text: "hello" });
  assert.equal(h.events[0].isCurrent(), true);
  const sibling = h.root.children[1];
  h.runtime.update("item0", { text: "reply" });
  assert.equal(h.events[0].isCurrent(), false);
  assert.equal(h.handles[0].disposed, true);
  assert.equal(h.root.children[1], sibling);
  h.contexts[0].emit("request", { text: "stale" });
  assert.equal(h.events.length, 1);
  assert.deepEqual(h.runtime.snapshot().layout[0].state, { text: "reply" });
  assert.equal(h.counts.loads, 1);
  assert.deepEqual(h.runtime.snapshot().layout[0].props, { label: "demo" });
});

test("invalid structure/props/source fail before construction and retain last-good view", () => {
  const h = harness(); h.runtime.replace(draft());
  const element = h.root.children[0], good = h.runtime.snapshot();
  const unknown = draft(); unknown.layout[0].definition = "missing";
  assert.throws(() => h.runtime.replace(unknown));
  assert.equal(h.counts.loads, 1);
  const invalid = draft(2); invalid.layout[1].props.label = false;
  assert.throws(() => h.runtime.replace(invalid));
  assert.equal(h.counts.creates, 1);
  const untrusted = draft(); untrusted.definitions[0].source = "untrusted";
  assert.throws(() => h.runtime.replace(untrusted));
  assert.equal(h.root.children[0], element);
  assert.deepEqual(h.runtime.snapshot(), good);
  assert.throws(() => h.runtime.update("item0", { fail: true }));
  assert.deepEqual(h.runtime.snapshot(), good);
  const copied = h.runtime.snapshot(); copied.layout[0].state.text = "outside";
  assert.deepEqual(h.runtime.snapshot(), good);
});

test("failed staging releases candidates, disposal failure cannot kill last-good view", () => {
  const h = harness(); h.runtime.replace(draft());
  const previous = h.root.children[0];
  const candidate = draft(2); candidate.layout[1].state.text = "throw";
  const create = h.definition.create;
  h.definition.create = (...args) => {
    const handle = create(...args); handle.throwDispose = true; return handle;
  };
  assert.throws(() => h.runtime.replace(candidate));
  assert.equal(h.handles[1].disposed, true);
  assert.equal(h.handles[0].disposed, false);
  assert.equal(h.root.children[0], previous);
  assert.equal(h.errors.length, 1);
  h.contexts[0].emit("request", { text: "still current" });
  assert.equal(h.events[0].isCurrent(), true);
  h.runtime.replace(draft());
  assert.equal(h.counts.loads, 1);
  h.runtime.dispose();
  h.runtime.dispose();
  h.contexts.at(-1).emit("request", { text: "disposed" });
  assert.equal(h.events.length, 1);
  assert.throws(() => h.runtime.snapshot());
});
