import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { load, installDOM } from "./runtime.mjs";
installDOM();
const { generateCatalog, roots } = await load("catalog.js");
const { builtins } = await load("registry.js");
const { validateComponent, validateEvent, ContractError } = await load("contracts.js");

test("public catalog is derived from definitions and all example payloads are admitted", async () => {
  const catalog = generateCatalog();
  assert.deepEqual(catalog, JSON.parse(await readFile(process.env.PLAYSPACE_CATALOG, "utf8")));
  const definitions = { ...builtins, ...roots };
  const contracts = new Set(Object.values(definitions).map(item => item.contract));
  assert.deepEqual(catalog.entries.map(item => item.name).sort(), Object.keys(definitions).sort());
  for (const entry of catalog.entries) {
    const definition = definitions[entry.name];
    assert.equal(entry.contract, definition.contract);
    assert.deepEqual(entry.supportedEvents, Object.keys(definition.events ?? {}).sort());
    const props = entry.renderable ? validateComponent(entry.example, builtins).data.props :
      definition.validate(entry.example.settings);
    const id = entry.renderable ? entry.example.data.id : entry.example.id;
    for (const example of entry.eventExamples) {
      const state = example.prerequisiteState === undefined ? undefined :
        definition.validateState(props, example.prerequisiteState);
      const instances = new Map([[id, { name: entry.name, props, state, contracts }]]);
      assert.deepEqual(validateEvent(example.payload, definitions, instances), example.payload);
      const unknown = structuredClone(example.payload);
      unknown.data.target = entry.name + "#missing-id";
      assert.throws(() => validateEvent(unknown, definitions, instances), ContractError);
      const unsupported = structuredClone(example.payload);
      unsupported.data.name = "not-supported";
      assert.throws(() => validateEvent(unsupported, definitions, instances), ContractError);
    }
  }
  const root = catalog.entries.find(item => item.name === "ps-chat");
  assert.equal(root.kind, "root");
  assert.equal(root.renderable, false);
  assert.deepEqual(root.supportedEvents, ["validation-feedback"]);
  for (const name of ["ps-unknown", "ps-chat"]) {
    assert.throws(() => validateComponent({ type: "component", data: { name, id: "unknown-example", props: {} } }, builtins), ContractError);
  }
});
