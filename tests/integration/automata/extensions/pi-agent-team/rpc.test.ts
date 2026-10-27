import assert from "node:assert/strict";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import test from "node:test";

const root = process.env.PI_EXTENSION_TEST_ROOT;
const { Worker, StartupError, TOOL_NAMES } = await import(pathToFileURL(join(root, "worker.ts")));
const { registerAgentTeam, MESSAGE_TYPE } = await import(pathToFileURL(join(root, "index.ts")));
const fake = join(dirname(fileURLToPath(import.meta.url)), "fixtures/fake-worker.mjs");
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(predicate) {
  for (let n = 0; n < 200; n++) { if (await predicate()) return; await delay(5); }
  assert.fail("Timed out waiting for observed condition");
}
const workerOptions = { command: process.execPath, prefixArgs: [fake], requestMs: 1000, shutdownMs: 30 };
const spec = id => ({ workerId: id, cwd: root, provider: "offline", model: "fake", thinking: "off", resources: "minimal" });
async function worker(t, options = {}) {
  const reports = [];
  const config = { ...workerOptions, ...options, requestMs: 1000 };
  const instance = new Worker(spec(`worker-${Math.random()}`), r => reports.push(r), config);
  t.after(() => instance.stop());
  await instance.start();
  config.requestMs = options.requestMs ?? workerOptions.requestMs;
  return { instance, reports };
}

function fixture(options = {}) {
  const tools = new Map(), handlers = new Map(), messages = [], entries = [], notices = [];
  const pi = {
    registerTool(tool) { tools.set(tool.name, tool); },
    on(event, fn) { handlers.set(event, fn); },
    appendEntry(customType, data) { entries.push({ type: "custom", customType, data }); },
    sendMessage(message, options) { messages.push({ message, options }); },
  };
  const ctx = { hasUI: true, ui: { notify: (...args) => notices.push(args) }, sessionManager: {
    getSessionId: () => "parent", getBranch: () => entries,
  } };
  registerAgentTeam(pi, { workerOptions, batchMs: 5, ...options });
  return { pi, ctx, tools, handlers, messages, entries, notices,
    emit: (event, data = {}) => handlers.get(event)?.(data, ctx),
    async call(name, params, signal) {
      return tools.get(name).execute("call-1", params, signal, undefined, ctx);
    },
  };
}

test("verified startup is idle and sends no prompt", async t => {
  const { instance, reports } = await worker(t);
  assert.equal(instance.state, "idle");
  assert.equal(instance.snapshot().verified.model.id, "fake");
  assert.equal(reports.length, 0);
  assert.deepEqual(instance.events.read(undefined).records.map(r => r.value.command), ["get_state"]);
});

test("waits for settled, not agent_end; duplicate settlement yields one report", async t => {
  const { instance, reports } = await worker(t);
  const receipt = await instance.send("prompt", "duplicate", "task-1");
  assert.equal(receipt.completed, false);
  await until(() => instance.events.read(undefined).records.some(r => r.value.type === "agent_end"));
  assert.equal(reports.length, 0);
  assert.equal(instance.state, "working");
  await until(() => reports.length);
  assert.equal(reports.length, 1);
  assert.equal(reports[0].summary, "duplicate");
  assert.equal(reports[0].outcome, "settled");
  assert.equal(instance.state, "idle");
  await assert.rejects(instance.send("prompt", "new", "task-1"), /already used/);
});

test("multiple workers have isolated streams, sessions and request IDs", async t => {
  const a = await worker(t), b = await worker(t);
  assert.notEqual(a.instance.snapshot().verified.sessionId, b.instance.snapshot().verified.sessionId);
  const receipts = await Promise.all([a.instance.send("prompt", "A", "task-a"), b.instance.send("prompt", "B", "task-b")]);
  assert.notEqual(receipts[0].requestId, receipts[1].requestId);
  await until(() => a.reports.length && b.reports.length);
  assert.equal(a.reports[0].summary, "A"); assert.equal(b.reports[0].summary, "B");
  assert.throws(() => b.instance.events.read(a.instance.events.read(undefined).nextCursor));
});

