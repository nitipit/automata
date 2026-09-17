import assert from "node:assert/strict";
import test from "node:test";
import { createAgentBrowserBridgeClient } from "../../../../src/automata/tools/agent-browser-bridge/browser/client.js";

class FakeWebSocket {
  static instances = [];
  readyState = 0;
  sent = [];
  throwOnSend = false;
  listeners = new Map();

  constructor() {
    FakeWebSocket.instances.push(this);
    queueMicrotask(() => {
      this.readyState = 1;
      this.emit("open", {});
    });
  }

  addEventListener(type, handler) {
    const handlers = this.listeners.get(type) ?? [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  send(raw) {
    if (this.throwOnSend) throw new Error("uncertain transport");
    this.sent.push(JSON.parse(raw));
  }

  close() {
    this.readyState = 3;
    this.emit("close", {});
  }

  emit(type, event) {
    if (type === "message") this.onmessage?.(event);
    for (const handler of this.listeners.get(type) ?? []) handler(event);
  }

  message(value) {
    this.emit("message", { data: JSON.stringify(value) });
  }
}

const location = { protocol: "http:", host: "127.0.0.1:8787", pathname: "/sessions/chat/", hash: "#pair=pair-token" };

test("generic payloads preserve transport, admission, reply, and uncertainty states", async () => {
  const states = [];
  const messages = [];
  const client = createAgentBrowserBridgeClient({
    WebSocketImpl: FakeWebSocket,
    location,
    onState: (state) => states.push(state),
    onMessage: (message) => messages.push(message),
  });
  client.connect();
  await new Promise((resolve) => setImmediate(resolve));
  const socket = FakeWebSocket.instances.at(-1);
  socket.message({ type: "hello_ack", role: "browser", channelId: "channel-1", pendingId: "old-message", agentBusy: false });
  assert.equal(client.getPendingId(), "old-message");
  assert.throws(() => client.sendMessage({ text: "blocked" }), /already pending/);

  socket.message({
    type: "reply",
    envelope: { v: 1, id: "old-reply", kind: "reply", correlationId: "old-message", payload: null },
  });
  assert.equal(client.getPendingId(), undefined);
  assert.deepEqual(messages.at(-1), {
    v: 1,
    id: "old-reply",
    kind: "reply",
    correlationId: "old-message",
    payload: null,
  });

  const payload = JSON.parse('{"text":"hello","context":{"componentId":"chat-1","quote":"line\\nnext"},"constructor":"data","__proto__":{"safe":true}}');
  const sent = client.sendMessage(payload);
  assert.equal(client.getPendingId(), sent.id);
  assert.deepEqual(socket.sent.at(-1), { v: 1, id: sent.id, kind: "message", payload });
  assert.throws(() => client.sendMessage({ text: "second" }), /already pending/);

  const stateCount = states.length;
  for (const type of ['receipt', 'admitted', 'rejected', 'duplicate']) socket.message({type, id: 'stale'});
  assert.equal(states.length, stateCount);
  assert.equal(client.getPendingId(), sent.id);
  socket.message({ type: "receipt", id: sent.id, status: "accepted" });
  assert.equal(client.getPendingId(), sent.id);
  assert.equal(states.at(-1).status, "accepted");
  socket.message({ type: "admitted", id: sent.id });
  assert.equal(states.at(-1).status, "admitted");

  const reply = { text: "done", extra: [null, false, 0, ""] };
  socket.message({ type: "reply", envelope: { v: 1, id: "reply-id", kind: "reply", correlationId: sent.id, payload: reply } });
  assert.equal(client.getPendingId(), undefined);
  assert.deepEqual(messages.at(-1).payload, reply);

  for (const value of [null, false, 0, 1.5, "", [], ["nested"], { constructor: "safe", __proto__: "data" }]) {
    const next = client.sendMessage(value);
    socket.message({ type: "reply", envelope: { v: 1, id: `reply-${next.id}`, kind: "reply", correlationId: next.id, payload: value } });
    assert.equal(client.getPendingId(), undefined);
  }

  socket.throwOnSend = true;
  assert.throws(() => client.sendMessage({ text: "uncertain" }), /uncertain transport/);
  const uncertain = states.at(-1).id;
  assert.throws(() => client.sendMessage(null), /already pending/);
  assert.equal(states.at(-1).uncertain, true);
  assert.equal(client.getPendingId(), uncertain);
  socket.throwOnSend = false;
  socket.message({type: 'duplicate', id: uncertain, status: 'pending'});
  assert.equal(states.at(-1).uncertain, true);
  assert.equal(client.getPendingId(), uncertain);
  socket.message({ type: "disconnected", pendingId: uncertain, message: "uncertain" });
  assert.equal(client.getPendingId(), uncertain);
  socket.message({ type: "reply", envelope: { v: 1, id: "resolved", kind: "reply", correlationId: uncertain, payload: "resolved" } });
  assert.equal(client.getPendingId(), undefined);
});

test("generic JSON bounds reject absent, unsafe, cyclic, sparse, instance, and oversize values", async () => {
  const client = createAgentBrowserBridgeClient({ WebSocketImpl: FakeWebSocket, location });
  client.connect();
  await new Promise((resolve) => setImmediate(resolve));
  const socket = FakeWebSocket.instances.at(-1);
  socket.message({ type: "hello_ack", role: "browser", channelId: "channel-bounds", agentBusy: false });
  assert.throws(() => client.sendMessage(undefined), /non-JSON/);
  assert.throws(() => client.sendMessage(Number.NaN), /finite/);
  assert.throws(() => client.sendMessage(Number.MAX_SAFE_INTEGER + 1), /safe/);
  assert.throws(() => client.sendMessage(1n), /non-JSON/);
  assert.throws(() => client.sendMessage(() => {}), /non-JSON/);
  const sparse = [];
  sparse[1] = "hole";
  assert.throws(() => client.sendMessage(sparse), /sparse/);
  const getter = [];
  Object.defineProperty(getter, "0", { enumerable: true, get() { throw new Error("getter invoked"); } });
  assert.throws(() => client.sendMessage(getter), /data properties/);
  const extra = [];
  extra["01"] = "not an index";
  assert.throws(() => client.sendMessage(extra), /extra properties/);
  assert.throws(() => client.sendMessage(new Date()), /plain JSON/);
  const cycle = {};
  cycle.self = cycle;
  assert.throws(() => client.sendMessage(cycle), /cycle/);
  let nested = null;
  for (let index = 0; index < 33; index++) nested = { value: nested };
  assert.throws(() => client.sendMessage(nested), /nesting/);
  assert.throws(() => client.sendMessage("x".repeat(33 * 1024)), /32 KiB/);
});

test('explicit delivery options and context controls do not interfere with Chat', async () => {
  const deliveries=[], states=[];
  const client=createAgentBrowserBridgeClient({WebSocketImpl:FakeWebSocket,location,
    onDelivery:value=>deliveries.push(value),onState:value=>states.push(value)});
  client.connect(); await new Promise(resolve=>setImmediate(resolve));
  const socket=FakeWebSocket.instances.at(-1);
  socket.message({type:'hello_ack',role:'browser'});
  assert.throws(()=>client.sendMessage(null,{role:'context',deliverAs:'nextTurn'}),/does not advertise/);
  socket.message({type:'hello_ack',role:'browser',deliveryOptions:1});
  const chat=client.sendMessage('hello');
  const context=client.sendMessage({selection:'button'},{role:'context',deliverAs:'nextTurn',slot:'selection'});
  assert.equal(client.getPendingId(),chat.id);
  assert.deepEqual(context.message.delivery,{role:'context',deliverAs:'nextTurn',slot:'selection'});
  const statesBefore=states.length;
  socket.message({type:'context_result',id:context.id,status:'buffered',details:{}});
  assert.equal(deliveries.at(-1).status,'buffered');
  socket.message({type:'context_result',id:'stale',status:'attached'});
  assert.equal(deliveries.length,1);
  socket.message({type:'context_result',id:context.id,status:'attached',details:{}});
  assert.equal(deliveries.at(-1).status,'attached');
  assert.equal(states.length,statesBefore);
  assert.equal(client.getPendingId(),chat.id);
  const inspect=client.inspectContext('selection');
  assert.equal(inspect.message.action,'inspect');
  const clear=client.clearContext();
  assert.equal(clear.message.kind,'context_control');
  assert.equal(Object.hasOwn(clear.message,'slot'),false);
  for(const options of [
    {role:'user',deliverAs:'nextTurn'}, {role:'system'}, {role:null},
    {role:'context',deliverAs:'nextTurn',triggerTurn:true},
    {role:'context',deliverAs:'steer',slot:'bad'}, {unknown:true},
  ]) assert.throws(()=>client.sendMessage(null,options));
  socket.message({type:'rejected',id:chat.id});
  assert.equal(client.sendMessage('steer',{role:'user',deliverAs:'steer'}).message.delivery.deliverAs,'steer');
  client.close();
});

test('context reconnect never replays updates and remains bounded', async () => {
 const client=createAgentBrowserBridgeClient({WebSocketImpl:FakeWebSocket,location});
 client.connect(); await new Promise(resolve=>setImmediate(resolve));
 const old=FakeWebSocket.instances.at(-1);
 old.message({type:'hello_ack',role:'browser',deliveryOptions:1});
 for(let i=0;i<32;i++)client.sendMessage(i,{role:'context',deliverAs:'nextTurn'});
 assert.throws(()=>client.sendMessage(null,{role:'context',deliverAs:'nextTurn'}),/capacity/);
 client.connect();await new Promise(resolve=>setImmediate(resolve));
 const next=FakeWebSocket.instances.at(-1);
 next.message({type:'hello_ack',role:'browser',deliveryOptions:1});
 assert.equal(next.sent.length,1); // Only authentication; no replay.
 client.close();
});
