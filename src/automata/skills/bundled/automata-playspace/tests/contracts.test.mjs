import test from "node:test";
import assert from "node:assert/strict";
import { load } from "./runtime.mjs";
const { cloneJSON, ContractError, validateSnapshot, evaluateTrustedDefinition } = await load("playspace.js");
const snapshot = () => ({ version: 1,
  definitions: [{ id: "demo", source: "() => ({})", css: "" }],
  layout: [{ id: "one", definition: "demo", props: {}, state: null }],
});

test("finite JSON admission rejects live values and snapshots are independent clones", () => {
  for (const value of [undefined, NaN, Infinity, new Date(), { x: undefined }, () => {}]) {
    assert.throws(() => cloneJSON(value), ContractError);
  }
  const cycle = {}; cycle.self = cycle;
  assert.throws(() => cloneJSON(cycle), ContractError);
  const source = snapshot();
  const checked = validateSnapshot(source);
  source.layout[0].props.changed = true;
  assert.deepEqual(checked.layout[0].props, {});
});

test("structural admission rejects unknown fields, duplicate IDs and unknown definitions", () => {
  for (const change of [
    value => { value.token = "not allowed"; },
    value => { value.version = 2; },
    value => { value.layout.push(value.layout[0]); },
    value => { value.definitions.push(value.definitions[0]); },
    value => { value.layout[0].definition = "unknown"; },
    value => { value.layout[0].id = "div #arbitrary"; },
    value => { value.definitions[0].source = ""; },
  ]) {
    const value = snapshot(); change(value);
    assert.throws(() => validateSnapshot(value), ContractError);
  }
});

test("explicit evaluator passes public UI/CSS and validates returned definition", () => {
  assert.throws(() => evaluateTrustedDefinition(snapshot().definitions[0], {}), ContractError);
  const record = { id: "demo", css: "authored", source: `(ui, css) => ({
    validateProps: value => value, validateState: (_p, value) => value,
    events: {}, update: (_p, _s, value) => value,
    create: () => ({ ui, css })
  })` };
  const marker = {};
  const definition = evaluateTrustedDefinition(record, marker);
  assert.deepEqual(definition.create(), { ui: marker, css: "authored" });
});