test("chunk boundaries, UTF-8 and Unicode line separators preserve framing", async t => {
  const { instance, reports } = await worker(t);
  await instance.send("prompt", "chunks", "task");
  await until(() => reports.length);
  assert.equal(instance.snapshot().protocolLoss, 0);
  const event = instance.events.read(undefined).records.find(r => r.value.type === "message_update");
  assert.equal(event.value.delta, "สวัสดี\u2028still-one-record\u2029");
});

test("rejected and handled prompts do not leave phantom busy assignments", async t => {
  const { instance, reports } = await worker(t);
  await assert.rejects(instance.send("prompt", "reject", "rejected"), /Rejected/);
  assert.equal(instance.state, "idle");
  assert.equal(instance.snapshot().taskId, undefined);
  const receipt = await instance.send("prompt", "handled", "handled");
  assert.equal(receipt.disposition, "handled");
  assert.equal(instance.state, "idle");
  assert.equal(reports[0].outcome, "handled");
});

test("unknown timeout is retained, blocks redispatch, and recovers a late rejection", async t => {
  const { instance } = await worker(t, { requestMs: 40 });
  await assert.rejects(instance.send("prompt", "late-reject", "uncertain"), error => error.unknownOutcome === true && !!error.requestId);
  assert.equal(instance.snapshot().requests[0].outcome, "unknown");
  await assert.rejects(instance.send("prompt", "new", "new"), /uncertain/);
  await until(() => instance.snapshot().requests.length === 0);
  assert.equal(instance.state, "idle");
  assert.equal(instance.snapshot().taskId, undefined);
});

test("lost acceptance never auto-replays; late acceptance does not finish assignment", async t => {
  const { instance } = await worker(t, { requestMs: 40 });
  await assert.rejects(instance.send("prompt", "late", "late"), error => error.unknownOutcome);
  await until(() => instance.snapshot().requests.length === 0);
  assert.equal(instance.state, "working");
  assert.equal(instance.events.read(undefined).records.filter(r => r.value.type === "agent_start").length, 1);
});

test("concurrent new assignments cannot pass the dispatch reservation", async t => {
  const { instance } = await worker(t);
  const first = instance.send("prompt", "slow", "first");
  await assert.rejects(instance.send("prompt", "second", "second"), /Dispatch/);
  await first;
});

test("abort does not promise queue clearing or undo; reports retain aborted evidence", async t => {
  const { instance, reports } = await worker(t);
  await instance.send("prompt", "slow", "task");
  await instance.send("follow_up", "keep this instruction");
  assert.equal(instance.snapshot().queue.followUp.length, 1);
  const result = await instance.abort();
  assert.equal(result.queueCleared, false);
  assert.equal(result.state.queue.followUp[0], "keep this instruction");
  await until(() => reports.length);
  assert.equal(reports[0].aborted, true);
  await assert.rejects(instance.send("prompt", "new", "new"), /queued work/);
});

test("malformed output is flagged without echoing payload; stderr is separate", async t => {
  const { instance, reports } = await worker(t);
  await instance.send("prompt", "malformed", "task");
  await until(() => reports.length);
  assert.equal(reports[0].captureIncomplete, true);
  assert.ok(!JSON.stringify(instance.events.read(undefined)).includes("not-json-secret"));
  assert.match(JSON.stringify(instance.stderr.read(undefined)), /diagnostic สวัสดี/);
});

test("oversize framing is bounded and the next event still parses", async t => {
  const { instance, reports } = await worker(t, { maxLineBytes: 1024 });
  await instance.send("prompt", "oversize", "task");
  await until(() => reports.length);
  assert.equal(instance.snapshot().protocolLoss, 1);
  assert.equal(reports[0].summary, "oversize");
});

test("headless permission dialog is explicitly cancelled, never approved", async t => {
  const { instance, reports } = await worker(t);
  await instance.send("prompt", "dialog", "task");
  await until(() => reports.length);
  const response = instance.events.read(undefined).records.find(r => r.value.type === "dialog_response_observed");
  assert.equal(response.value.cancelled, true);
  assert.equal(response.value.confirmed, false);
});

test("provider error remains evidence, not a task-success classification", async t => {
  const { instance, reports } = await worker(t);
  await instance.send("prompt", "error", "task");
  await until(() => reports.length);
  assert.equal(reports[0].outcome, "settled");
  assert.equal(reports[0].error, "Provider failed");
});

