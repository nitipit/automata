import { createPlayspace, createPlayspaceRouter, evaluateTrustedDefinition } from "./lib/playspace.js";
import { initialSnapshot, starterDefinition } from "./component.js";

/** Actual page orchestration; dependencies are explicit for focused lifecycle tests. */
export function createStarter({ elements, adaptiveUI, createClient, auth, recovery }) {
  let alive = true;
  let intent = 0;
  let draftRevision = 0;
  let request;
  const listeners = [];
  const show = message => { if (alive) elements.status.textContent = message; };
  const current = epoch => alive && epoch === intent;
  const router = createPlayspaceRouter({ createClient, onState(packet) {
    if (!alive) return;
    if (packet.status === "connected") elements.connection.textContent = "Authenticated connection";
    if (packet.status === "disconnected") {
      elements.connection.textContent = "Disconnected; explicit Connect required";
      if (request && request.phase !== "terminal") {
        request.phase = "terminal";
        show("Delivery interrupted/uncertain; no automatic replay");
      }
    }
    if (packet.status === "handler_error") show("Response handler failed; no automatic retry");
  } });
  const runtime = createPlayspace({ root: elements.root,
    loadDefinition(record) {
      if (record.id !== starterDefinition.id || record.source !== starterDefinition.source ||
          record.css !== starterDefinition.css) throw new Error("Untrusted definition revision");
      return evaluateTrustedDefinition(record, adaptiveUI);
    },
    onChange() { draftRevision++; show("Draft changed; Save to retain this version"); },
    onError: () => show("Component validation/lifecycle failed; inspect the authored contract"),
    onEvent(event) {
      if (!alive) return;
      if (!router.isConnected()) { show("Disconnected; authenticate and explicitly Connect before Send"); return; }
      if (request && request.phase !== "terminal" && request.isCurrent()) {
        show("A request is pending; no duplicate sent"); return;
      }
      const epoch = intent;
      const active = { phase: "sending" };
      request = active; // before send: Router callbacks may be synchronous
      const isCurrent = () => current(epoch) && request === active && event.isCurrent();
      active.isCurrent = isCurrent;
      const fail = message => {
        if (!isCurrent() || active.phase === "terminal") return;
        active.phase = "terminal";
        show(message);
      };
      show("Sending; awaiting forwarding receipt");
      try {
        const sent = router.send(elements.target.value.trim(), event.payload, {
          expectReply: true, isCurrent,
          onResponse(packet) {
            if (!isCurrent() || active.phase === "terminal") return;
            if (packet.type === "route_closed") {
              fail("Route closed; delivery uncertain; no automatic replay");
              return;
            }
            const receipt = packet.metadata?.pi?.type;
            if (packet.type === "response" && receipt === "admitted" && packet.final === false) {
              active.phase = "admitted";
              show("Agent admitted request; awaiting reply");
            } else if (packet.type === "response" && receipt === "reply" && packet.final === true) {
              active.phase = "terminal";
              try {
                runtime.update(event.id, packet.payload);
                show("Reply applied to originating component; Save to retain it");
              } catch { show("Invalid reply or reconstruction failure; last good result retained"); }
            } else if (packet.type === "response" && receipt === "rejected") {
              fail("Agent rejected request; no automatic retry");
            } else {
              fail("Unexpected receipt; delivery uncertain; component not updated");
            }
          },
        });
        void sent.accepted.then(result => {
          if (!isCurrent() || active.phase === "terminal") return;
          if (result.status !== "forwarded") { fail("Request was not forwarded; no automatic retry"); return; }
          if (active.phase === "sending") {
            active.phase = "forwarded";
            show("Forwarded; this is not agent completion");
          }
        }, () => fail("Forwarding failed or uncertain; no automatic retry"));
      } catch { fail("Send failed; check connection and destination; no automatic retry"); }
    },
  });
  function invalidate() {
    ++intent; // before close, flush, load, auth or any other await
    request = undefined;
    router.disconnect();
    return intent;
  }
  async function connect() {
    if (!alive) return false;
    const epoch = invalidate();
    const target = elements.target.value.trim();
    elements.connection.textContent = "Checking existing pairing…";
    try {
      const status = await auth.status();
      if (!current(epoch)) return false;
      if (!target) throw new Error("Explicit destination required");
      const session = auth.connection(status);
      if (!current(epoch)) return false;
      const connected = await router.connectSession(session);
      if (!current(epoch)) return false;
      elements.connection.textContent = connected ? `Connected; destination ${target}` : "Connection unavailable";
      return connected;
    } catch {
      if (current(epoch)) {
        router.disconnect();
        elements.connection.textContent = "Not connected; authorized pairing and explicit destination required";
      }
      return false;
    }
  }
  async function pair(code = elements.code.value) {
    if (!alive) return false;
    const epoch = invalidate();
    elements.code.value = ""; // one-use code never enters a snapshot
    try {
      const status = await auth.pair(code);
      if (!current(epoch)) return false;
      elements.connection.textContent = status.authenticated ? "Paired; press Connect separately" : "Not paired";
      return status.authenticated === true;
    } catch {
      if (current(epoch)) elements.connection.textContent = "Pairing failed or uncertain; check authorized operator status";
      return false;
    }
  }
  async function status() {
    if (!alive) return false;
    const epoch = intent;
    try {
      const result = await auth.status();
      if (!current(epoch)) return false;
      elements.connection.textContent = result.authenticated ?
        (router.isConnected() ? "Paired and connected" : "Paired; press Connect separately") : "Not paired";
      return result.authenticated;
    } catch {
      if (current(epoch)) elements.connection.textContent = "Auth unavailable; local draft remains usable";
      return false;
    }
  }
  async function save() {
    if (!alive) return false;
    const epoch = intent;
    const revision = draftRevision;
    try {
      const result = await recovery.save(runtime.snapshot());
      if (current(epoch)) show(!result ? "Not saved; draft retained" : revision === draftRevision ?
        "Saved locally; this origin/profile only" : "Earlier snapshot saved; current edits are not saved");
      return result;
    } catch {
      if (current(epoch)) show("Not saved; invalid draft; last good cache retained");
      return false;
    }
  }
  async function restore() {
    if (!alive) return false;
    const epoch = invalidate();
    try {
      await recovery.flush();
      if (!current(epoch)) return false;
      const snapshot = await recovery.load();
      if (!current(epoch)) return false;
      if (snapshot === null) { show("No recoverable snapshot; current draft retained"); return false; }
      runtime.replace(snapshot);
      show("Restored draft only; disconnected; no sends replayed");
      return true;
    } catch {
      if (current(epoch)) show("Recovery rejected; last good draft retained; cache not erased");
      return false;
    }
  }
  function disconnect() {
    if (!alive) return;
    invalidate();
    show("Disconnected; outstanding delivery may be uncertain; no replay");
  }
  function dispose() {
    if (!alive) return;
    ++intent;
    alive = false;
    request = undefined;
    router.dispose();
    runtime.dispose();
    recovery.dispose();
    for (const [element, event, handler] of listeners) element.removeEventListener(event, handler);
  }
  const bind = (element, event, handler) => {
    element.addEventListener(event, handler);
    listeners.push([element, event, handler]);
  };
  for (const [name, action] of Object.entries({ save, restore, pair, connect, disconnect, status })) {
    bind(elements[name === "status" ? "authStatus" : name], "click", () => { void action(); });
  }
  bind(elements.target, "input", disconnect);
  runtime.replace(initialSnapshot());
  const ready = restore(); // draft restoration only; never auth/connect on startup
  return { runtime, router, save, restore, pair, connect, disconnect, status, dispose, ready };
}
