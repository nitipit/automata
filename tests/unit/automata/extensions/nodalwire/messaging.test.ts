import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { registerNodalWire, encodeMessage, decodeMessage, default: register } =
  await import(pathToFileURL(join(process.env.PI_EXTENSION_TEST_ROOT, "index.ts")));
const tick = () => new Promise(resolve => setImmediate(resolve));

function client() {
  const inbox = [];
  let waiter;
  return {
    sent: [], closed: 0,
    push(message) { if (waiter) { const fn = waiter; waiter = undefined; fn(message); } else inbox.push(message); },
    async receive({ signal }) {
      signal.throwIfAborted();
      if (inbox.length) return inbox.shift();
      return new Promise((resolve, reject) => {
        const abort = () => { waiter = undefined; reject(signal.reason); };
        signal.addEventListener("abort", abort, { once: true });
        waiter = message => { signal.removeEventListener("abort", abort); resolve(message); };
      });
    },
    async send(destination, payload, options) {
      this.sent.push({ destination, payload, options });
      return "a".repeat(32); // NWM3 accepted ID is not application acknowledgement.
    },
    async close() { this.closed++; },
  };
}

function fixture({ name, connect } = {}) {
  const node = client();
  const handlers = new Map(), commands = new Map(), flags = new Map();
  const messages = [], notices = [], statuses = [], tools = [];
  const connections = [];
  const pi = {
    on(event, fn) { handlers.set(event, fn); },
    registerFlag(key, value) { flags.set(key, key === "nodalwire-name" ? name : value.default); },
    getFlag(key) { return flags.get(key); },
    registerCommand(key, command) { commands.set(key, command); },
    registerTool(tool) { tools.push(tool); },
    sendMessage(message, options) { messages.push({ message, options }); },
  };
  const ctx = { hasUI: true, ui: {
    notify(...args) { notices.push(args); }, setStatus(...args) { statuses.push(args); },
  } };
  registerNodalWire(pi, async (...args) => { connections.push(args); return connect ? connect(...args) : node; });
  return {
    node, pi, ctx, messages, notices, statuses, flags, connections, tools,
    attempts: () => connections.length,
    emit(event, data = {}) { return handlers.get(event)?.(data, ctx); },
    command(args) { return commands.get("nodalwire").handler(args, ctx); },
    send(to, content, signal, options) {
      const message = typeof content === "string" ? { content, display: true } : content;
      return tools.find(tool => tool.name === "nodalwire_send").execute("call-1", { to, message, options }, signal);
    },
    connection(action, options = {}, signal) {
      return tools.find(tool => tool.name === "nodalwire_connection")
        .execute("connection-1", { action, ...options }, signal, undefined, ctx);
    },
  };
}

const incoming = (content, sender = "python-peer", options) => ({
  sender, payload: encodeMessage(typeof content === "string" ? { content, display: true } : content, options),
});

test("strict version-2 UTF-8 API envelope with bounded bytes", () => {
  const message = { content: "Hello สวัสดี", display: true };
  assert.deepEqual(decodeMessage(encodeMessage(message)), { version: 2, message });
  for (const content of ["a".repeat(65536), "😀".repeat(20000)]) {
    assert.throws(() => encodeMessage({ content, display: true }));
  }
  for (const payload of [Uint8Array.of(255), new Uint8Array(65537),
    Buffer.from("not json"), Buffer.from('{"version":2,"type":"message","text":"hi"}'),
    Buffer.from('{"version":1,"type":"message","text":" "}'), Buffer.from("null"),
    Buffer.from('{"version":2,"message":{"content":"hi","display":true},"role":"user"}')]) {
    assert.throws(() => decodeMessage(payload));
  }
});

test("disabled extension does not load native dependency or start resources", async () => {
  const f = fixture();
  await f.emit("session_start");
  assert.equal(f.attempts(), 0);
  await assert.rejects(f.send("bob", "hi"), /disconnected/);
  await f.emit("session_shutdown");
  // Registering the real entry point is also safe without an installed client.
  register(f.pi);
});

