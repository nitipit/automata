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
  let uncertainAction = false, timer, owner, autoPaused = false;
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
  function stopWaiting() { clearTimeout(timer); timer = undefined; }
  function canWait() {
    const request = requester?.view();
    return alive && dialog.open && document.visibilityState === "visible" && !busy &&
      !paired && !autoPaused && !requesterError && !recovery && !request?.claimAttempted &&
      !!request?.request && ["pending", "approved"].includes(request.state);
  }
  function schedule() {
    stopWaiting();
    if (canWait()) timer = setTimeout(() => {
      timer = undefined;
      if (canWait()) checkRequest(true);
      else if (alive) render(); // includes expiry: never extend the original TTL
    }, 2000);
  }
  function showStatus(status, recover = true) {
    requester?.confirmSession(status);
    paired = status.authenticated;
    if (paired) uncertainAction = false;
    if (paired || (recover && !uncertainAction)) recovery = "";
    get("page-participant").textContent = paired && typeof status.participant === "string" ? status.participant : "Not approved yet";
    show(paired ? "Browser approved" : "Browser not approved / approval expired");
    render();
  }
  async function refresh(recover = true) {
    return act("status", async current => {
      const status = await auth.status();
      if (current()) showStatus(status, recover);
    });
  }
  async function act(kind, action) {
    if (!alive || busy || !auth) return;
    stopWaiting();
    const epoch = ++generation;
    owner = epoch; busy = true; pendingKind = kind; render();
    show(kind.startsWith("request") ? "Checking pairing request… · no connection opened" :
      kind === "pair" ? "Pairing browser… · no connection opened" : kind === "forget" ? "Revoking this browser session…" :
      kind === "status" ? "Checking browser approval…" : "Checking pairing for explicit Connect…");
    try { await action(() => alive && epoch === generation); }
    catch { if (alive) {
      // Physical single flight means this is still the same binding, even if hidden.
      // A stale failure must stop waiting too, without publishing stale success UI.
      uncertainAction ||= !["status", "request-check"].includes(kind) || !!requester?.view()?.claimUncertain;
      recovery = "Request unavailable or response uncertain. Check session status. If still unapproved, ask the operator to check/revoke any orphaned page session before a fresh request. No automatic retry.";
      if (epoch === generation) show(kind === "connect" ? "Connection failed. Check the local service and agent, then explicitly Connect again." : "Browser approval could not be confirmed.");
    } }
    finally {
      // Fencing never releases the physical lock. Only its owner can settle it.
      if (owner === epoch) {
        owner = undefined; busy = false; pendingKind = "";
        if (alive) {
          if (epoch === generation) code.value = "";
          render(); schedule(); // every resume gets a fresh two-second delay
        }
      }
    }
  }
  function cancel(pause = true) {
    stopWaiting();
    if (pause) autoPaused = true;
    generation++; code.value = "";
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
    autoPaused = false;
    dialog.showModal(); render(); void refresh(false);
    // Native modal owns focus trapping/Escape; never focus a collapsed field.
    view.focusNext(busy);
  }
  function pair(event) {
    event.preventDefault();
    if (!alive || busy || !auth) return;
    const secret = code.value; code.value = "";
    void act("pair", async current => {
      const status = await auth.pair(secret);
      if (current()) showStatus(status);
    });
  }
  function startRequest() {
    void act("request-create", async current => {
      await requester.start();
      if (current()) { recovery = ""; uncertainAction = false; autoPaused = false; get("copy-pairing-state").textContent = ""; show("Waiting for agent approval · no connection opened"); }
    });
  }
  function checkRequest(automatic = false) {
    if (!dialog.open || document.visibilityState !== "visible") return;
    if (requester?.view()?.state === "expired" || (automatic && !canWait())) { render(); return; }
    void act("request-check", async current => {
      const eligible = () => current() && dialog.open && document.visibilityState === "visible";
      if (!automatic) autoPaused = false;
      // Status first recovers a delivered cookie after an uncertain claim response.
      const status = await auth.status();
      if (!eligible()) return;
      if (status.authenticated) {
        showStatus(status);
        show("This browser is already approved. Remove browser approval explicitly before claiming a different request.");
        return;
      }
      if (requester.view()?.claimUncertain) {
        recovery = "The claim outcome is uncertain. Ask the operator to check/revoke the orphaned page session. Do not retry the claim or start a new request.";
        return;
      }
      const request = await requester.check();
      if (!eligible()) return;
      recovery = ""; uncertainAction = false;
      if (request.state === "approved" && !request.claimAttempted) {
        const pairedStatus = await requester.claim();
        if (current()) showStatus(pairedStatus);
      } else if (request.state === "redeemed") {
        show("Request was already claimed but this browser has no session cookie. Ask the operator to revoke the orphaned page session, then create a fresh request. Do not retry the claim.");
      } else show(request.state === "pending" ? "Waiting for agent approval · no connection opened" : `Request ${request.state} · no connection opened`);
    });
  }
  async function copyMessage() {
    const request = requester?.view();
    if (!alive || busy || paired) return;
    if (request?.state !== "pending" || !request.request) { render(); return; }
    const epoch = generation;
    try {
      await navigator.clipboard.writeText(`Please approve pairing ${request.request}`);
      if (alive && epoch === generation) get("copy-pairing-state").textContent = "Copied. Send this message to the agent; approval is checked automatically while this dialog is visible.";
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
    const to = target.value.trim(); // never inferred from presence
    void act("connect", async current => {
      cancelConnect(); // reserve the auth lock before callbacks; fence cache/import BEFORE auth wait
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
      // Cookies can change outside this control. Never attest from displayed state.
      const before = await auth.status();
      if (!current()) return;
      const revokedParticipant = before.authenticated ? before.participant : undefined;
      // This fresh observation is not an atomic cross-tab status/logout guarantee.
      const status = await auth.forget();
      if (current()) {
        // Revoking a different cookie is not authority to retire this claim.
        const request = requester?.view();
        if (!status.authenticated && !request?.claimUncertain &&
            ["redeemed", "expired", "cancelled"].includes(request?.state) &&
            (request.state !== "redeemed" || (revokedParticipant && revokedParticipant === request.participant)))
          requester.clearExpired({revokedParticipant});
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
  listen(get("check-pairing-request"), "click", () => checkRequest());
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
  listen(document, "visibilitychange", () => {
    if (document.visibilityState !== "visible") cancel(false);
    else schedule();
  });
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
  }
  catch { recovery = "Pairing unavailable. Use the authoritative 127.0.0.1 local HTTP origin, then Check session status."; show("Browser approval unavailable"); render(); }
  return {
    refresh, cancel,
    selectTarget(to) {
      if (!validTargetParticipant(to)) return false;
      cancel();
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
      stopWaiting(); alive = false; generation++; code.value = "";
      for (const [element, name, fn] of listeners) element.removeEventListener(name, fn);
      if (dialog.open) dialog.close();
    },
  };
}