test("crash is reported without breaking another worker", async t => {
  const a = await worker(t), b = await worker(t);
  await a.instance.send("prompt", "crash", "crash");
  await b.instance.send("prompt", "fine", "fine");
  await until(() => a.reports.length && b.reports.length);
  assert.equal(a.instance.state, "failed");
  assert.equal(a.reports[0].outcome, "exited");
  assert.equal(b.reports[0].summary, "fine");
});

test("a pipe failure notifies uncertainty without pretending the live worker exited", async t => {
  const { instance, reports } = await worker(t);
  await instance.send("prompt", "slow", "task");
  // Inject an OS-stream failure at the owned pipe boundary.
  instance.child.stdout.emit("error", new Error("simulated stream error"));
  assert.equal(instance.state, "failed");
  assert.equal(instance.snapshot().exit, undefined);
  assert.equal(reports.length, 1);
  assert.equal(reports[0].outcome, "failed");
  assert.match(reports[0].error, /may still be running/);
  await assert.rejects(instance.send("prompt", "new", "new"), /not ready/);
  await instance.stop();
  assert.equal(reports.length, 1);
});

test("startup setting mismatch shuts down without task dispatch", async () => {
  const instance = new Worker(spec("mismatch"), () => {}, { ...workerOptions, env: { AGENT_FAKE_SCENARIO: "mismatch" } });
  await assert.rejects(instance.start(), /mismatch/);
  assert.ok(instance.snapshot().exit);
  assert.equal(instance.events.read(undefined).records.some(r => r.value.type === "agent_start"), false);
});

test("explicit resume verifies the exact identity", async t => {
  const instance = new Worker({ ...spec("resume"), sessionId: "exact-session" }, () => {}, workerOptions);
  t.after(() => instance.stop());
  await instance.start();
  assert.equal(instance.snapshot().verified.sessionId, "exact-session");
});

test("stop is idempotent and escalates for a stubborn process", async t => {
  const { instance } = await worker(t, { env: { AGENT_FAKE_SCENARIO: "stubborn" } });
  const [a, b] = await Promise.all([instance.stop(), instance.stop()]);
  assert.deepEqual(a, b);
  assert.equal(a.state, "stopped");
  assert.equal(a.exit.signal, "SIGKILL");
});

test("extension tools deliver deduplicated labeled reports and save recovery references", async t => {
  const f = fixture();
  await f.emit("session_start");
  t.after(() => f.emit("session_shutdown"));
  const started = await f.call("agent_start", spec("reviewer"));
  assert.equal(started.isError, undefined);
  const sent = await f.call("agent_send", { workerId: "reviewer", mode: "prompt", text: "duplicate", taskId: "review" });
  assert.equal(sent.details.accepted, true);
  await until(() => f.messages.length);
  await delay(30);
  assert.equal(f.messages.length, 1);
  assert.equal(f.messages[0].message.customType, MESSAGE_TYPE);
  assert.match(f.messages[0].message.content, /not authoritative instructions/);
  assert.deepEqual(f.messages[0].options, { triggerTurn: true, deliverAs: "followUp" });
  const report = await f.call("agent_read", { workerId: "reviewer", view: "report" });
  assert.equal(report.details.taskId, "review");
  let status = await f.call("agent_status", {});
  assert.equal(status.details.pendingParentDeliveries, 1);
  await f.emit("message_end", { message: { role: "custom", ...f.messages[0].message } });
  status = await f.call("agent_status", {});
  assert.equal(status.details.pendingParentDeliveries, 0);
  await f.emit("session_shutdown");
  assert.equal(f.entries.at(-1).data.event, "stopped");
  assert.ok(f.entries.at(-1).data.exit);
  assert.equal(f.notices.length, 0);
});

test("extension rejects duplicate IDs, parent attachment, and simultaneous resume ownership", async t => {
  const f = fixture(); await f.emit("session_start"); t.after(() => f.emit("session_shutdown"));
  assert.equal((await f.call("agent_resume", { ...spec("parent-copy"), sessionId: "parent" })).isError, true);
  const one = f.call("agent_resume", { ...spec("one"), sessionId: "shared" });
  const two = f.call("agent_resume", { ...spec("two"), sessionId: "shared" });
  const results = await Promise.all([one, two]);
  assert.equal(results.filter(r => !r.isError).length, 1);
  const ownedId = results.find(r => !r.isError).details.workerId;
  assert.equal((await f.call("agent_start", spec(ownedId))).isError, true);
});

