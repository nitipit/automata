import test from "node:test";
import assert from "node:assert/strict";
import { load } from "./runtime.mjs";
const { bindChatTransport } = await load("transport.js");

class ChatProbe extends EventTarget {
  replies = [];
  statuses = [];
  rejected = [];
  sent = 0;
  setConnection(value) { this.connected = value; }
  setAgentBusy(value) { this.busy = value; }
  setStatus(value) { this.statuses.push(value); }
  interrupt(value) { this.statuses.push(value); }
  reject(value) { this.rejected.push(value); }
  receiveMessage(value) { this.replies.push(value); }
  markSent() { this.sent++; }
  emit(payload) { this.dispatchEvent(new CustomEvent("agent-message", { detail: payload })); }
}
const tick = () => new Promise(resolve => setImmediate(resolve));

test("sample mode is explicitly labeled and retired replies never apply", async () => {
  const chat = new ChatProbe();
  let resolve;
  const states = [];
  const transport = bindChatTransport(chat, { sampleReply: () => new Promise(done => { resolve = done; }), onState: value => states.push(value) });
  transport.sample();
  assert.ok(states.at(-1).includes("not a live agent"));
  chat.emit({ type: "text", data: "sample" });
  assert.equal(chat.sent, 1);
  transport.disconnected();
  resolve({ type: "text", data: "late" });
  await tick();
  assert.deepEqual(chat.replies, []);
  transport.dispose();
  chat.emit({ type: "text", data: "retired" });
  assert.equal(chat.sent, 1);
});

test("live adapter wires complete content, safe failure state and ignores replaced-client replies", async () => {
  const chat = new ChatProbe();
  const clients = [];
  const sent = [];
  let connections = 0;
  const transport = bindChatTransport(chat, { sampleReply: () => ({ type: "text", data: "local" }),
    createLiveClient(options) {
      const client = { options, closed: false,
        async connect() { connections++; options.onState({ status: "connected" }); },
        close() { this.closed = true; }, isConnected: () => true,
        sendMessage(content) { sent.push(content); },
      };
      clients.push(client);
      return client;
    },
  });
  assert.equal(connections, 0); // no automatic provisioning
  await transport.connect({ token: "test-only" }, "authorized-agent");
  assert.equal(chat.connected, true);
  const content = { type: "event", data: { name: "form-submit", target: "ps-form#form-1", detail: { submissionId: "submit-1", previousSubmissionId: null, values: { goal: "complete" } } } };
  chat.emit(content);
  assert.deepEqual(sent, [content]);
  clients[0].options.onState({ status: "rejected", error: { message: "DO-NOT-ECHO" } });
  assert.ok(!chat.rejected.at(-1).includes("DO-NOT-ECHO"));
  await transport.connect({ token: "test-only" }, "authorized-agent");
  assert.equal(clients[0].closed, true);
  clients[0].options.onMessage({ v: 1, kind: "reply", payload: { type: "text", data: "stale" } });
  assert.deepEqual(chat.replies, []);
  clients[1].options.onMessage({ v: 1, kind: "reply", payload: { type: "text", data: "current" } });
  assert.deepEqual(chat.replies, [{ type: "text", data: "current" }]);
  transport.dispose();
  clients[1].options.onMessage({ v: 1, kind: "reply", payload: { type: "text", data: "retired" } });
  assert.equal(chat.replies.length, 1);
  assert.equal(clients[1].closed, true);
});

test("paired transport offline snapshot is not a stale send gate; unknown target closes binding", async () => {
  const chat = new ChatProbe();
  const sent = [], clients = [], states = [];
  const transport = bindChatTransport(chat, {sampleReply:() => null, onState:value => states.push(value),
    createLiveClient(options) {
      const client = {closed:false,
        connect() { throw new Error('Permanent tokens must not be used'); },
        async connectSession(value) { this.session = value; options.onState({status:'connected'}); },
        async status() { return {destinations:[{id:'late-agent',kind:'agent',connected:false}]}; },
        close() { this.closed = true; }, isConnected:() => true,
        sendMessage(payload) { sent.push(payload); },
      };
      clients.push(client);
      return client;
    },
  });
  const session = {wsUrl:'ws://127.0.0.1:8787/session/ws',participant:'page'};
  assert.equal(await transport.connect(session, 'late-agent', {session:true}), true);
  assert.equal(chat.connected, true);
  assert.ok(states.at(-1).includes('offline'));
  assert.deepEqual(sent, []); // status alone never sends an application message
  const payload = {type:'component',data:{name:'ps-text',id:'explicit-new',props:{text:'new request'}}};
  chat.emit(payload);
  assert.deepEqual(sent, [payload]); // later explicit send uses current router presence/admission
  assert.equal(await transport.connect(session, 'ungranted-agent', {session:true}), false);
  assert.equal(chat.connected, false);
  assert.equal(clients.at(-1).closed, true);
  assert.deepEqual(sent, [payload]);
  transport.dispose();
});
