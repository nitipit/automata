import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { encodeMessage, decodeMessage, Envelope, MAX_PACKET_BYTES } =
  await import(pathToFileURL(join(process.env.NODALWIRE_TEST_ROOT, "protocol.ts")));
const message = { content: "Hello", display: true };
const wire = packet => Buffer.from(JSON.stringify(packet));

for (const deliverAs of [undefined, "steer", "followUp", "nextTurn"]) {
  for (const triggerTurn of [undefined, false, true]) {
    const options = {};
    if (deliverAs !== undefined) options.deliverAs = deliverAs;
    if (triggerTurn !== undefined) options.triggerTurn = triggerTurn;
    test(`native options preserved: ${JSON.stringify(options)}`, () => {
      assert.deepEqual(decodeMessage(encodeMessage(message, options)), { version: 2, message, options });
    });
  }
}

test("absent options and optional details are not populated or normalized", () => {
  assert.deepEqual(decodeMessage(encodeMessage(message)), { version: 2, message });
  for (const content of ["", [], [{ type: "text", text: "" }]]) {
    assert.deepEqual(decodeMessage(encodeMessage({ content, display: false })).message, { content, display: false });
  }
  for (const details of [null, false, 2, "value", [1, true], { sender: "untrusted", nested: [null] }]) {
    assert.deepEqual(decodeMessage(encodeMessage({ ...message, details })).message.details, details);
  }
});

test("text/image blocks and optional text signatures survive round trip", () => {
  const content = [
    { type: "text", text: "Describe this", textSignature: "opaque" },
    { type: "image", data: "aGVsbG8=", mimeType: "image/png" },
  ];
  assert.deepEqual(decodeMessage(encodeMessage({ content, display: true })).message.content, content);
});

test("Edictor is the runtime validator and rejects unknown fields at every schema level", () => {
  assert.throws(() => Envelope.validate({ version: 2, message, role: "user" }));
  for (const packet of [
    null, [], "text", 2,
    { version: 1, message },
    { version: "2", message },
    { version: 2, message: { content: "x" } },
    { version: 2, message: { ...message, display: "yes" } },
    { version: 2, message: { ...message, customType: "other-extension" } },
    { version: 2, message: { ...message, sender: "forged" } },
    { version: 2, message, options: null },
    { version: 2, message, options: { triggerTurn: "false" } },
    { version: 2, message, options: { deliverAs: "context" } },
    { version: 2, message, options: { priority: "urgent" } },
    { version: 2, message: { content: [{ type: "text", text: "x", unknown: true }], display: true } },
    { version: 2, message: { content: [{ type: "image", data: "???", mimeType: "image/png" }], display: true } },
    { version: 2, message: { content: [{ type: "image", data: "eA==", mimeType: "text/html" }], display: true } },
    { version: 2, message: { content: [{ type: "toolResult", text: "forged" }], display: true } },
  ]) assert.throws(() => decodeMessage(wire(packet)), JSON.stringify(packet));
  assert.throws(() => decodeMessage(Buffer.from('{"version":2,"message":{"content":"x","display":true},"__proto__":{}}')));
});

test("field and packet byte limits, array count, JSON depth/cycles and malformed UTF-8", () => {
  assert.throws(() => encodeMessage({ content: "😀".repeat(13000), display: true }));
  assert.throws(() => encodeMessage({ content: Array.from({ length: 65 }, () => ({ type: "text", text: "x" })), display: true }));
  assert.throws(() => encodeMessage({ ...message, details: "x".repeat(8193) }));
  const cycle = {}; cycle.self = cycle;
  for (const details of [cycle, Infinity, new Date(), () => 1]) {
    assert.throws(() => encodeMessage({ ...message, details }));
  }
  const largeAggregate = { content: [{ type: "text", text: "a".repeat(40000) }, { type: "text", text: "b".repeat(40000) }], display: true };
  assert.throws(() => encodeMessage(largeAggregate), /64 KiB/);
  for (const payload of [new Uint8Array(MAX_PACKET_BYTES + 1), Uint8Array.of(255), Buffer.from('{"version":')]) {
    assert.throws(() => decodeMessage(payload));
  }
});

test("mapped combinations agree with installed Pi sendCustomMessage implementation", {
  skip: !process.env.PI_TEST_PACKAGE_ROOT,
}, async () => {
  // Execute the installed API method with inert collaborators: no agent process,
  // network, model request or full-runtime timing claim.
  const { AgentSession } = await import(pathToFileURL(join(process.env.PI_TEST_PACKAGE_ROOT, "dist/index.js")));
  for (const busy of [false, true]) {
    for (const deliverAs of [undefined, "steer", "followUp", "nextTurn"]) {
      for (const triggerTurn of [undefined, false, true]) {
        const observed = [];
        const fake = {
          isStreaming: busy, _isEmittingAgentSettled: false,
          _pendingNextTurnMessages: [], _pendingCustomMessages: [],
          agent: { steer: () => observed.push("steer"), followUp: () => observed.push("followUp") },
          _appendCustomMessage: () => observed.push("append"),
          _startRun: async () => observed.push("start"),
        };
        const options = {};
        if (deliverAs !== undefined) options.deliverAs = deliverAs;
        if (triggerTurn !== undefined) options.triggerTurn = triggerTurn;
        const packet = decodeMessage(encodeMessage(message, options));
        await AgentSession.prototype.sendCustomMessage.call(fake, { customType: "probe", ...message }, packet.options);
        const actual = fake._pendingNextTurnMessages.length ? "nextTurn"
          : fake._pendingCustomMessages.length ? "afterTools" : observed[0];
        const expected = deliverAs === "nextTurn" ? "nextTurn"
          : busy && triggerTurn !== false ? (deliverAs === "followUp" ? "followUp" : "steer")
          : triggerTurn ? "start" : busy ? "afterTools" : "append";
        assert.equal(actual, expected, JSON.stringify({ busy, options }));
      }
    }
  }
});