test("new-session start rejects sessionId before spawning and can reuse the rejected worker ID", async t => {
  const f = fixture(); await f.emit("session_start"); t.after(() => f.emit("session_shutdown"));
  for (const sessionId of ["conversation", "new", "exact-session", "", undefined]) {
    const rejected = await f.call("agent_start", { ...spec("new"), sessionId });
    assert.equal(rejected.isError, true);
    assert.match(rejected.details.error, /agent_resume/);
  }
  assert.equal((await f.call("agent_status", {})).details.workers.length, 0);
  const started = await f.call("agent_start", spec("new"));
  assert.equal(started.isError, undefined);
  assert.equal(started.details.state, "idle");
  const events = (await f.call("agent_read", { workerId: "new", view: "events" })).details.records;
  const args = events.find(r => r.value.command === "get_state").value.data.launchArgs;
  assert.equal(args.includes("--session"), false);
  assert.deepEqual(args[args.indexOf("--exclude-tools") + 1].split(","), TOOL_NAMES);
  assert.ok(TOOL_NAMES.includes("agent_resume"));
  assert.equal(events.some(r => r.value.type === "agent_start"), false);
});

test("resume requires an ID before spawning and forwards the exact identity", async t => {
  const f = fixture(); await f.emit("session_start"); t.after(() => f.emit("session_shutdown"));
  for (const sessionId of [undefined, "", "/path/to/session", null]) {
    assert.equal((await f.call("agent_resume", { ...spec("resumed"), sessionId })).isError, true);
  }
  assert.equal((await f.call("agent_status", {})).details.workers.length, 0);
  const resumed = await f.call("agent_resume", { ...spec("resumed"), sessionId: "exact-session" });
  assert.equal(resumed.isError, undefined);
  assert.equal(resumed.details.verified.sessionId, "exact-session");
  const events = (await f.call("agent_read", { workerId: "resumed", view: "events" })).details.records;
  const args = events.find(r => r.value.command === "get_state").value.data.launchArgs;
  assert.equal(args[args.indexOf("--session") + 1], "exact-session");
  assert.equal(events.some(r => r.value.type === "agent_start"), false);
});

test("resume refuses a different effective identity without dispatching work", async t => {
  const f = fixture({ workerOptions: { ...workerOptions, env: { AGENT_FAKE_SCENARIO: "resume-mismatch" } } });
  await f.emit("session_start"); t.after(() => f.emit("session_shutdown"));
  const result = await f.call("agent_resume", { ...spec("mismatch"), sessionId: "exact-session" });
  assert.equal(result.isError, true);
  assert.equal(result.details.phase, "startup");
  assert.equal(result.details.taskDispatched, false);
  assert.equal(result.details.unknownOutcome, false);
  assert.match(result.details.error, /mismatch/);
  assert.ok(result.details.state.exit);
});

test("failed resume returns stderr and confirmed exit directly, without replay or fallback", async t => {
  const f = fixture({ workerOptions: { ...workerOptions, env: { AGENT_FAKE_SCENARIO: "startup-failure" } } });
  await f.emit("session_start"); t.after(() => f.emit("session_shutdown"));
  const result = await f.call("agent_resume", { ...spec("missing"), sessionId: "missing-session" });
  assert.equal(result.isError, true);
  assert.equal(result.details.phase, "startup");
  assert.equal(result.details.workerId, "missing");
  assert.equal(result.details.taskDispatched, false);
  assert.equal(result.details.unknownOutcome, false);
  assert.equal(result.details.requestOutcomeUnknown, true);
  assert.equal(result.details.state.exit.code, 1);
  assert.equal(result.details.stderr.tail, "No session found matching 'missing-session'\n");
  assert.equal(result.details.stderr.truncated, false);
  assert.match(result.content[0].text, /No session found/);
  assert.equal(f.messages.length, 0);
  const state = (await f.call("agent_status", {})).details;
  assert.equal(state.workers.length, 1);
  assert.equal(state.workers[0].retainedReports, 0);
  assert.equal(state.workers[0].requests.length, 1);
  assert.equal(state.workers[0].requests[0].command, "get_state");
  assert.equal(f.entries.filter(e => e.data.event === "start_failed").length, 1);
});

