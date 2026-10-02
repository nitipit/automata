import { load, installDOM, FakeNode } from "./runtime.mjs";
installDOM();
const adaptiveUI = await load("adaptive-ui.js");
const { createStarter } = await load("../page.js");
export const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
export const settle = () => new Promise(resolve => setImmediate(resolve));
export const response = (type, payload = null, final = true) => ({
  v: 2, type: "response", id: "route-id", requestId: "request-id",
  from: { id: "agent", kind: "agent" }, final, payload, metadata: { pi: { type } },
});

/** Runs the shipped page composition and authored Base component, not a copied controller. */
export async function starterHarness() {
  const elements = Object.fromEntries(["root", "status", "connection", "target", "code", "save",
    "restore", "pair", "connect", "disconnect", "authStatus"].map(id => [id, new FakeNode()]));
  elements.target.value = "agent";
  const clients = [], saves = [], pairs = [];
  const control = { authWait: null, loadWait: null, flushWait: null, connectWait: null,
    stored: null, onSend: null, authCalls: 0, disposed: false, saveWait: null };
  const auth = {
    async status() { control.authCalls++; return control.authWait ? await control.authWait.promise : { authenticated: true, participant: "page" }; },
    connection(status) { if (!status.authenticated) throw Error("unauthenticated"); return { participant: status.participant, wsUrl: "ws://local/session/ws" }; },
    async pair(code) { pairs.push(code); return { authenticated: true }; },
  };
  const recovery = {
    async load() { return control.loadWait ? await control.loadWait.promise : control.stored; },
    async save(value) {
      saves.push(value);
      if (control.saveWait) await control.saveWait.promise;
      control.stored = structuredClone(value);
      return true;
    },
    async flush() { if (control.flushWait) await control.flushWait.promise; },
    dispose() { control.disposed = true; },
  };
  const page = createStarter({ elements, adaptiveUI, auth, recovery, createClient(callbacks) {
    const client = { connected: false, closed: false, callbacks, sends: [],
      async connectSession(session) {
        client.session = session;
        if (control.connectWait) await control.connectWait.promise;
        client.connected = true;
        callbacks.onState({ status: "connected" });
      },
      async connect() { throw Error("Unexpected bearer connection"); },
      isConnected: () => client.connected,
      close() {
        client.closed = true; client.connected = false;
        callbacks.onState({ status: "disconnected" });
        for (const sent of client.sends) sent.options.onResponse({ type: "route_closed", uncertain: true });
      },
      send(to, payload, options) {
        const accepted = deferred();
        const sent = { to, payload, options, accepted };
        client.sends.push(sent);
        control.onSend?.(sent);
        return { id: "request-id", accepted: accepted.promise };
      },
    };
    clients.push(client); return client;
  } });
  await page.ready;
  return { page, elements, clients, saves, pairs, control,
    send(text = "question") {
      const component = elements.root.children[0];
      component.querySelector("textarea").value = text;
      component.querySelector("form").emit("submit");
      return clients.at(-1)?.sends.at(-1);
    },
    get message() { return elements.status.textContent; },
    get connection() { return elements.connection.textContent; },
    get state() { return page.runtime.snapshot().layout[0].state; },
  };
}
