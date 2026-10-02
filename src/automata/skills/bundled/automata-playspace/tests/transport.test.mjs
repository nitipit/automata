import test from "node:test";
import assert from "node:assert/strict";
import { load } from "./runtime.mjs";
const { createPlayspaceRouter } = await load("playspace.js");
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
function harness() {
  const clients = [], states = [], responses = [], messages = [];
  const facade = createPlayspaceRouter({ onState: state => states.push(state),
    onMessage: packet => messages.push(packet), createClient(callbacks) {
      const opening = deferred();
      const client = { callbacks, opening, connected: false, closed: false,
        connect(credentials) { client.credentials = credentials; return opening.promise; },
        connectSession(session) { client.session = session; return opening.promise; },
        isConnected: () => client.connected,
        send(to, payload, options) {
          client.sent = { to, payload, options };
          client.acceptance = deferred();
          return { id: "request-id", accepted: client.acceptance.promise };
        },
        respond(id, payload, options) { client.replied = { id, payload, options }; return Promise.resolve("ok"); },
        close() {
          client.closed = true;
          callbacks.onState({ status: "old-close" });
          client.sent?.options.onResponse({ type: "route_closed", uncertain: true });
        },
      };
      clients.push(client); return client;
    } });
  return { facade, clients, states, responses, messages };
}

test("explicit connection only; facade forwards exact Router options and inbound reply ID", async () => {
  const h = harness(); assert.equal(h.clients.length, 0);
  assert.throws(() => h.facade.send("agent", {}));
  const connecting = h.facade.connectSession({ participant: "page", wsUrl: "ws://local/session/ws" });
  const client = h.clients[0]; client.connected = true; client.opening.resolve();
  assert.equal(await connecting, true);
  let instanceCurrent = true;
  const sent = h.facade.send("agent", { arbitrary: "component JSON" }, {
    metadata: { pi: {} }, expectReply: true, isCurrent: () => instanceCurrent,
    onResponse: packet => h.responses.push(packet),
  });
  assert.deepEqual(client.sent.payload, { arbitrary: "component JSON" });
  assert.equal(Object.hasOwn(client.sent.options, "isCurrent"), false);
  const packet = { type: "response", final: true, payload: null, metadata: { pi: { type: "reply" } } };
  client.sent.options.onResponse(packet);
  assert.equal(h.responses[0], packet);
  instanceCurrent = false; client.sent.options.onResponse(packet);
  assert.equal(h.responses.length, 1);
  client.acceptance.resolve({ status: "forwarded" });
  assert.deepEqual(await sent.accepted, { status: "forwarded" });
  await h.facade.respond("inbound-route-id", { reply: true }, { final: true });
  assert.equal(client.replied.id, "inbound-route-id");
  client.callbacks.onMessage({ id: "incoming" });
  assert.equal(h.messages.length, 1);
  h.facade.disconnect();
  assert.deepEqual(h.states, [{ status: "disconnected" }]); // synchronous old-close suppressed
  client.callbacks.onMessage({ id: "stale" });
  assert.equal(h.messages.length, 1);
});

test("superseded and disposed connect completions cannot close or relabel newer clients", async () => {
  const h = harness();
  const first = h.facade.connect({ token: "memory-only" });
  const old = h.clients[0];
  const second = h.facade.connectSession({ participant: "new" });
  const next = h.clients[1]; next.connected = true; next.opening.resolve();
  assert.equal(await second, true);
  old.opening.reject(Error("late old failure"));
  assert.equal(await first, false);
  assert.equal(next.closed, false);
  assert.deepEqual(h.states, []);
  h.facade.dispose();
  next.callbacks.onState({ status: "connected" });
  assert.equal(h.states.length, 0);
  assert.throws(() => h.facade.send("agent", null));
  await assert.rejects(h.facade.connect({}));
});