test("startup diagnostics are bounded UTF-8 tails with explicit truncation", async t => {
  const f = fixture({ workerOptions: { ...workerOptions, env: { AGENT_FAKE_SCENARIO: "startup-diagnostic" } } });
  await f.emit("session_start"); t.after(() => f.emit("session_shutdown"));
  const result = await f.call("agent_start", spec("diagnostic"));
  assert.equal(result.isError, true);
  assert.equal(result.details.stderr.truncated, true);
  assert.ok(Buffer.byteLength(result.details.stderr.tail) <= 4000);
  assert.ok(result.details.stderr.tail.endsWith("\nfinal diagnostic\n"));
  assert.equal(result.details.stderr.tail.includes("\ufffd"), false);
});

test("startup failure without stderr still returns the observed exit", async t => {
  const f = fixture({ workerOptions: { ...workerOptions, env: { AGENT_FAKE_SCENARIO: "startup-silent" } } });
  await f.emit("session_start"); t.after(() => f.emit("session_shutdown"));
  const result = await f.call("agent_start", spec("silent"));
  assert.equal(result.isError, true);
  assert.equal(result.details.state.exit.code, 2);
  assert.equal(result.details.stderr.tail, "");
  assert.equal(result.details.unknownOutcome, false);
});

test("missing executable returns the spawn failure and no task dispatch", async t => {
  const f = fixture({ workerOptions: { ...workerOptions, command: join(root, "nonexistent-executable") } });
  await f.emit("session_start"); t.after(() => f.emit("session_shutdown"));
  const result = await f.call("agent_start", spec("spawn-error"));
  assert.equal(result.isError, true);
  assert.equal(result.details.taskDispatched, false);
  assert.match(result.details.error, /ENOENT/);
  assert.ok(result.details.state.exit);
});

test("startup keeps an unknown outcome when cleanup cannot confirm exit", async t => {
  const instance = new Worker(spec("unconfirmed"), () => {}, { ...workerOptions, requestMs: 10,
    env: { AGENT_FAKE_SCENARIO: "delayed-state" } });
  // Simulate cleanup failing at the stop boundary, then restore it for real cleanup.
  const stop = instance.stop.bind(instance);
  t.after(stop);
  instance.stop = async () => instance.snapshot();
  await assert.rejects(instance.start(), error => error instanceof StartupError &&
    error.unknownOutcome === true && error.state.exit === undefined);
});

test("tool cancellation during preflight prevents assignment dispatch", async t => {
  const f = fixture({ workerOptions: { ...workerOptions, env: { AGENT_FAKE_SCENARIO: "delayed-state" } } });
  await f.emit("session_start"); t.after(() => f.emit("session_shutdown"));
  await f.call("agent_start", spec("slow"));
  const abort = new AbortController();
  const pending = f.call("agent_send", { workerId: "slow", mode: "prompt", text: "do not send", taskId: "no" }, abort.signal);
  setTimeout(() => abort.abort(), 10);
  assert.equal((await pending).isError, true);
  const events = await f.call("agent_read", { workerId: "slow", view: "events" });
  assert.equal(events.details.records.some(r => r.value.type === "agent_start"), false);
});

test("session shutdown suppresses late notifications and stops active workers", async () => {
  const f = fixture(); await f.emit("session_start");
  await f.call("agent_start", spec("worker"));
  await f.call("agent_send", { workerId: "worker", mode: "prompt", text: "slow", taskId: "work" });
  await f.emit("session_shutdown");
  await delay(40);
  assert.equal(f.messages.length, 0);
  assert.ok(f.entries.at(-1).data.exit);
  assert.equal((await f.call("agent_status", {})).isError, true);
});

test("startup timeout and startup cancellation both stop the owned process", async t => {
  const instance = new Worker(spec("timeout"), () => {}, { ...workerOptions, requestMs: 10,
    env: { AGENT_FAKE_SCENARIO: "delayed-state" } });
  await assert.rejects(instance.start(), error => error instanceof StartupError &&
    error.unknownOutcome === false && error.requestOutcomeUnknown === true && !!error.state.exit);
  assert.ok(instance.snapshot().exit);
  const f = fixture({ workerOptions: { ...workerOptions, env: { AGENT_FAKE_SCENARIO: "delayed-state" } } });
  await f.emit("session_start"); t.after(() => f.emit("session_shutdown"));
  const abort = new AbortController();
  const pending = f.call("agent_start", spec("cancelled"), abort.signal);
  await until(async () => (await f.call("agent_status", {})).details.workers.length === 1);
  abort.abort();
  assert.equal((await pending).isError, true);
  const state = (await f.call("agent_status", {})).details.workers[0];
  assert.ok(state.exit);
});

