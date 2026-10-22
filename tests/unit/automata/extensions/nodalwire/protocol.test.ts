import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { encodeMessage, decodeMessage, Envelope, MAX_PACKET_BYTES } =
  await import(pathToFileURL(join(process.env.PI_EXTENSION_TEST_ROOT, "protocol.ts")));
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

test("text and JSON-details byte limits accept the boundary and reject one byte more", () => {
  const text = "x".repeat(48 * 1024);
  assert.equal(decodeMessage(encodeMessage({ content: text, display: true })).message.content, text);
  assert.throws(() => encodeMessage({ content: text + "x", display: true }));
  const details = "x".repeat(8 * 1024 - 2); // JSON string quotes count toward the limit.
  assert.equal(decodeMessage(encodeMessage({ ...message, details })).message.details, details);
  assert.throws(() => encodeMessage({ ...message, details: details + "x" }));
});

test("aggregate envelope accepts exactly 64 KiB and rejects one additional byte", () => {
  const packetMessage = { content: [{ type: "text", text: "" }, { type: "text", text: "" }], display: true };
  const overhead = encodeMessage(packetMessage).byteLength;
  packetMessage.content[0].text = "a".repeat(48 * 1024);
  packetMessage.content[1].text = "b".repeat(MAX_PACKET_BYTES - overhead - 48 * 1024);
  assert.equal(encodeMessage(packetMessage).byteLength, MAX_PACKET_BYTES);
  packetMessage.content[1].text += "b";
  assert.throws(() => encodeMessage(packetMessage), /64 KiB/);
});

test("details nesting and visited-node limits accept exact boundaries", () => {
  const nested = depth => Array.from({ length: depth }).reduce(value => [value], 0);
  assert.deepEqual(decodeMessage(encodeMessage({ ...message, details: nested(16) })).message.details, nested(16));
  assert.throws(() => encodeMessage({ ...message, details: nested(17) }));
  const details = Array(2047).fill(0); // The containing array is also one visited node.
  assert.equal(decodeMessage(encodeMessage({ ...message, details })).message.details.length, 2047);
  assert.throws(() => encodeMessage({ ...message, details: [...details, 0] }));
});
