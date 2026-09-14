import assert from "node:assert/strict";
import { access, appendFile, mkdtemp, rename, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

// Only temporary fixtures and fake adapters are used; no real Pi store or trash.
const root = process.env.SESSION_TEST_ROOT;
const { default: register } = await import(pathToFileURL(join(root, "pi-sessions.ts")));
const { SessionManager } = await import(pathToFileURL(
  join(root, "node_modules/@earendil-works/pi-coding-agent/index.js"),
));

async function fixture(hasUI = false) {
  const cwd = await mkdtemp(join(root, "case-"));
  const sessions = [];
  for (const id of ["current", "target", "other"]) {
    const path = join(cwd, `${id}.jsonl`);
    await writeFile(path, `${id}\n`);
    sessions.push({
      id, path, cwd, name: id, created: new Date(), modified: new Date(), messageCount: 1,
    });
  }
  const ctx = {
    cwd, hasUI,
    ui: { confirm() { assert.fail("No confirmation dialog should be called"); } },
    sessionManager: {
      getSessionId: () => "current",
      getSessionFile: () => join(cwd, "current.jsonl"),
      getSessionDir: () => cwd,
    },
  };
  SessionManager.list = async (actualCwd, sessionDir) => {
    assert.equal(actualCwd, ctx.cwd);
    assert.equal(sessionDir, cwd);
    return sessions;
  };
  const tools = new Map();
  const commands = [];
  const pi = {
    registerTool(tool) { tools.set(tool.name, tool); },
    async exec(command, args) {
      commands.push([command, args]);
      assert.ok(command === "trash" || command === "gio");
      const path = args.at(-1);
      assert.ok(sessions.some((session) => session.path === path));
      await rename(path, `${path}.trashed`);
      return { code: 0, stderr: "" };
    },
  };
  register(pi);
  const call = (name, params = {}, signal) => tools.get(name).execute(
    "test-call", params, signal, undefined, ctx,
  );
  const list = async () => (await call("pi_session_list")).details;
  const trash = (receipt, sessionId = "target", signal) => call(
    "pi_session_trash", { receipt, sessionId }, signal,
  );
  const batch = (receipt, sessionIds, signal) => call(
    "pi_session_trash", { receipt, sessionIds }, signal,
  );
  return { cwd, ctx, sessions, commands, pi, list, trash, batch, call };
}

for (const hasUI of [true, false]) {
  test(`authorized call needs no dialog (hasUI=${hasUI})`, async () => {
    const f = await fixture(hasUI);
    const { receipt } = await f.list();
    const result = await f.trash(receipt);
    assert.equal(result.details.status, "trashed");
    assert.equal(result.details.sessionId, "target");
    assert.equal(result.details.method, "trash");
    await access(`${f.sessions[1].path}.trashed`);
    await assert.rejects(access(f.sessions[1].path));
    await assert.rejects(f.trash(receipt, "other"), /Unknown or superseded/);
    assert.equal(f.commands.length, 1);
  });
}

test("listing is exact-CWD, bounded, and omits paths and content", async () => {
  const f = await fixture();
  f.sessions[2].cwd = `${f.cwd}/nested`;
  f.sessions.push({ ...f.sessions[2], id: "unknown-cwd", cwd: "" });
  const result = await f.list();
  assert.deepEqual(result.sessions.map((s) => s.id), ["current", "target"]);
  assert.equal(result.sessions[0].current, true);
  for (const session of result.sessions) {
    assert.equal("path" in session, false);
    assert.equal("content" in session, false);
  }
  await assert.rejects(f.trash(result.receipt, "other"), /not present/);
  for (let i = 0; i < 101; i++) {
    f.sessions.push({ ...f.sessions[1], id: `extra-${i}` });
  }
  const bounded = await f.list();
  assert.equal(bounded.sessions.length, 100);
  assert.equal(bounded.omittedCount, 3);
  assert.equal(f.commands.length, 0);
});

test("current ID and current-file aliases are protected", async () => {
  const f = await fixture();
  const { receipt } = await f.list();
  await assert.rejects(f.trash(receipt, "current"), /currently active/);
  f.ctx.sessionManager.getSessionId = () => "different-id";
  await assert.rejects(f.trash(receipt, "current"), /currently active/);
  assert.equal(f.commands.length, 0);
});

test("unknown, superseded, expired receipts and partial IDs are rejected", async () => {
  const f = await fixture();
  const first = await f.list();
  const second = await f.list();
  await assert.rejects(f.trash("unknown"), /Unknown or superseded/);
  await assert.rejects(f.trash(first.receipt), /Unknown or superseded/);
  await assert.rejects(f.trash(second.receipt, "tar"), /not present/);
  const now = Date.now;
  try {
    Date.now = () => now() + 6 * 60 * 1000;
    await assert.rejects(f.trash(second.receipt), /expired/);
  } finally {
    Date.now = now;
  }
  assert.equal(f.commands.length, 0);
});

test("changed CWD and changed file are rejected", async () => {
  const f = await fixture();
  const { receipt } = await f.list();
  f.ctx.cwd = `${f.cwd}/nested`;
  await assert.rejects(f.trash(receipt), /working directory changed/);
  f.ctx.cwd = f.cwd;
  await appendFile(f.sessions[1].path, "changed\n");
  await assert.rejects(f.trash(receipt), /changed since it was listed/);
  assert.equal(f.commands.length, 0);
});

test("missing and duplicate session identities are rejected", async () => {
  const f = await fixture();
  const { receipt } = await f.list();
  const candidate = f.sessions.splice(1, 1)[0];
  await assert.rejects(f.trash(receipt), /missing or its ID is not unique/);
  f.sessions.push(candidate, { ...candidate });
  await assert.rejects(f.trash(receipt), /missing or its ID is not unique/);
  assert.equal(f.commands.length, 0);
});

test("replaced file identity is rejected even at the same path", async () => {
  const f = await fixture();
  const { receipt } = await f.list();
  const path = f.sessions[1].path;
  await rename(path, `${path}.original`);
  await writeFile(path, "target\n");
  await assert.rejects(f.trash(receipt), /changed since it was listed/);
  assert.equal(f.commands.length, 0);
});

test("cancellation prevents trash", async () => {
  const f = await fixture();
  const { receipt } = await f.list();
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(f.trash(receipt, "target", controller.signal), /abort/i);
  assert.equal(f.commands.length, 0);
});

test("gio fallback is recoverable and total failure preserves the file", async () => {
  const f = await fixture();
  const { receipt } = await f.list();
  f.pi.exec = async (command, args) => {
    f.commands.push([command, args]);
    return { code: 1, stderr: "unavailable" };
  };
  await assert.rejects(f.trash(receipt), /No recoverable trash command succeeded/);
  assert.deepEqual(f.commands.map(([command]) => command), ["trash", "gio"]);
  await access(f.sessions[1].path);
  f.pi.exec = async (command, args) => {
    if (command === "trash") return { code: 1, stderr: "unavailable" };
    assert.equal(command, "gio");
    assert.equal(args[0], "trash");
    await rename(args[1], `${args[1]}.trashed`);
    return { code: 0, stderr: "" };
  };
  await assert.rejects(f.trash(receipt), /Unknown or superseded/);
  assert.equal((await f.trash((await f.list()).receipt)).details.method, "gio trash");
});

test("false trash success is rejected", async () => {
  const f = await fixture();
  const { receipt } = await f.list();
  f.pi.exec = async () => ({ code: 0, stderr: "" });
  await assert.rejects(f.trash(receipt), /session file is still present/);
  await access(f.sessions[1].path);
});

test("batch uses one receipt and preserves single-call protection", async () => {
  const f = await fixture();
  const { receipt } = await f.list();
  const result = await f.batch(receipt, ["target", "other"]);
  assert.equal(result.details.status, "trashed");
  assert.deepEqual(result.details.results.map((r) => [r.sessionId, r.status]),
    [["target", "trashed"], ["other", "trashed"]]);
  assert.equal(f.commands.length, 2);
  await access(f.sessions[0].path);
  await assert.rejects(f.batch(receipt, ["other"]), /Unknown or superseded/);
});

test("batch validates every target before moving anything", async () => {
  for (const invalid of ["current", "missing", "other"]) {
    const f = await fixture();
    const { receipt } = await f.list();
    if (invalid === "other") await appendFile(f.sessions[2].path, "changed");
    await assert.rejects(f.batch(receipt, ["target", invalid]));
    assert.equal(f.commands.length, 0);
    await access(f.sessions[1].path);
  }
});

test("batch rejects empty, duplicate, oversized and ambiguous input", async () => {
  const f = await fixture();
  const { receipt } = await f.list();
  for (const sessionIds of [[], ["target", "target"], [""], Array(101).fill("x")]) {
    await assert.rejects(f.batch(receipt, sessionIds), /unique full session IDs/);
  }
  await assert.rejects(f.call("pi_session_trash", { receipt }), /exactly one/);
  await assert.rejects(f.call("pi_session_trash", {
    receipt, sessionId: "target", sessionIds: ["other"],
  }), /exactly one/);
  assert.equal(f.commands.length, 0);
});

test("batch stops on failure and reports completed and unattempted IDs", async () => {
  const f = await fixture();
  const path = join(f.cwd, "last.jsonl");
  await writeFile(path, "last");
  f.sessions.push({ ...f.sessions[2], id: "last", path });
  const { receipt } = await f.list();
  const exec = f.pi.exec;
  f.pi.exec = async (command, args) => {
    if (args.at(-1) === f.sessions[2].path) return { code: 1, stderr: "unavailable" };
    return exec(command, args);
  };
  const result = await f.batch(receipt, ["target", "other", "last"]);
  assert.equal(result.isError, true);
  assert.equal(result.details.status, "incomplete");
  assert.deepEqual(result.details.results.map((r) => r.status),
    ["trashed", "failed", "not_attempted"]);
  await access(f.sessions[2].path);
  await access(path);
  await assert.rejects(f.trash(receipt, "other"), /Unknown or superseded/);
});

test("batch rechecks later targets and reports cancellation after a move", async () => {
  for (const cancel of [false, true]) {
    const f = await fixture();
    const { receipt } = await f.list();
    const controller = new AbortController();
    const exec = f.pi.exec;
    f.pi.exec = async (...args) => {
      const result = await exec(...args);
      if (cancel) controller.abort();
      else await appendFile(f.sessions[2].path, "changed");
      return result;
    };
    const result = await f.batch(receipt, ["target", "other"], controller.signal);
    assert.equal(result.isError, true);
    assert.deepEqual(result.details.results.map((r) => r.status), ["trashed", "failed"]);
    assert.equal(f.commands.length, 1);
    await access(f.sessions[2].path);
  }
});

test("concurrent batch calls cannot claim the same receipt", async () => {
  const f = await fixture();
  const { receipt } = await f.list();
  const results = await Promise.allSettled([
    f.batch(receipt, ["target"]), f.batch(receipt, ["other"]),
  ]);
  assert.equal(results.filter((r) => r.status === "fulfilled").length, 1);
  assert.equal(f.commands.length, 1);
});

test("multiple selected IDs survive re-listing and reordered results", async () => {
  const f = await fixture();
  const first = await f.list();
  await f.trash(first.receipt, "target");
  f.sessions.reverse();
  const next = await f.list();
  assert.equal((await f.trash(next.receipt, "other")).details.sessionId, "other");
});
