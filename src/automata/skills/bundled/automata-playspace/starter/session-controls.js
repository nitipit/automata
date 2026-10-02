import { createBrowserSessionAuth } from "./router/session.js";
import { createPairingRequest } from "./router/pairing-request.js";
import { createTargetPreference, validTargetParticipant } from "./lib/target-preference.js";
import { createSessionView } from "./session-view.js";

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
  let pendingKind = "", opener, ownedClose = false, requester, requesterError = "", recovery = "";
  let uncertainAction = false;
  const view = createSessionView(get);
  const listeners = [];
  function listen(element, name, fn) { element.addEventListener(name, fn); listeners.push([element, name, fn]); }
  function show(message) { if (alive) state.textContent = message; }
  function updateTarget() { get("selected-target").textContent = target.value.trim() || "No target selected"; }
  function render() {
    view.render({paired, connected, busy, pendingKind, request: requester?.view(),
      recovery: requesterError || recovery, targetValid: validTargetParticipant(target.value.trim())});
    updateTarget();
  }
  function showStatus(status) {
    paired = status.authenticated;
    if (paired) uncertainAction = false;
    if (paired || !uncertainAction) recovery = "";
    get("page-participant").textContent = paired && typeof status.participant === "string" ? status.participant : "Not approved yet";
    show(paired ? "Browser approved" : "Browser not approved / approval expired");
    render();
  }
  async function refresh() {
    if (!alive || busy || !auth) return;
    const epoch = generation;
    try { const status = await auth.status(); if (alive && epoch === generation) showStatus(status); }
    catch { if (alive && epoch === generation) {
      recovery ||= "Cannot check browser approval. Recover the local service, then Check session status. No automatic retry or connection.";
      show("Browser approval unavailable"); render();
    } }
  }
  async function act(kind, action) {
    if (!alive || busy || !auth) return;
    const epoch = ++generation;
    busy = true; pendingKind = kind; render();
    show(kind.startsWith("request") ? "Checking pairing request… · no connection opened" :
      kind === "pair" ? "Pairing browser… · no connection opened" : kind === "forget" ? "Revoking this browser session…" : "Checking pairing for explicit Connect…");
    try { await action(() => alive && epoch === generation); }
    catch { if (alive && epoch === generation) {
      uncertainAction = true;
      recovery = "Request unavailable or response uncertain. Check session status. If still unapproved, ask the operator to check/revoke any orphaned page session before a fresh request. No automatic retry.";
      show(kind === "connect" ? "Connection failed. Check the local service and agent, then explicitly Connect again." : "Browser approval could not be confirmed.");
    } }
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
    // Native modal owns focus trapping/Escape; never focus a collapsed field.
    view.focusNext(busy);
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
      if (current()) { recovery = ""; uncertainAction = false; get("copy-pairing-state").textContent = ""; show("Pairing request ready · no connection opened"); }
    });
  }
  function checkRequest() {
    if (requester?.view()?.state === "expired") { render(); return; }
    void act("request-check", async current => {
      // Status first recovers a delivered cookie after an uncertain claim response.
      const status = await auth.status();
      if (!current()) return;
      if (status.authenticated) {
        showStatus(status);
        show("This browser is already approved. Remove browser approval explicitly before claiming a different request.");
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
  async function copyMessage() {
    const request = requester?.view();
    if (!alive || busy || paired) return;
    if (request?.state !== "pending" || !request.request) { render(); return; }
    const epoch = generation;
    try {
      await navigator.clipboard.writeText(`Please approve pairing ${request.request}`);
      if (alive && epoch === generation) get("copy-pairing-state").textContent = "Copied. Send this message to the agent, then Check approval.";
    } catch {
      if (alive && epoch === generation) get("copy-pairing-state").textContent = "Clipboard unavailable. Select and copy the message above, then send it to the agent.";
    }
  }
  function cancelRequest() {
    if (requester?.view()?.state === "expired") { render(); return; }
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
      if (current()) {
        // Confirmed explicit revocation makes this terminal binding safe to retire.
        if (!status.authenticated && ["redeemed", "expired", "cancelled"].includes(requester?.view()?.state)) requester.clearExpired();
        uncertainAction = false;
        showStatus(status);
      }
    });
  }
  listen(form, "submit", pair);
  listen(get("request-pairing"), "click", startRequest);
  listen(get("copy-pairing-message"), "click", () => { void copyMessage(); });
  listen(get("choose-agent"), "click", () => { get("connection-advanced").open = true; target.focus(); });
  listen(get("done-connection"), "click", closeDialog);
  listen(get("check-pairing-request"), "click", checkRequest);
  listen(get("cancel-pairing-request"), "click", cancelRequest);
  listen(get("check-session-status"), "click", () => { void refresh(); });
  listen(get("advanced-check-session"), "click", () => { void refresh(); });
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
    catch { requesterError = "Pairing request storage is unavailable or malformed. Check session status; ask the operator to repair the request before starting again. Private-code pairing remains available under Advanced."; render(); }
    void refresh();
  }
  catch { recovery = "Pairing unavailable. Use the authoritative 127.0.0.1 local HTTP origin, then Check session status."; show("Browser approval unavailable"); render(); }
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