test("failed relay release warns without exposing raw errors or reconnecting", async () => {
  const f = fixture();
  f.node.close = async () => { f.node.closed++; throw new Error("PRIVATE-RELEASE-ERROR"); };
  await f.connection("connect", { name: "release-test" });
  const result = await f.connection("disconnect");
  assert.equal(result.details.status, "disconnected");
  assert.equal(f.node.closed, 1);
  assert.ok(f.notices.some(([text, level]) => /lease may remain/.test(text) && level === "warning"));
  assert.doesNotMatch(JSON.stringify(f.notices), /PRIVATE-RELEASE-ERROR/);
  await f.connection("disconnect");
  assert.equal(f.node.closed, 1);
  assert.equal(f.attempts(), 1);
});

test("busy follow-up does not block later steering; provenance and native options remain explicit", async () => {
  const f = fixture({ name: "pi-test" });
  await f.emit("session_start");
  f.node.push(incoming("first", "python-peer", { deliverAs: "followUp", triggerTurn: true }));
  f.node.push(incoming("second", "coordinator", { deliverAs: "steer", triggerTurn: true }));
  await tick();
  assert.equal(f.messages.length, 2, "receive must not wait for settlement");
  const { message, options } = f.messages[0];
  assert.equal(message.customType, "automata-pi-nodalwire");
  assert.equal(message.details.sender, "python-peer");
  assert.equal(message.details.recipient, "pi-test");
  assert.equal(typeof message.details.deliveryId, "string");
  assert.equal(message.content, "[NodalWire: python-peer → pi-test]\nfirst");
  assert.equal(message.display, true);
  assert.deepEqual(options, { triggerTurn: true, deliverAs: "followUp" });
  assert.deepEqual(f.messages[1].options, { triggerTurn: true, deliverAs: "steer" });
  await f.emit("session_shutdown");
  await f.emit("session_shutdown");
  assert.equal(f.node.closed, 1);
});

test("invalid incoming envelopes/senders are rejected without echoing their bytes", async () => {
  const f = fixture({ name: "pi-test" });
  await f.emit("session_start");
  f.node.push({ sender: "python-peer", payload: Buffer.from("SECRET-invalid-JSON") });
  f.node.push(incoming("secret", "bad\u001bname"));
  f.node.push(incoming("valid"));
  await tick();
  assert.equal(f.messages.length, 1);
  assert.equal(f.notices.length, 1, "invalid-packet warnings are rate limited");
  assert.ok(!JSON.stringify(f.notices).includes("SECRET"));
  await f.emit("session_shutdown");
});

test("image/text provenance cannot be overwritten by peer details; false display/options survive", async () => {
  const f = fixture({ name: "pi-test" });
  await f.emit("session_start");
  const content = [{ type: "image", data: "eA==", mimeType: "image/png" }];
  f.node.push(incoming({ content, display: false, details: { sender: "forged", deliveryId: "forged" } }, "reviewer", { triggerTurn: false }));
  f.node.push({ ...incoming("omitted"), id: "b".repeat(32), reply_to: "c".repeat(32), network: "default" });
  await tick();
  assert.deepEqual(f.messages[0].message.content, [{ type: "text", text: "[NodalWire: reviewer → pi-test]\n" }, ...content]);
  assert.equal(f.messages[0].message.display, false);
  assert.equal(f.messages[0].message.details.sender, "reviewer");
  assert.equal(f.messages[0].message.details.peerDetails.sender, "forged");
  assert.notEqual(f.messages[0].message.details.deliveryId, "forged");
  assert.deepEqual(f.messages[0].options, { triggerTurn: false });
  assert.equal(f.messages[1].options, undefined);
  assert.match(f.messages[1].message.content, /omitted$/);
  assert.deepEqual(Object.keys(f.messages[1].message.details).sort(), ["deliveryId", "recipient", "sender"],
    "native correlation metadata does not alter application provenance or delivery");
  assert.equal(f.node.sent.length, 0, "receiving does not auto-reply or acknowledge");
  await f.emit("session_shutdown");
});

