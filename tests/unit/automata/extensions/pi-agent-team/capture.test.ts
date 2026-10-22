import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { Capture, clip } = await import(pathToFileURL(join(process.env.PI_EXTENSION_TEST_ROOT, "capture.ts")));

test("cursor reads are non-consuming, exclusive, independent and budgeted", () => {
  const c = new Capture();
  c.append("first");
  const first = c.read(undefined);
  assert.equal(first.records[0].value, "first");
  assert.deepEqual(c.read(undefined), first);
  assert.equal(c.read(first.nextCursor).records.length, 0);
  c.append("second");
  assert.equal(c.read(first.nextCursor).records[0].value, "second");
  assert.throws(() => new Capture().read(first.nextCursor), /another worker/);
  assert.throws(() => c.read("garbage"));
  assert.throws(() => c.read(undefined, 0));
});

test("expired cursor exposes gaps; blocked reads never skip records", () => {
  const c = new Capture(1500, 1000);
  const start = c.read(undefined).nextCursor;
  c.append("x".repeat(500)); c.append("y".repeat(500)); c.append("z".repeat(500));
  const blocked = c.read(start, 256);
  assert.equal(blocked.gap, true);
  assert.equal(blocked.droppedRecords, 1);
  assert.equal(blocked.blocked, true);
  assert.equal(blocked.records.length, 0);
  assert.equal(c.read(blocked.nextCursor, blocked.requiredBytes).records[0].value[0], "y");
});

test("large capture records are explicitly truncated and remain retrievable", () => {
  const c = new Capture(2000, 1000);
  c.append("😀".repeat(1000));
  const result = c.read(undefined, 2000);
  assert.equal(result.truncatedRecords, 1);
  assert.equal(result.records[0].value.truncated, true);
});

test("UTF-8 clipping preserves complete characters at exact byte boundaries", () => {
  for (const [text, expected] of [
    ["A😀B", ["", "A", "A", "A", "A", "A😀", "A😀B"]],
    ["กข", ["", "", "", "ก", "ก", "ก", "กข"]],
    ["A�B", ["", "A", "A", "A", "A�", "A�B"]],
    ["\uFEFFA", ["", "", "", "\uFEFF", "\uFEFFA"]],
  ]) {
    expected.forEach((prefix, budget) => {
      assert.equal(clip(text, budget), prefix, `${text}: ${budget} bytes`);
    });
  }
  assert.equal(clip("A�B", 4), "A�", "a literal replacement character is not a partial code point");
});

test("capture read budgets accept exact bounds and reject invalid values", () => {
  const c = new Capture();
  c.append("value");
  for (const budget of [256, 131072]) assert.equal(c.read(undefined, budget).records.length, 1);
  for (const budget of [255, 131073, -1, 1.5, NaN, Infinity]) {
    assert.throws(() => c.read(undefined, budget), /maxBytes/);
  }
});

test("cursor sequences reject negative, fractional, future and unsafe positions", () => {
  const c = new Capture();
  c.append("value");
  const [identity, next] = JSON.parse(Buffer.from(c.read(undefined).nextCursor, "base64url").toString());
  for (const position of [-1, 0.5, next + 1, Number.MAX_SAFE_INTEGER + 1, "1", null]) {
    const cursor = Buffer.from(JSON.stringify([identity, position])).toString("base64url");
    assert.throws(() => c.read(cursor), /invalid/);
  }
  assert.equal(c.read(c.read(undefined).nextCursor).records.length, 0);
});
