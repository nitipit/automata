import { registerPlayspace, ContractError, text, formContracts } from "./lib/playspace.js";
import { createCacheRecovery } from "./lib/recovery.js";
import { validateStarterSnapshot } from "./lib/state.js";
import { bindChatTransport } from "./lib/transport.js";
import { sampleForm, sampleReply } from "./sample.js";
import { createMessageRouterChatClient } from "./router/pi-client.js";
import { bindSessionControls } from "./session-controls.js";

registerPlayspace();
const chat = document.querySelector("ps-chat");
const recoveryState = document.querySelector("#recovery");
let initializing = true;
let disposed = false;
let connectionIntent = 0;
let liveFactory = createMessageRouterChatClient;
let sessionControls;
let openingConnection = false;
let pendingProvisionIntent;
function showConnection(value) {
  openingConnection = value === "LIVE · connecting to selected participant";
  sessionControls?.setConnection(value);
  if (!initializing && value.startsWith("LIVE DISCONNECTED")) void sessionControls?.refresh(false);
}
const transport = bindChatTransport(chat, {
  sampleReply, createLiveClient: options => liveFactory(options),
  onState: showConnection,
});
const recovery = createCacheRecovery({
  key: new URL("./__playspace_chat_snapshot_v2__", location.href).href,
  onState: value => { recoveryState.textContent = value; },
});
const snapshot = () => validateStarterSnapshot({ version: 2, mode: transport.getMode(), chat: chat.snapshot() });
function save() {
  if (disposed) return Promise.resolve(false);
  try { return recovery.save(snapshot()); }
  catch (error) {
    recoveryState.textContent = error instanceof ContractError ? `Not saved · ${error.message}` : "Not saved · snapshot contract failed; current draft retained";
    return Promise.resolve(false);
  }
}
function onChange() { if (!initializing) void save(); }
chat.addEventListener("chat-change", onChange);
async function restore() {
  sessionControls?.cancel(); // BEFORE flush/load: delayed auth status cannot reconnect
  const intent = ++connectionIntent;
  if (transport.getMode() === "sample") transport.sample();
  else transport.disconnected(); // also retire a connection already opening
  await recovery.flush();
  if (disposed || intent !== connectionIntent) return false;
  const value = await recovery.load();
  if (!value || disposed || intent !== connectionIntent) return false;
  const previous = initializing;
  initializing = true;
  try {
    const candidate = validateStarterSnapshot(value);
    transport.disconnected(); // retire capabilities before replacing any instances
    if (!chat.restore(candidate.chat)) {
      recoveryState.textContent = "Recovery reconstruction failed · last-good display retained; see component feedback";
      return false;
    }
    if (candidate.mode === "sample") transport.sample();
    recoveryState.textContent = "Recovered v2 display/drafts · no events/sends replayed · v1 preserved/not imported";
    return true;
  } catch (error) {
    recoveryState.textContent = error instanceof ContractError ? `Recovery rejected · last-good draft retained\n${error.message}` : "Recovery failed · cache not erased";
    return false;
  } finally { initializing = previous; }
}
sessionControls = bindSessionControls({
  async connect(session, to) {
    connectionIntent++;
    liveFactory = createMessageRouterChatClient;
    const connected = await transport.connect(session, to, { session: true });
    void save();
    return connected;
  },
  disconnect: () => { connectionIntent++; transport.disconnected(); void save(); },
  cancelConnect() {
    connectionIntent++; // modal Cancel also supersedes an older pending cache Restore
    if (!openingConnection && pendingProvisionIntent === undefined) return;
    pendingProvisionIntent = undefined;
    transport.disconnected();
    void save();
  },
});
function demo() {
  connectionIntent++;
  sessionControls.cancel();
  transport.sample();
  void save();
}
const handlers = new Map([
  ["sample-mode", demo],
  ["live-mode", () => { connectionIntent++; sessionControls.cancel(); transport.disconnected(); void save(); }],
  ["sample-form", () => { demo(); chat.addMessage("agent", sampleForm()); }],
  ["save", () => { void save(); }], ["restore", () => { void restore(); }],
]);
for (const [id, handler] of handlers) document.getElementById(id).addEventListener("click", handler);

/** Authorized provisioning only; credentials/capabilities stay out of snapshots. */
async function connect(credentials, to, { createClient, moduleURL = "./router/pi-client.js" } = {}) {
  if (disposed || !sessionControls.selectTarget(to)) return false;
  sessionControls.cancel(); // explicit memory provisioning supersedes paired Connect
  const intent = ++connectionIntent;
  transport.disconnected();
  pendingProvisionIntent = intent;
  try {
    const factory = createClient ?? (await import(moduleURL)).createMessageRouterChatClient;
    if (disposed || intent !== connectionIntent) return false;
    pendingProvisionIntent = undefined;
    liveFactory = factory;
    const connected = await transport.connect(credentials, to);
    void save();
    return connected;
  } catch {
    if (disposed || intent !== connectionIntent) return false;
    transport.disconnected();
    showConnection("LIVE DISCONNECTED · router assets unavailable; no request sent");
    return false;
  } finally {
    if (pendingProvisionIntent === intent) pendingProvisionIntent = undefined;
  }
}
function dispose() {
  if (disposed) return;
  disposed = true;
  connectionIntent++;
  chat.removeEventListener("chat-change", onChange);
  for (const [id, handler] of handlers) document.getElementById(id).removeEventListener("click", handler);
  sessionControls.dispose();
  transport.dispose();
  chat.dispose();
  recovery.dispose();
  globalThis.removeEventListener("pagehide", onPageHide);
}
function onPageHide(event) { if (!event.persisted) dispose(); }
globalThis.addEventListener("pagehide", onPageHide);
globalThis.playspaceChat = { chat, contracts: formContracts, snapshot, save, restore, connect, dispose };
try {
  transport.disconnected();
  if (!await restore()) chat.addMessage("agent", text("What would you like to explore? Connect your agent to begin, or try the local Demo in Tools."));
} catch {
  document.querySelector("#startup-error").textContent = "Starter initialization failed · no remote request sent. Check public modules/component contracts.";
} finally {
  initializing = false;
  // Startup Restore fences connection intents; check auth only after that boundary.
  void sessionControls.refresh(false);
}