test("pending submissions are bounded, consumption releases capacity, reconnect does not reset it", async () => {
  const f = fixture({ name: "pi-test" });
  await f.emit("session_start");
  for (let n = 0; n < 40; n++) f.node.push(incoming(`deferred-${n}`, "peer", { deliverAs: "nextTurn" }));
  await tick();
  assert.equal(f.messages.length, 32);
  await f.connection("disconnect");
  await f.connection("connect", { name: "pi-test" });
  f.node.push(incoming("still full"));
  await tick();
  assert.equal(f.messages.length, 32);
  await f.emit("message_end", { message: { role: "custom", ...f.messages[0].message } });
  f.node.push(incoming("capacity released"));
  await tick();
  assert.equal(f.messages.length, 33);
  assert.match(f.messages.at(-1).message.content, /capacity released/);
  await f.emit("session_shutdown");
});

test("all option combinations reach Pi without presets or normalization", async () => {
  const f = fixture({ name: "pi-test" });
  await f.emit("session_start");
  const optionsList = [undefined];
  for (const deliverAs of [undefined, "steer", "followUp", "nextTurn"]) {
    for (const triggerTurn of [undefined, false, true]) {
      const options = {};
      if (deliverAs !== undefined) options.deliverAs = deliverAs;
      if (triggerTurn !== undefined) options.triggerTurn = triggerTurn;
      optionsList.push(options);
      f.node.push(incoming("mapped", "peer", options));
    }
  }
  f.node.push(incoming("mapped"));
  await tick();
  assert.deepEqual(f.messages.map(x => x.options), [...optionsList.slice(1), undefined]);
  await f.emit("session_shutdown");
});

test("outbound bytes, cancellation, honest acceptance and no transparent retry", async () => {
  const f = fixture({ name: "pi-test" });
  await f.emit("session_start");
  const signal = new AbortController().signal;
  const result = await f.send("bob", "reply", signal);
  assert.equal(f.node.sent.length, 1);
  assert.equal(decodeMessage(f.node.sent[0].payload).message.content, "reply");
  assert.equal(f.node.sent[0].destination, "bob");
  assert.equal(f.node.sent[0].options.signal, signal);
  assert.deepEqual(result.details, { to: "bob", status: "relay_accepted" });
  assert.match(result.content[0].text, /not confirmed/);
  let calls = 0;
  f.node.send = async () => { calls++; throw new Error("ReceiptTimeout: effect uncertain"); };
  await assert.rejects(f.send("bob", "uncertain"), /effect uncertain/);
  assert.equal(calls, 1);
  await assert.rejects(f.send("bad name", "hi"), /Invalid recipient/);
  await f.emit("session_shutdown");
});

test("send tool requires to and does not accept destination as an alias", async () => {
  const f = fixture({ name: "pi-test" });
  const tool = f.tools.find(tool => tool.name === "nodalwire_send");
  assert.deepEqual(tool.parameters.required, ["to", "message"]);
  assert.ok(!("destination" in tool.parameters.properties));
  await f.emit("session_start");
  await assert.rejects(tool.execute("legacy", { destination: "bob", text: "old schema" }), /Invalid recipient/);
  assert.equal(f.node.sent.length, 0);
  await f.send("bob", "new schema");
  assert.equal(f.node.sent[0].destination, "bob", "native client's positional interface is unchanged");
  await f.emit("session_shutdown");
});

test("commands, failed connection, and explicit disconnect while awaiting receive", async () => {
  const f = fixture();
  await f.command("status");
  assert.deepEqual(f.notices.at(-1), ["Disconnected", "info"]);
  await f.command("connect --name pi-test tcp://127.0.0.1:7777");
  await f.command("status");
  assert.match(f.notices.at(-1)[0], /pi-test at tcp:\/\/127.0.0.1:7777/);
  await f.command("connect --name bad/name");
  assert.equal(f.attempts(), 1, "bad names rejected before changing connection");
  await f.command("disconnect");
  assert.equal(f.node.closed, 1);
  await f.command("unexpected");
  assert.match(f.notices.at(-1)[0], /Usage:/);
  const bad = fixture({ name: "pi-test", connect: async () => { throw new Error("unavailable"); } });
  await bad.emit("session_start");
  assert.match(bad.notices.at(-1)[0], /Could not connect/);
  await bad.emit("session_shutdown");
});

