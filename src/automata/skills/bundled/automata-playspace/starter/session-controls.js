import { createBrowserSessionAuth } from "./router/session.js";
import { createTargetPreference, validTargetParticipant } from "./lib/target-preference.js";

/** Pair/forget affect only auth. Connect/disconnect affect only this live binding. */
export function bindSessionControls({ connect, disconnect }) {
  const state = document.querySelector("#pairing-state");
  const code = document.querySelector("#pairing-code");
  const target = document.querySelector("#target-participant");
  const form = document.querySelector("#pairing-form");
  const connectButton = document.querySelector("#connect-session");
  const forgetButton = document.querySelector("#forget-pairing");
  const preferenceState = document.querySelector("#target-preference-state");
  const preference = createTargetPreference({
    key: `automata-playspace-chat-target-v1:${new URL(".", location.href).href}`,
    onState: message => { preferenceState.textContent = message; },
  });
  target.value = preference.restore(target.value); // restore choice only, no auth or socket
  let auth, alive = true, generation = 0, busy = false;
  function show(message) { if (alive) state.textContent = message; }
  function setBusy(value) {
    busy = value;
    for (const element of form.elements) element.disabled = value;
    connectButton.disabled = value;
    forgetButton.disabled = value;
  }
  function showStatus(status) {
    show(status.authenticated ? `PAIRED · ${status.participant} · expires ${new Date(status.expiresAt * 1000).toLocaleString()} · connection is explicit` :
      "NOT PAIRED / EXPIRED · obtain a fresh private code from the operator");
  }
  async function refresh() {
    if (!alive || busy || !auth) return;
    const epoch = generation;
    try { const status = await auth.status(); if (alive && epoch === generation) showStatus(status); }
    catch { if (alive && epoch === generation) show("AUTH UNAVAILABLE · start/recover the local service explicitly; no automatic reconnect"); }
  }
  async function act(action) {
    if (!alive || busy || !auth) return;
    const epoch = ++generation;
    setBusy(true);
    try { await action(() => alive && epoch === generation); }
    catch { if (alive && epoch === generation) show("AUTH / CONNECTION ERROR · check service, code expiry and selected target; no automatic retry"); }
    finally { code.value = ""; if (alive) setBusy(false); }
  }
  function pair(event) {
    event.preventDefault();
    const secret = code.value;
    code.value = "";
    void act(async current => {
      const status = await auth.pair(secret);
      if (current()) showStatus(status);
    });
  }
  function open() {
    const to = target.value.trim(); // explicit target, never inferred from presence
    void act(async current => {
      if (!validTargetParticipant(to)) throw new Error("Select a participant ID");
      preference.save(to); // explicit Connect choice only; storage failure does not change input
      const status = await auth.status();
      if (!current()) return;
      showStatus(status);
      if (!status.authenticated) return;
      await connect(auth.connection(status), to);
    });
  }
  function forget() {
    void act(async current => {
      disconnect();
      const status = await auth.forget();
      if (current()) showStatus(status);
    });
  }
  form.addEventListener("submit", pair);
  connectButton.addEventListener("click", open);
  forgetButton.addEventListener("click", forget);
  try { auth = createBrowserSessionAuth(); void refresh(); }
  catch { show("AUTH UNAVAILABLE · use the authoritative 127.0.0.1 local HTTP origin"); }
  return {
    refresh,
    cancel() { generation++; },
    dispose() {
      alive = false; generation++; code.value = "";
      form.removeEventListener("submit", pair);
      connectButton.removeEventListener("click", open);
      forgetButton.removeEventListener("click", forget);
    },
  };
}
