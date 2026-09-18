import assert from "node:assert/strict";
import fsPromises, { access, appendFile, mkdir, mkdtemp, readFile, rename, symlink, writeFile } from "node:fs/promises";
import { syncBuiltinESMExports } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
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
    await writeFile(path, JSON.stringify({ type: "session", id, cwd, version: 3 }) + "\n" +
      JSON.stringify({ type: "custom", id: `${id}-entry`, customType: "fixture", data: { path: "/old/path" } }) + "\n");
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
  const targetCwd = await mkdtemp(join(root, "destination-"));
  const copies = [];
  SessionManager.forkFrom = (path, target, dir, options) => {
    assert.equal(target, targetCwd);
    assert.equal(dir, undefined);
    assert.match(options.id, /^[0-9a-f-]{36}$/);
    const output = join(target, `${options.id}.jsonl`);
    const entries = readFileSync(path, "utf8").trim().split("\n").map(line => JSON.parse(line));
    entries[0] = { ...entries[0], id: options.id, cwd: target, parentSession: path };
    writeFileSync(output, entries.map(entry => JSON.stringify(entry)).join("\n") + "\n", { flag: "wx" });
    copies.push({ source: path, id: options.id, output });
    return {
      getSessionId: () => options.id,
      getCwd: () => target,
      getSessionFile: () => output,
    };
  };
  const copy = (copyReceipt, sessionIds = ["target"], signal) => call(
    "pi_session_copy", { copyReceipt, sessionIds, targetCwd }, signal,
  );
  return { cwd, ctx, sessions, commands, pi, list, trash, batch, call, copy, copies, targetCwd };
}