for (const [args, endpoint] of [
  ["connect --name pi-test", "tcp://127.0.0.1:5555"],
  ["connect --name pi-test tcp://127.0.0.1:7777", "tcp://127.0.0.1:7777"],
  ["connect tcp://127.0.0.1:7777 --name pi-test", "tcp://127.0.0.1:7777"],
  ["connect --name=pi-test tcp://127.0.0.1:7777", "tcp://127.0.0.1:7777"],
]) {
  test(`named connect options: ${args}`, async () => {
    const f = fixture();
    await f.command(args);
    assert.equal(f.attempts(), 1);
    assert.deepEqual(f.connections[0].slice(0, 2), ["pi-test", endpoint]);
    await f.command("status");
    assert.equal(f.notices.at(-1)[0], `pi-test at ${endpoint}`);
    await f.command("disconnect");
    assert.equal(f.node.closed, 1);
  });
}

test("invalid connect arguments preserve the current connection", async () => {
  const f = fixture();
  await f.command("connect --name pi-test");
  for (const args of [
    "connect", "connect pi-test", "connect pi-test tcp://127.0.0.1:7777",
    "connect --name", "connect --name --unknown", "connect --name bad/name",
    "connect --name first --name second", "connect --name=first --name=second",
    "connect --name first --name", "connect --name pi-test --unknown",
    "connect --name pi-test --endpoint tcp://127.0.0.1:7777",
    "connect --name pi-test tcp://127.0.0.1:7777 tcp://127.0.0.1:8888",
  ]) {
    await f.command(args);
    assert.equal(f.notices.at(-1)[1], "warning", args);
    assert.equal(f.attempts(), 1, args);
    assert.equal(f.node.closed, 0, args);
    await f.command("status");
    assert.equal(f.notices.at(-1)[0], "pi-test at tcp://127.0.0.1:5555", args);
  }
  await f.send("bob", "still connected");
  await f.emit("session_shutdown");
  assert.equal(f.node.closed, 1);
});

test("connection tool status, validation and disconnect are safe while disconnected", async () => {
  const f = fixture();
  assert.deepEqual((await f.connection("status")).details, { status: "disconnected" });
  await assert.rejects(f.connection("connect"), /valid unique node name/);
  await assert.rejects(f.connection("connect", { name: "bad/name" }), /valid unique node name/);
  await assert.rejects(f.connection("status", { name: "unused" }), /only valid for connect/);
  await assert.rejects(f.connection("disconnect", { endpoint: "unused" }), /only valid for connect/);
  await assert.rejects(f.connection("unknown"), /Unknown connection action/);
  assert.deepEqual((await f.connection("disconnect")).details, { status: "disconnected" });
  assert.equal(f.attempts(), 0);
});

test("connection tool connects, reuses the same route and requires explicit disconnect to change it", async () => {
  const f = fixture();
  const connected = await f.connection("connect", { name: "pi-tool" });
  assert.deepEqual(connected.details, {
    status: "connected", name: "pi-tool", endpoint: "tcp://127.0.0.1:5555",
  });
  assert.deepEqual((await f.connection("status")).details, connected.details);
  assert.deepEqual((await f.connection("connect", { name: "pi-tool" })).details, connected.details);
  await assert.rejects(f.connection("connect", { name: "different" }), /disconnect explicitly/);
  await assert.rejects(f.connection("connect", {
    name: "pi-tool", endpoint: "tcp://127.0.0.1:7777",
  }), /disconnect explicitly/);
  assert.equal(f.attempts(), 1);
  assert.equal(f.node.closed, 0);
  await f.send("bob", "tool-connected reply");
  assert.equal(decodeMessage(f.node.sent[0].payload).message.content, "tool-connected reply");
  assert.deepEqual((await f.connection("disconnect")).details, { status: "disconnected" });
  await f.connection("disconnect");
  assert.equal(f.node.closed, 1);
});

test("connection tool reuses startup connections and connects elsewhere after explicit disconnect", async () => {
  const nodes = [];
  const f = fixture({ name: "pi-test", connect: async () => {
    const node = client(); nodes.push(node); return node;
  } });
  await f.emit("session_start");
  await f.connection("connect", { name: "pi-test" });
  assert.equal(f.attempts(), 1);
  await f.connection("disconnect");
  const result = await f.connection("connect", { name: "new-name", endpoint: "tcp://127.0.0.1:7777" });
  assert.deepEqual(result.details, { status: "connected", name: "new-name", endpoint: "tcp://127.0.0.1:7777" });
  assert.deepEqual(f.connections[1].slice(0, 2), ["new-name", "tcp://127.0.0.1:7777"]);
  assert.equal(nodes[0].closed, 1);
  await f.emit("session_shutdown");
  assert.equal(nodes[1].closed, 1);
});