test("concurrent starts enforce the live-worker cap without oversubscription", async t => {
  const f = fixture(); await f.emit("session_start"); t.after(() => f.emit("session_shutdown"));
  const results = await Promise.all(Array.from({ length: 9 }, (_, i) => f.call("agent_start", spec(`cap-${i}`))));
  assert.equal(results.filter(result => !result.isError).length, 8);
  assert.equal((await f.call("agent_status", {})).details.workers.length, 8);
});

test("capture eviction is observable even when the final report remains readable", async t => {
  const { instance, reports } = await worker(t, { captureBytes: 300 });
  const firstCursor = instance.events.read(undefined).nextCursor;
  await instance.send("prompt", "fine", "task");
  await until(() => reports.length);
  assert.equal(instance.events.read(firstCursor).gap, true);
  assert.equal(reports[0].captureIncomplete, true);
  assert.equal(instance.read("report", {}).summary, "fine");
});

test("report retention expires explicitly and task IDs remain protected after eviction", async t => {
  const { instance, reports } = await worker(t);
  for (let n = 0; n < 33; n++) await instance.send("prompt", "handled", `task-${n}`);
  assert.equal(instance.snapshot().retainedReports, 32);
  assert.deepEqual(instance.read("report", { reportId: "", cursor: "" }), instance.read("report", {}));
  assert.throws(() => instance.read("report", { reportId: reports[0].reportId }), /no longer retained/);
  await assert.rejects(instance.send("prompt", "new", "task-0"), /already used/);
});

test("notification capacity is bounded and consumption releases queued batches", async t => {
  const f = fixture(); await f.emit("session_start"); t.after(() => f.emit("session_shutdown"));
  await f.call("agent_start", spec("many"));
  for (let n = 0; n < 18; n++) {
    await f.call("agent_send", { workerId: "many", mode: "prompt", text: "handled", taskId: `task-${n}` });
    if (n < 16) await until(() => f.messages.length === n + 1);
  }
  await delay(30);
  let state = (await f.call("agent_status", {})).details;
  assert.equal(f.messages.length, 16);
  assert.equal(state.pendingParentDeliveries, 16);
  assert.equal(state.pendingReportNotifications, 2);
  await f.emit("message_end", { message: { role: "custom", ...f.messages[0].message } });
  await until(() => f.messages.length === 17);
  assert.equal(f.messages.at(-1).message.details.reports.length, 2);
  state = (await f.call("agent_status", {})).details;
  assert.equal(state.pendingReportNotifications, 0);
});

test("recovery references merge identity with later report records, without reattachment", async t => {
  const f = fixture(); await f.emit("session_start"); t.after(() => f.emit("session_shutdown"));
  await f.call("agent_start", spec("original"));
  await f.call("agent_send", { workerId: "original", mode: "prompt", text: "handled", taskId: "task" });
  await until(() => f.messages.length);
  const restored = fixture();
  restored.entries.push(...f.entries);
  await restored.emit("session_start");
  const status = (await restored.call("agent_status", {})).details;
  assert.equal(status.workers.length, 0);
  assert.equal(status.recovery.length, 1);
  assert.equal(status.recovery[0].cwd, root);
  assert.equal(status.recovery[0].taskId, "task");
  await restored.emit("session_shutdown");
});

test("a report-delivery failure is not automatically replayed", async t => {
  const f = fixture(); await f.emit("session_start"); t.after(() => f.emit("session_shutdown"));
  f.pi.sendMessage = () => { throw new Error("unknown acceptance"); };
  await f.call("agent_start", spec("worker"));
  await f.call("agent_send", { workerId: "worker", mode: "prompt", text: "fine", taskId: "work" });
  await until(() => f.entries.some(e => e.data.event === "started") && (f.handlers.size > 0));
  await delay(100);
  const status = await f.call("agent_status", {});
  assert.match(status.details.notificationError, /outcome unknown/);
  assert.equal((await f.call("agent_read", { workerId: "worker", view: "report" })).details.summary, "fine");
});