async function globalFixture() {
  const f = await fixture();
  let scans = 0;
  SessionManager.listAll = async () => { scans++; return [...f.sessions]; };
  SessionManager.list = async (cwd, dir) => {
    assert.equal(dir, undefined, "global receipt must retain default storage, even for runtime CWD");
    return f.sessions.filter(s => s.cwd === cwd);
  };
  const add = async (id, cwd) => {
    const path = join(f.cwd, `${id}.jsonl`);
    await writeFile(path, JSON.stringify({ type: "session", version: 3, id, cwd }) + "\n" +
      JSON.stringify({ type: "custom", id: `${id}-entry`, customType: "fixture", data: "/old/path" }) + "\n");
    const session = { ...f.sessions[1], id, cwd, path };
    f.sessions.push(session);
    return session;
  };
  const globalList = async (params = {}) => (await f.call("pi_session_list", { scope: "global", ...params })).details;
  return { ...f, add, globalList, scans: () => scans };
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

test("active file inode aliases are protected across copy and trash", async () => {
  const f = await fixture();
  const alias = join(f.cwd, "alias.jsonl");
  await symlink(f.sessions[0].path, alias);
  f.sessions.push({ ...f.sessions[0], id: "alias", path: alias });
  const listing = await f.list();
  await assert.rejects(f.trash(listing.receipt, "alias"), /currently active/);
  await assert.rejects(f.copy(listing.copyReceipt, ["alias"]), /currently active/);
  assert.equal(f.commands.length, 0);
  await access(f.sessions[0].path);
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

test("trash verification does not treat permission errors as disappearance", async () => {
  const f = await fixture();
  const { receipt } = await f.list();
  f.pi.exec = async () => ({ code: 0, stderr: "" });
  const original = fsPromises.access;
  fsPromises.access = async (...args) => {
    if (args[0] === f.sessions[1].path) throw Object.assign(new Error("denied"), { code: "EACCES" });
    return original(...args);
  };
  syncBuiltinESMExports();
  try {
    await assert.rejects(f.trash(receipt), /Cannot verify whether/);
  } finally {
    fsPromises.access = original;
    syncBuiltinESMExports();
  }
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

test("target listing uses default store, exact CWD and scoped trash authority", async () => {
  const f = await fixture();
  const previous = await f.list();
  const targetCwd = join(f.cwd, "destination");
  SessionManager.list = async (cwd, dir) => {
    assert.equal(cwd, targetCwd);
    assert.equal(dir, undefined);
    return [
      { ...f.sessions[1], cwd: targetCwd },
      { ...f.sessions[2], cwd: `${targetCwd}/nested` },
      { ...f.sessions[0], cwd: "" },
    ];
  };
  const result = (await f.call("pi_session_list", { cwd: "destination" })).details;
  assert.equal(result.cwd, targetCwd);
  assert.equal(result.storage, "default");
  assert.equal(typeof result.receipt, "string");
  assert.equal(typeof result.receiptExpiresAt, "string");
  assert.deepEqual(result.sessions.map(s => s.id), ["target"]);
  assert.equal("path" in result.sessions[0], false);
  await assert.rejects(f.trash(previous.receipt), /Unknown or superseded/);
  f.ctx.cwd = targetCwd;
  await assert.rejects(f.trash(result.receipt), /working directory changed/);
  f.ctx.cwd = f.cwd;
  assert.equal((await f.trash(result.receipt)).details.cwd, targetCwd);
  assert.equal(f.commands.length, 1);
});

test("explicit current CWD retains runtime store and trash receipt", async () => {
  const f = await fixture();
  const result = (await f.call("pi_session_list", { cwd: f.cwd })).details;
  assert.equal(result.storage, "runtime");
  assert.equal(typeof result.receipt, "string");
  assert.equal((await f.trash(result.receipt)).details.status, "trashed");
});

test("copy creates distinct IDs, preserves sources and consumes only its own receipt", async () => {
  const f = await fixture();
  const before = await Promise.all(f.sessions.map(s => readFile(s.path, "utf8")));
  const { receipt, copyReceipt } = await f.list();
  assert.notEqual(receipt, copyReceipt);
  const result = await f.copy(copyReceipt, ["target", "other"]);
  assert.equal(result.details.status, "copied");
  assert.equal(result.details.targetCwd, f.targetCwd);
  assert.equal(new Set(f.copies.map(c => c.id)).size, 2);
  assert.deepEqual(result.details.results.map(r => r.sourceSessionId), ["target", "other"]);
  assert.deepEqual(await Promise.all(f.sessions.map(s => readFile(s.path, "utf8"))), before);
  assert.equal(f.commands.length, 0);
  await assert.rejects(f.copy(copyReceipt), /copy receipt/);
  await f.trash(receipt);
});

test("copy preflights all IDs and cannot use trash receipts", async () => {
  for (const invalid of ["current", "unknown", "other"]) {
    const f = await fixture();
    const { copyReceipt, receipt } = await f.list();
    if (invalid === "other") await appendFile(f.sessions[2].path, "changed");
    await assert.rejects(f.copy(copyReceipt, ["target", invalid]));
    await assert.rejects(f.copy(receipt), /copy receipt/);
    await assert.rejects(f.trash(copyReceipt), /Unknown or superseded/);
    assert.equal(f.copies.length, 0);
    assert.equal(f.commands.length, 0);
  }
});

test("remote listing grants separate copy and trash receipts", async () => {
  const f = await fixture();
  const remote = join(f.cwd, "remote");
  f.sessions[1].cwd = remote;
  const data = (await readFile(f.sessions[1].path, "utf8")).trim().split("\n").map(JSON.parse);
  data[0].cwd = remote;
  await writeFile(f.sessions[1].path, data.map(e => JSON.stringify(e)).join("\n") + "\n");
  SessionManager.list = async (cwd, dir) => {
    assert.equal(cwd, remote);
    assert.equal(dir, undefined);
    return f.sessions;
  };
  const listing = (await f.call("pi_session_list", { cwd: remote })).details;
  assert.equal(typeof listing.receipt, "string");
  assert.equal((await f.copy(listing.copyReceipt)).details.status, "copied");
  await assert.rejects(f.trash(listing.copyReceipt), /Unknown or superseded/);
  await f.trash(listing.receipt);
  assert.equal(f.commands.length, 1);
});

test("copy rejects stale, superseded, expired and runtime-shifted receipts", async () => {
  const f = await fixture();
  const first = await f.list();
  const next = await f.list();
  await assert.rejects(f.copy(first.copyReceipt), /copy receipt/);
  const now = Date.now;
  try {
    Date.now = () => now() + 6 * 60 * 1000;
    await assert.rejects(f.copy(next.copyReceipt), /expired/);
  } finally { Date.now = now; }
  f.ctx.cwd = f.targetCwd;
  await assert.rejects(f.copy(next.copyReceipt), /Runtime working directory changed/);
  assert.equal(f.copies.length, 0);
});

test("copy batch reports partial failure, leaves evidence and prevents retry", async () => {
  const f = await fixture();
  const { copyReceipt } = await f.list();
  const fork = SessionManager.forkFrom;
  SessionManager.forkFrom = (...args) => {
    const result = fork(...args);
    if (f.copies.length === 2) throw new Error("simulated interrupted write");
    return result;
  };
  const lastPath = join(f.cwd, "last.jsonl");
  await writeFile(lastPath, JSON.stringify({ type: "session", id: "last", cwd: f.cwd }) + "\n");
  f.sessions.push({ ...f.sessions[2], id: "last", path: lastPath });
  const listing = await f.list();
  const result = await f.copy(listing.copyReceipt, ["target", "other", "last"]);
  assert.equal(result.isError, true);
  assert.deepEqual(result.details.results.map(r => r.status), ["copied", "failed", "not_attempted"]);
  assert.equal(result.details.results[1].destinationMayContainCopy, true);
  for (const c of f.copies) await access(c.output);
  for (const s of f.sessions) await access(s.path);
  await assert.rejects(f.copy(listing.copyReceipt), /copy receipt/);
  assert.equal(f.commands.length, 0);
});

test("copy detects source changes during fork without deleting the destination", async () => {
  const f = await fixture();
  const { copyReceipt } = await f.list();
  const fork = SessionManager.forkFrom;
  SessionManager.forkFrom = (...args) => {
    const result = fork(...args);
    writeFileSync(f.sessions[1].path, "concurrent writer changed source");
    return result;
  };
  const result = await f.copy(copyReceipt);
  assert.equal(result.isError, true);
  assert.equal(result.details.results[0].destinationMayContainCopy, true);
  assert.match(result.details.results[0].error, /changed since listing/);
  await access(f.copies[0].output);
});

test("copy snapshots an unterminated source and preserves provenance and history", async () => {
  const f = await fixture();
  const source = f.sessions[1];
  const before = (await readFile(source.path, "utf8")).trimEnd();
  await writeFile(source.path, before);
  const { copyReceipt } = await f.list();
  assert.equal((await f.copy(copyReceipt)).details.status, "copied");
  assert.equal(await readFile(source.path, "utf8"), before);
  const copied = (await readFile(f.copies[0].output, "utf8")).trim().split("\n").map(JSON.parse);
  assert.equal(copied[0].parentSession, source.path);
  assert.equal(copied[0].cwd, f.targetCwd);
  assert.deepEqual(copied.slice(1), before.split("\n").map(JSON.parse).slice(1));
  await assert.rejects(access(f.copies[0].source)); // temporary snapshot cleaned up
});

test("copy rejects malformed history rather than silently losing entries", async () => {
  const f = await fixture();
  await appendFile(f.sessions[1].path, "private malformed content\n");
  const { copyReceipt } = await f.list();
  const result = await f.copy(copyReceipt);
  assert.equal(result.isError, true);
  assert.match(result.details.results[0].error, /Malformed session entry/);
  assert.equal(result.details.results[0].error.includes("private malformed"), false);
  assert.equal(f.copies.length, 0);
});

test("copy validates input and destination without side effects", async () => {
  const f = await fixture();
  const { copyReceipt } = await f.list();
  for (const ids of [[], ["target", "target"], [""], Array(101).fill("x")]) {
    await assert.rejects(f.copy(copyReceipt, ids), /unique full session IDs/);
  }
  for (const targetCwd of ["", "   ", "bad\u0000path", null, f.cwd, f.sessions[0].path, join(f.cwd, "missing")]) {
    await assert.rejects(f.call("pi_session_copy", { copyReceipt, sessionIds: ["target"], targetCwd }));
  }
  const controller = new AbortController(); controller.abort();
  await assert.rejects(f.copy(copyReceipt, ["target"], controller.signal), /abort/i);
  assert.equal(f.copies.length, 0);
});

test("concurrent copy calls cannot consume the same receipt twice", async () => {
  const f = await fixture();
  const { copyReceipt } = await f.list();
  const results = await Promise.allSettled([f.copy(copyReceipt), f.copy(copyReceipt, ["other"])]);
  assert.equal(results.filter(r => r.status === "fulfilled").length, 1);
  assert.equal(f.copies.length, 1);
});

test("global discovery classifies CWDs, filters missing, and exposes metadata only", async () => {
  const f = await globalFixture();
  await f.add("orphan", join(f.cwd, "deleted"));
  await f.add("not-directory", f.sessions[0].path);
  const all = await f.globalList();
  assert.equal(all.scope, "global");
  assert.equal(all.storage, "default");
  assert.equal("cwd" in all, false);
  assert.equal(all.totalCount, 5);
  assert.equal(all.sessions.find(s => s.id === "current").current, true);
  assert.equal(all.sessions.find(s => s.id === "orphan").directoryStatus, "missing");
  assert.equal(all.sessions.find(s => s.id === "not-directory").directoryStatus, "unknown");
  for (const s of all.sessions) {
    assert.equal("path" in s, false);
    assert.equal("firstMessage" in s, false);
    assert.equal("content" in s, false);
  }
  const missing = await f.globalList({ directoryStatus: "missing" });
  assert.deepEqual(missing.sessions.map(s => s.id), ["orphan"]);
  await assert.rejects(f.trash(missing.receipt, "target"), /not present/);
  assert.equal(f.commands.length, 0);
});

test("inaccessible directories are unknown, not orphan candidates", async () => {
  const f = await globalFixture();
  const denied = join(f.cwd, "denied");
  await f.add("denied", denied);
  const original = fsPromises.stat;
  fsPromises.stat = async (...args) => {
    if (args[0] === denied) throw Object.assign(new Error("denied"), { code: "EACCES" });
    return original(...args);
  };
  syncBuiltinESMExports();
  try {
    const unknown = await f.globalList({ directoryStatus: "unknown" });
    assert.deepEqual(unknown.sessions.map(s => s.id), ["denied"]);
    assert.equal((await f.globalList({ directoryStatus: "missing" })).sessions.length, 0);
  } finally {
    fsPromises.stat = original;
    syncBuiltinESMExports();
  }
});

test("global receipts bind each source CWD and support explicit batch trash", async () => {
  const f = await globalFixture();
  const one = await f.add("one", join(f.cwd, "deleted-one"));
  const two = await f.add("two", join(f.cwd, "deleted-two"));
  const listing = await f.globalList();
  await assert.rejects(f.trash(listing.receipt, "current"), /currently active/);
  const result = await f.batch(listing.receipt, ["one", "two"]);
  assert.equal(result.details.scope, "global");
  assert.deepEqual(result.details.results.map(r => r.cwd), [one.cwd, two.cwd]);
  for (const s of f.sessions.slice(0, 3)) await access(s.path);
  assert.equal(f.commands.length, 2);
});

test("global copy supports multiple CWDs without changing originals", async () => {
  const f = await globalFixture();
  const one = await f.add("one", join(f.cwd, "missing-one"));
  const two = await f.add("two", join(f.cwd, "missing-two"));
  const listing = await f.globalList();
  const result = await f.copy(listing.copyReceipt, ["one", "two"]);
  assert.equal(result.details.status, "copied");
  assert.deepEqual(result.details.results.map(r => r.sourceCwd), [one.cwd, two.cwd]);
  for (const s of [one, two]) await access(s.path);
  assert.equal(f.commands.length, 0);
});

test("global duplicate IDs are non-selectable even across filtered pages", async () => {
  const f = await globalFixture();
  const other = await f.add("duplicate", join(f.cwd, "missing"));
  f.sessions.push({ ...other, cwd: f.cwd, path: f.sessions[1].path });
  const listing = await f.globalList({ directoryStatus: "missing", limit: 1 });
  assert.equal(listing.sessions[0].selectable, false);
  await assert.rejects(f.copy(listing.copyReceipt, ["duplicate"]), /not present/);
  await assert.rejects(f.trash(listing.receipt, "duplicate"), /not present/);
  assert.equal(f.commands.length, 0);
});

test("pagination is bounded, stable and supersedes prior-page receipts", async () => {
  const f = await globalFixture();
  await f.add("a", f.cwd);
  await f.add("b", f.cwd);
  const first = await f.globalList({ limit: 2 });
  assert.equal(first.sessions.length, 2);
  assert.equal(first.omittedCount, 3);
  const token = first.nextCursor;
  await f.add("later", f.cwd);
  const second = (await f.call("pi_session_list", { cursor: token })).details;
  assert.equal(second.sessions.length, 2);
  await assert.rejects(f.call("pi_session_list", { cursor: token }), /cursor/);
  await assert.rejects(f.trash(first.receipt, first.sessions[0].id), /superseded/);
  const third = (await f.call("pi_session_list", { cursor: second.nextCursor })).details;
  assert.equal(third.sessions.length, 1);
  assert.equal(third.nextCursor, undefined);
  assert.equal(third.omittedCount, 0);
  const ids = [...first.sessions, ...second.sessions, ...third.sessions].map(s => s.id);
  assert.equal(new Set(ids).size, 5);
  assert.equal(ids.includes("later"), false);
  assert.equal(f.scans(), 1);
});

test("concurrent cursor use cannot publish the same page twice", async () => {
  const f = await globalFixture();
  const first = await f.globalList({ limit: 1 });
  const results = await Promise.allSettled([
    f.call("pi_session_list", { cursor: first.nextCursor }),
    f.call("pi_session_list", { cursor: first.nextCursor }),
  ]);
  assert.equal(results.filter(r => r.status === "fulfilled").length, 1);
});

test("pagination refuses to issue receipts for files changed since snapshot", async () => {
  const f = await globalFixture();
  const first = await f.globalList({ limit: 1 });
  for (const session of f.sessions) {
    if (session.id !== first.sessions[0].id) await appendFile(session.path, "changed\n");
  }
  const next = (await f.call("pi_session_list", { cursor: first.nextCursor })).details;
  assert.equal(next.sessions.length, 0);
  assert.equal(next.unavailableCount, 1);
  await assert.rejects(f.trash(next.receipt, "target"), /not present/);
  assert.equal(f.commands.length, 0);
});

test("cursors expire, reject runtime changes and incompatible options", async () => {
  const f = await globalFixture();
  const first = await f.globalList({ limit: 1 });
  await assert.rejects(f.call("pi_session_list", { cursor: first.nextCursor, scope: "global" }), /cursor alone/);
  const now = Date.now;
  try {
    Date.now = () => now() + 6 * 60 * 1000;
    await assert.rejects(f.call("pi_session_list", { cursor: first.nextCursor }), /expired/);
  } finally { Date.now = now; }
  f.ctx.cwd = f.targetCwd;
  await assert.rejects(f.call("pi_session_list", { cursor: first.nextCursor }), /cursor/);
  f.ctx.cwd = f.cwd;
  await f.globalList();
  await assert.rejects(f.call("pi_session_list", { cursor: first.nextCursor }), /cursor/);
});

test("changed orphan status invalidates copy and trash selections", async () => {
  const f = await globalFixture();
  const orphan = await f.add("orphan", join(f.cwd, "restored"));
  const listing = await f.globalList({ directoryStatus: "missing" });
  await mkdir(orphan.cwd);
  await assert.rejects(f.copy(listing.copyReceipt, ["orphan"]), /changed/);
  await assert.rejects(f.trash(listing.receipt, "orphan"), /changed/);
  assert.equal(f.commands.length, 0);
});

test("invalid scope/filter/page input does not scan global store", async () => {
  const f = await globalFixture();
  for (const params of [
    { scope: "all" }, { scope: "global", cwd: f.cwd }, { directoryStatus: "deleted" },
    { limit: 0 }, { limit: 101 }, { limit: 1.5 }, { limit: "2" }, { cursor: "unknown" },
  ]) await assert.rejects(f.call("pi_session_list", params));
  assert.equal(f.scans(), 0);
  assert.equal(f.commands.length, 0);
});

test("invalid target inputs are rejected without listing or trash", async () => {
  const f = await fixture();
  SessionManager.list = async () => assert.fail("invalid input must not list");
  for (const cwd of ["", "   ", "bad\0path", 42, null]) {
    await assert.rejects(f.call("pi_session_list", { cwd }), /non-empty directory path/);
  }
  assert.equal(f.commands.length, 0);
});
