/** Presentation only: no auth, requests, storage or connection effects. */
export function createSessionView(get) {
  const actionIds = ["request-pairing", "copy-pairing-message", "check-pairing-request",
    "cancel-pairing-request", "connect-session", "choose-agent", "done-connection",
    "check-session-status", "live-mode", "forget-pairing"];
  let primary;
  function render({paired, connected, busy, pendingKind, request, recovery, targetValid}) {
    const dialog = get("connection-dialog"), active = document.activeElement;
    const form = get("pairing-form"), region = get("request-pairing-controls");
    const wasInForm = form.contains(active), wasInRequest = region.contains(active);
    const lostToBusy = busy && (wasInForm || wasInRequest || actionIds.some(id => get(id) === active));
    const pending = request?.state === "pending" && !!request.request;
    const approved = request?.state === "approved" && !!request.request;
    const repair = !paired && (recovery || request?.state === "redeemed" || (request && !request.request));
    const message = request?.request ? `Please approve pairing ${request.request}` : "";
    get("dialog-target").textContent = get("target-participant").value.trim() || "Choose an agent";
    get("pairing-request-locator").textContent = request?.request || "No request yet";
    get("pairing-message").textContent = message;
    form.hidden = paired;
    for (const element of form.elements) element.disabled = busy || paired;
    region.hidden = paired || connected;
    for (const id of actionIds) {
      const button = get(id);
      button.hidden = true;
      button.disabled = busy;
      button.className = id === "forget-pairing" ? "quiet danger" : "secondary";
    }
    function offer(id, main = false) {
      const button = get(id);
      button.hidden = false;
      if (main) { primary = button; button.className = "primary"; }
      return button;
    }
    primary = undefined;
    let guidance;
    if (connected || paired) {
      if (connected) {
        offer("done-connection", true);
        offer("live-mode");
        guidance = "Connected. Messages and replies appear in your conversation.";
      } else if (targetValid) {
        offer("connect-session", true).textContent = busy && pendingKind === "connect" ? "Connecting…" : `Connect to ${get("target-participant").value.trim()}`;
        guidance = "Browser approved. Connect when you are ready; this does not start the agent or guarantee admission.";
      } else {
        offer("choose-agent", true);
        guidance = "Browser approved. Choose the agent you want to connect to.";
      }
      if (paired) offer("forget-pairing").className = "quiet danger";
    } else if (repair) {
      offer("check-session-status", true);
      guidance = recovery || (request?.state === "redeemed" ?
        "This request was already claimed, but this browser has no approval cookie. Check session status. If still unapproved, ask the operator to revoke the orphaned page session before starting again; do not retry the claim." :
        "The request outcome is uncertain. Check session status and ask the operator to repair the request before starting again.");
    } else if (approved) {
      offer("check-pairing-request", true);
      offer("cancel-pairing-request");
      guidance = "Approved by agent — check approval to finish browser approval. This does not connect.";
    } else if (pending) {
      offer("copy-pairing-message", true);
      offer("check-pairing-request");
      offer("cancel-pairing-request");
      guidance = "Send this message to the agent. After they approve, select Check approval. Checks are manual; nothing connects automatically.";
    } else {
      offer("request-pairing", true).textContent = request ? "Start new pairing" : "Start pairing";
      guidance = request?.state === "expired" ? "This pairing request expired. Start a new request and ask the agent to approve it." :
        request?.state === "cancelled" ? "Pairing request cancelled. Start a new one when you are ready." :
        "First, ask the agent to approve this browser. Then you can connect.";
    }
    get("pairing-message-box").hidden = paired || !pending || !!repair;
    get("pairing-request-state").textContent = guidance;
    get("request-expiry").textContent = !paired && (pending || approved) && !repair ? `Expires ${new Date(request.expiresAt * 1000).toLocaleTimeString()}` : "";
    get("request-dismiss-note").hidden = paired || !(pending || approved);
    get("forget-row").hidden = !paired;
    get("advanced-check-session").disabled = busy;
    get("cancel-pairing-request").className = "quiet";
    get("connection-settings").textContent = connected ? "Connection" : "Connect";
    get("connection-settings").setAttribute("aria-expanded", String(dialog.open));
    const unavailable = active?.disabled || active?.hidden || (paired && wasInForm) || ((paired || connected) && wasInRequest);
    if (dialog.open && (lostToBusy || unavailable || (!busy && active === get("pairing-state")))) focusNext(busy);
  }
  function focusNext(busy = false) {
    (busy ? get("pairing-state") : primary || get("close-connection")).focus();
  }
  return {render, focusNext};
}
