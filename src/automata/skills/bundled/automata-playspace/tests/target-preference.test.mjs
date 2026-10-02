import test from "node:test";
import assert from "node:assert/strict";
import { load } from "./runtime.mjs";
const { createTargetPreference, validTargetParticipant } = await load("target-preference.js");

test("explicit target preference survives a new page without credentials, snapshots or sends", () => {
  const values = new Map(), calls = [], states = [];
  const storage = {getItem:key => values.get(key) ?? null,
    setItem(key, value) { calls.push({key,value}); values.set(key,value); }};
  const key = "automata-playspace-chat-target-v1:http://127.0.0.1:8775/";
  const options = {key,getStorage:() => storage,onState:value => states.push(value)};
  const first = createTargetPreference(options);
  assert.equal(first.restore("agent"), "agent");
  assert.equal(calls.length, 0); // initial fallback does not silently select/save
  assert.equal(first.save("pc1-agent"), true);
  const restarted = createTargetPreference(options);
  assert.equal(restarted.restore("agent"), "pc1-agent");
  assert.deepEqual(calls, [{key,value:"pc1-agent"}]);
  assert.ok(states.at(-1).includes("no connection or message sent"));
  const otherDirectory = createTargetPreference({...options,key:key+"other/"});
  assert.equal(otherDirectory.restore("other-default"), "other-default");
  for (const value of ["", "bad target", "agent?token=secret", {}, "a".repeat(129)]) {
    assert.equal(validTargetParticipant(value), false);
    assert.throws(() => first.save(value), /participant ID/);
  }
  assert.equal(calls.length, 1);
});

test("malformed or unavailable preference retains current input and reports safe limitation", () => {
  const states = [];
  const invalid = createTargetPreference({key:"owned", getStorage:() => ({getItem:()=>'{"token":"do-not-echo"}'}),
    onState:message => states.push(message)});
  assert.equal(invalid.restore("pc1-agent"), "pc1-agent");
  assert.ok(states.at(-1).includes("invalid"));
  assert.ok(!states.at(-1).includes("do-not-echo"));
  const blocked = createTargetPreference({key:"owned", getStorage:() => {throw new Error("private-error");},
    onState:message => states.push(message)});
  assert.equal(blocked.restore("pc1-agent"), "pc1-agent");
  assert.equal(blocked.save("pc1-agent"), false);
  assert.ok(states.at(-1).includes("not saved"));
  assert.ok(states.every(message => !message.includes("private-error")));
});
