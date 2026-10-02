import { createBrowserSessionAuth } from "./router/session.js";
import { createPairingRequest } from "./router/pairing-request.js";
import { createTargetPreference, validTargetParticipant } from "./lib/target-preference.js";

/** Auth stays separate from the page-owned shared transport. No action auto-connects. */
export function bindSessionControls({ connect, disconnect, cancelConnect = () => {} }) {
  const get = id => document.getElementById(id);
  const state = get("pairing-state"), code = get("pairing-code"), target = get("target-participant");
  const form = get("pairing-form"), connectButton = get("connect-session"), forgetButton = get("forget-pairing");
  const dialog = get("connection-dialog"), trigger = get("connection-settings"), menu = get("tools-menu");
  const preference = createTargetPreference({
    key: `automata-playspace-chat-target-v1:${new URL(".", location.href).href}`,
    onState: message => { get("target-preference-state").textContent = message; },
  });
  target.value = preference.restore(target.value); // choice only, never auth or socket
  let auth, alive = true, generation = 0, busy = false, paired = false, connected = false;
  let pendingKind = "", opener, ownedClose = false, requester, requesterError = "";
  const requestRegion = get("request-pairing-controls");
  const listeners = [];
  function listen(element, name, fn) { element.addEventListener(name, fn); listeners.push([element, name, fn]); }
  function show(message) { if (alive) state.textContent = message; }
  function updateTarget() { get("selected-target").textContent = target.value.trim() || "No target selected"; }
  function render() {
    // Capture focus before hiding/disabled controls makes the browser move it to BODY.
    const redirectFocus = (paired || busy) && dialog.open &&
      ((!form.hidden && form.contains(document.activeElement)) ||
       (!requestRegion.hidden && requestRegion.contains(document.activeElement)));
    form.hidden = paired;
    for (const element of form.elements) element.disabled = busy || paired;
    // Leave target editable: a new target intent explicitly retires the old binding.
    connectButton.disabled = busy || !paired || !validTargetParticipant(target.value.trim());
    connectButton.textContent = busy && pendingKind === "connect" ? "Connecting…" : "Connect";
    forgetButton.disabled = busy || !paired;
    requestRegion.hidden = paired;
    const request = requester?.view();
    const outstanding = request && ["pending", "approved"].includes(request.state);
    get("request-pairing").disabled = busy || paired || !!requesterError;
    get("check-pairing-request").disabled = busy || paired || !request?.request || !outstanding;
    get("cancel-pairing-request").disabled = busy || paired || !request?.request || !outstanding;
    get("pairing-request-locator").textContent = request?.request || "No request yet";
    get("pairing-request-state").textContent = requesterError || (request ?
      `Request ${request.state} · expires ${new Date(request.expiresAt * 1000).toLocaleTimeString()}` :
      "Request pairing, then ask the agent to approve the displayed locator.");
    get("live-mode").hidden = !connected;
    trigger.textContent = connected ? "Connection" : "Connect";
    trigger.setAttribute("aria-expanded", String(dialog.open));
    updateTarget();
    if (redirectFocus) target.focus();
  }
  function showStatus(status) {
    paired = status.authenticated;
    get("page-participant").textContent = paired && typeof status.participant === "string" ? status.participant : "Not paired yet";
    show(paired ? `Browser paired · ${status.participant} · expires ${new Date(status.expiresAt * 1000).toLocaleString()}` :
      "Browser not paired / pairing expired");
    render();
  }
  async function refresh() {
    if (!alive || busy || !auth) return;
    const epoch = generation;
    try { const status = await auth.status(); if (alive && epoch === generation) showStatus(status); }
    catch { if (alive && epoch === generation) show("Pairing unavailable · recover the local service explicitly; no automatic reconnect"); }
  }
  async function act(kind, action) {
    if (!alive || busy || !auth) return;
    const epoch = ++generation;
    busy = true; pendingKind = kind; render();
    show(kind.startsWith("request") ? "Checking pairing request… · no connection opened" :
      kind === "pair" ? "Pairing browser… · no connection opened" : kind === "forget" ? "Revoking this browser session…" : "Checking pairing for explicit Connect…");
    try { await action(() => alive && epoch === generation); }
    catch { if (alive && epoch === generation) show(kind.startsWith("request") ?
      "Request unavailable or response uncertain · check session status explicitly; if a claim committed without a cookie, ask the operator to revoke it before a fresh request. No automatic retry." :
      "Pairing / connection error · check service, code expiry and target; no automatic retry"); }
    finally {
      // A stale completion must not clear a NEW code or release a newer action.
      if (alive && epoch === generation) { code.value = ""; busy = false; pendingKind = ""; render(); }
    }
  }
  function cancel() {
    generation++; code.value = ""; busy = false; pendingKind = "";
    cancelConnect(); // fence page recovery/import; retire only not-yet-established sockets
    render();
  }
  function closeDialog() {
    cancel();
    if (dialog.open) {
      ownedClose = true;
      try { dialog.close(); } finally { ownedClose = false; }
    }
    opener?.focus();
    render();
  }
  function openDialog() {
    if (!alive || dialog.open) return;
    menu.open = false;
    opener = trigger;
    dialog.showModal(); render(); void refresh();
    // Native modal owns focus trapping/Escape; choose an enabled initial field.
    (paired ? target : get("request-pairing")).focus();
  }
  function pair(event) {
    event.preventDefault();
    const secret = code.value; code.value = "";
    void act("pair", async current => {
      const status = await auth.pair(secret);
      if (current()) showStatus(status);
    });
  }
  function startRequest() {
    void act("request-create", async current => {
      await requester.start();
      if (current()) show("Relay only the displayed locator to the agent and explicitly request approval for an existing page. Then Check approval. No connection opened.");
    });
  }
  function checkRequest() {
    void act("request-check", async current => {
      // Status first recovers a delivered cookie after an uncertain claim response.
      const status = await auth.status();
      if (!current()) return;
      if (status.authenticated) {
        showStatus(status);
        show("This browser is already paired. Forget explicitly before claiming a different request.");
        return;
      }
      const request = await requester.check();
      if (!current()) return;
      if (request.state === "approved") {
        const pairedStatus = await requester.claim();
        if (current()) showStatus(pairedStatus);
      } else if (request.state === "redeemed") {
        show("Request was already claimed but this browser has no session cookie. Ask the operator to revoke the orphaned page session, then create a fresh request. Do not retry the claim.");
      } else show(`Request ${request.state} · no connection opened; approval checks are manual`);
    });
  }
  function cancelRequest() {
    void act("request-cancel", async current => {
      await requester.cancel();
      if (current()) show("Pairing request cancelled · no session revoked or connection opened");
    });
  }
  function openConnection() {
    if (!alive || busy || !auth) return;
    cancelConnect(); // explicit Connect supersedes cache/import work BEFORE its auth wait
    const to = target.value.trim(); // never inferred from presence
    void act("connect", async current => {
      if (!validTargetParticipant(to)) throw new Error("Select a participant ID");
      preference.save(to);
      const status = await auth.status();
      if (!current()) return;
      showStatus(status);
      if (!status.authenticated) return;
      await connect(auth.connection(status), to);
    });
  }
  function forget() {
    void act("forget", async current => {
      disconnect();
      const status = await auth.forget();
      if (current()) showStatus(status);
    });
  }
  listen(form, "submit", pair);
  listen(get("request-pairing"), "click", startRequest);
  listen(get("check-pairing-request"), "click", checkRequest);
  listen(get("cancel-pairing-request"), "click", cancelRequest);
  listen(get("check-session-status"), "click", () => { void refresh(); });
  listen(connectButton, "click", openConnection);
  listen(forgetButton, "click", forget);
  listen(trigger, "click", openDialog);
  listen(get("close-connection"), "click", closeDialog);
  listen(get("cancel-connection"), "click", closeDialog);
  listen(dialog, "cancel", event => { event.preventDefault(); closeDialog(); });
  // Native beforetoggle is synchronous with close(), unlike the queued close event.
  // Retire external closes at their actual transition, so mixed owned/external closes
  // cannot consume guessed FIFO credits or invalidate a newer explicit intent later.
  listen(dialog, "beforetoggle", event => {
    if (event.newState !== "closed" || ownedClose) return;
    cancel();
    const epoch = generation;
    queueMicrotask(() => {
      if (alive && epoch === generation && !dialog.open) { opener?.focus(); render(); }
    });
  });
  listen(dialog, "close", render); // notification only; never cancel or refocus here
  listen(target, "input", () => { cancel(); disconnect(); render(); });
  listen(menu, "click", event => {
    if (event.target.closest("button, a")) {
      menu.open = false;
      if (event.target.closest("button")) menu.querySelector("summary").focus();
    }
  });
  listen(menu, "keydown", event => {
    if (event.key === "Escape") { event.preventDefault(); menu.open = false; menu.querySelector("summary").focus(); }
  });
  render();
  try {
    auth = createBrowserSessionAuth();
    requester = createPairingRequest({auth});
    try { requester.restore(); render(); }
    catch { requesterError = "Transient request storage unavailable or malformed; private-code pairing remains available."; render(); }
    void refresh();
  }
  catch { show("Pairing unavailable · use the authoritative 127.0.0.1 local HTTP origin"); }
  return {
    refresh, cancel,
    selectTarget(to) {
      if (!validTargetParticipant(to)) return false;
      target.value = to; render(); // explicit trusted provisioning, NOT a saved preference
      return true;
    },
    setConnection(message) {
      const demo = message.startsWith("SAMPLE");
      const opening = message.includes("connecting to selected");
      connected = !demo && !opening && message.startsWith("LIVE · authenticated");
      const pill = get("connection");
      pill.textContent = demo ? "Demo · local" : opening ? "Connecting…" : connected ? "Connected" : "Disconnected";
      pill.dataset.state = demo ? "demo" : opening ? "connecting" : connected ? "connected" : "disconnected";
      pill.title = message;
      get("connection-detail").textContent = message;
      render();
    },
    dispose() {
      alive = false; generation++; code.value = "";
      for (const [element, name, fn] of listeners) element.removeEventListener(name, fn);
      if (dialog.open) dialog.close();
    },
  };
}
