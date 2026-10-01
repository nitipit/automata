import { registerPlayspace, ContractError, text, formContracts } from "./lib/playspace.js";
import { createCacheRecovery } from "./lib/recovery.js";
import { validateStarterSnapshot } from "./lib/state.js";
import { bindChatTransport } from "./lib/transport.js";
import { sampleForm, sampleReply } from "./sample.js";

registerPlayspace();
const chat = document.querySelector("ps-chat");
const connection = document.querySelector("#connection");
const recoveryState = document.querySelector("#recovery");
let initializing = true;
let disposed = false;
let liveFactory;
const transport = bindChatTransport(chat, {
  sampleReply, createLiveClient: options => liveFactory(options),
  onState: value => { connection.textContent = value; },
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
  await recovery.flush();
  const value = await recovery.load();
  if (!value || disposed) return false;
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
const handlers = new Map([
  ["sample-mode", () => { transport.sample(); void save(); }],
  ["live-mode", () => { transport.disconnected(); void save(); }],
  ["sample-form", () => chat.addMessage("agent", sampleForm())],
  ["save", () => { void save(); }], ["restore", () => { void restore(); }],
]);
for (const [id, handler] of handlers) document.getElementById(id).addEventListener("click", handler);

/** Authorized provisioning only; credentials/capabilities stay out of snapshots. */
async function connect(credentials, to, { createClient, moduleURL = "./router/pi-client.js" } = {}) {
  if (disposed) return false;
  try {
    liveFactory = createClient ?? (await import(moduleURL)).createMessageRouterChatClient;
    const connected = await transport.connect(credentials, to);
    void save();
    return connected;
  } catch {
    transport.disconnected();
    connection.textContent = "LIVE DISCONNECTED · router assets unavailable; no request sent";
    return false;
  }
}
function dispose() {
  if (disposed) return;
  disposed = true;
  chat.removeEventListener("chat-change", onChange);
  for (const [id, handler] of handlers) document.getElementById(id).removeEventListener("click", handler);
  transport.dispose();
  chat.dispose();
  recovery.dispose();
  globalThis.removeEventListener("pagehide", onPageHide);
}
function onPageHide(event) { if (!event.persisted) dispose(); }
globalThis.addEventListener("pagehide", onPageHide);
globalThis.playspaceChat = { chat, contracts: formContracts, snapshot, save, restore, connect, dispose };
try {
  transport.sample();
  if (!await restore()) chat.addMessage("agent", text("Sample agent mode is local, not live. Try ‘form’ or ‘json’. This is v2; old v1 cache is preserved but not imported."));
} catch {
  document.querySelector("#startup-error").textContent = "Starter initialization failed · no remote request sent. Check public modules/component contracts.";
} finally { initializing = false; }