test("connection tool failures are sanitized, do not retry and leave status usable", async () => {
  const f = fixture({ connect: async () => { throw new Error("SECRET transport failure"); } });
  await assert.rejects(f.connection("connect", { name: "pi-tool" }), error => {
    assert.match(error.message, /Could not connect/);
    assert.ok(!error.message.includes("SECRET"));
    return true;
  });
  assert.equal(f.attempts(), 1);
  assert.deepEqual((await f.connection("status")).details, { status: "disconnected" });
  await f.emit("session_shutdown");
});

for (const action of ["abort", "disconnect", "shutdown"]) {
  test(`pending tool connection: ${action} cancels and closes a late result`, async () => {
    let finish, started, signal;
    const begun = new Promise(resolve => { started = resolve; });
    const late = client();
    const f = fixture({ connect: async (_name, _endpoint, options) => {
      signal = options.signal; started();
      return new Promise(resolve => { finish = resolve; });
    } });
    const controller = new AbortController();
    const connecting = f.connection("connect", { name: "pi-tool" }, controller.signal);
    // No await before this competing call: reservation must precede the first yield.
    await assert.rejects(f.connection("connect", { name: "competitor" }), /attempt is pending/);
    await begun;
    assert.deepEqual((await f.connection("status")).details, { status: "connecting" });
    if (action === "abort") controller.abort();
    else if (action === "disconnect") await f.connection("disconnect");
    else await f.emit("session_shutdown");
    assert.equal(signal.aborted, true);
    finish(late);
    await assert.rejects(connecting, /cancelled, superseded or lost/);
    assert.equal(late.closed, 1);
    assert.equal(f.attempts(), 1);
    assert.deepEqual((await f.connection("status")).details, { status: "disconnected" });
  });
}

test("operator replacement supersedes a pending tool attempt without closing the new client", async () => {
  let finish, started;
  const begun = new Promise(resolve => { started = resolve; });
  const late = client(), operator = client();
  const f = fixture({ connect: async name => {
    if (name === "operator") return operator;
    started(); return new Promise(resolve => { finish = resolve; });
  } });
  const connecting = f.connection("connect", { name: "pi-tool" });
  await begun;
  await f.command("connect --name operator");
  assert.equal(f.connections[0][2].signal.aborted, true);
  finish(late);
  await assert.rejects(connecting, /cancelled, superseded or lost/);
  assert.equal(late.closed, 1);
  assert.equal(operator.closed, 0);
  assert.deepEqual((await f.connection("status")).details, {
    status: "connected", name: "operator", endpoint: "tcp://127.0.0.1:5555",
  });
  await f.emit("session_shutdown");
  assert.equal(operator.closed, 1);
});

test("connection tool respects cancellation before dispatch or before native connect", async () => {
  const f = fixture();
  const stopped = new AbortController(); stopped.abort();
  await assert.rejects(f.connection("connect", { name: "pi-tool" }, stopped.signal), /abort/i);
  const immediate = new AbortController();
  const connecting = f.connection("connect", { name: "pi-tool" }, immediate.signal);
  immediate.abort();
  await assert.rejects(connecting, /cancelled, superseded or lost/);
  assert.equal(f.attempts(), 0);
  assert.deepEqual((await f.connection("status")).details, { status: "disconnected" });
});

test("shutdown during connect cancels pending attempt and closes a late result", async () => {
  let finish, started;
  const begun = new Promise(resolve => { started = resolve; });
  const late = client();
  let signal;
  const f = fixture({ name: "pi-test", connect: async (_name, _endpoint, options) => {
    signal = options.signal; started();
    return new Promise(resolve => { finish = resolve; });
  } });
  const starting = f.emit("session_start");
  await begun;
  await f.emit("session_shutdown");
  assert.equal(signal.aborted, true);
  finish(late);
  await starting;
  assert.equal(late.closed, 1);
  await assert.rejects(f.send("bob", "hi"), /disconnected/);
});
