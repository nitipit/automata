import { Adapter } from "@devcapsule/adapter";
import { applyBaseStyles } from "./_base.css";
import { appStyle } from "./index.style";
import "./_components/status-badge";
import "./_components/native-dialog";
import type { NativeDialog, DialogRequest } from "./_components/native-dialog";

class AutomataApp extends Adapter {}
AutomataApp.css = appStyle;
AutomataApp.define("automata-app");
applyBaseStyles();

const element = <T extends Element>(selector: string): T => {
  const result = document.querySelector<T>(selector);
  if (!result) throw new Error(`Missing interface element: ${selector}`);
  return result;
};
const transcript = element<HTMLElement>("#transcript");
const generated = element<HTMLElement>("#generated-ui");
// Keep one stable bridge target: moving it preserves live controls and listeners.
// It enters the transcript at the current reply when its content changes.
const generatedObserver = new MutationObserver(() => {
  generated.hidden = ![...generated.childNodes].some(node =>
    node.nodeType === Node.ELEMENT_NODE || Boolean(node.textContent?.trim()));
  if (!generated.hidden) {
    transcript.querySelector(".empty-state")?.remove();
    if (transcript.lastElementChild !== generated) transcript.append(generated);
    transcript.scrollTop = transcript.scrollHeight;
  }
});
generatedObserver.observe(generated, { childList: true, subtree: true, characterData: true });
window.addEventListener("pagehide", () => generatedObserver.disconnect(), { once: true });
const form = element<HTMLFormElement>("#composer");
const prompt = element<HTMLTextAreaElement>("#prompt");
const send = element<HTMLButtonElement>("#send");
const stop = element<HTMLButtonElement>("#stop");
const connection = element<HTMLElement>("#connection-status");
const badge = element<HTMLElement>("status-badge");
const status = element<HTMLElement>("#run-status");
const dialog = element<NativeDialog>("native-rpc-dialog");

type RecordValue = Record<string, any>;
let state: "idle" | "running" | "stopping" | "error" = "error";
let connected = false;
let promptPending = false;
let stream: { body: HTMLElement; blocks: Map<number, string> } | undefined;
let dialogQueue: RecordValue[] = [];
const seenDialogs = new Set<string>();
let dialogActive = false;
let generation = 0;
let socket: WebSocket | undefined;
const pending = new Map<string, "prompt" | "stop">();

function refresh() {
  send.disabled = !connected || state !== "idle" || promptPending;
  prompt.disabled = !connected;
  stop.disabled = !connected || (state !== "running" && !promptPending);
}
function setStatus(next: typeof state, detail?: string) {
  state = next;
  status.textContent = detail || ({ idle: "Ready", running: "Responding…", stopping: "Stopping…", error: "Unavailable" }[next]);
  refresh();
}
function appendMessage(role: string, text: string) {
  transcript.querySelector(".empty-state")?.remove();
  const node = document.createElement("article");
  node.className = `message ${role === "user" ? "user" : "assistant"}`;
  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "Automata";
  const body = document.createElement("div");
  body.textContent = text;
  node.append(label, body);
  transcript.append(node);
  transcript.scrollTop = transcript.scrollHeight;
  return body;
}
function textOf(message: RecordValue): string {
  if (typeof message.content === "string") return message.content;
  if (!Array.isArray(message.content)) return "";
  return message.content.filter((part: RecordValue) => part?.type === "text" && typeof part.text === "string").map((part: RecordValue) => part.text).join("");
}
function showMessage(message: RecordValue) {
  if (message?.role !== "user" && message?.role !== "assistant") return undefined;
  const text = textOf(message);
  if (!text && message.role === "assistant") return undefined;
  return appendMessage(message.role, text);
}
function transmit(message: RecordValue): boolean {
  if (!socket || socket.readyState !== WebSocket.OPEN) return false;
  socket.send(JSON.stringify(message));
  return true;
}
function command(type: "prompt" | "stop", extra: RecordValue = {}) {
  const id = crypto.randomUUID();
  if (!transmit({ type, id, ...extra })) return false;
  pending.set(id, type);
  return true;
}
function addDialog(request: RecordValue) {
  if (!request || typeof request.id !== "string") return;
  if (request.method === "notify") { status.textContent = String(request.message ?? ""); return; }
  if (request.method === "setStatus") { status.textContent = String(request.statusText ?? ""); return; }
  if (request.method === "set_editor_text") { prompt.value = String(request.text ?? ""); return; }
  if (!["confirm", "select", "input", "editor"].includes(request.method)) return;
  if (seenDialogs.has(request.id)) return;
  seenDialogs.add(request.id);
  dialogQueue.push(request);
  void nextDialog();
}
async function nextDialog() {
  if (dialogActive || !connected || !dialogQueue.length) return;
  dialogActive = true;
  const request = dialogQueue[0];
  const epoch = generation;
  const spec: DialogRequest = request.method === "select"
    ? { kind: "select", title: String(request.title ?? "Choose"), options: Array.isArray(request.options) ? request.options.filter((x: unknown) => typeof x === "string") : [] }
    : request.method === "confirm"
      ? { kind: "confirm", title: String(request.title ?? "Confirm"), message: String(request.message ?? "") }
      : request.method === "editor"
        ? { kind: "editor", title: String(request.title ?? "Edit"), value: String(request.prefill ?? "") }
        : { kind: "input", title: String(request.title ?? "Input"), placeholder: String(request.placeholder ?? "") };
  let result: boolean | string | undefined;
  try { result = await dialog.ask(spec); } catch { result = undefined; }
  if (generation === epoch && connected && dialogQueue[0] === request) {
    const response = result === undefined ? { cancelled: true } : typeof result === "boolean" ? { confirmed: result } : { value: result };
    transmit({ type: "extension_ui_response", id: request.id, ...response });
    dialogQueue.shift();
  }
  dialogActive = false;
  void nextDialog();
}
function handleEvent(event: RecordValue) {
  if (!event || typeof event.type !== "string") return;
  switch (event.type) {
    case "agent_start": if (state !== "stopping" && state !== "error") setStatus("running"); break;
    case "agent_settled":
      promptPending = false;
      if (state !== "stopping" && state !== "error") setStatus("idle");
      break;
    case "message_start":
      if (event.message?.role === "assistant") { stream = { body: appendMessage("assistant", ""), blocks: new Map() }; }
      else showMessage(event.message);
      break;
    case "message_update": {
      const update = event.assistantMessageEvent;
      if (!stream || !update) break;
      const index = Number(update.contentIndex ?? 0);
      if (update.type === "text_delta") stream.blocks.set(index, (stream.blocks.get(index) ?? "") + String(update.delta ?? ""));
      if (update.type === "text_end") stream.blocks.set(index, String(update.content ?? ""));
      stream.body.textContent = [...stream.blocks.entries()].sort((a, b) => a[0] - b[0]).map(([, value]) => value).join("");
      transcript.scrollTop = transcript.scrollHeight;
      break;
    }
    case "message_end":
      if (event.message?.role === "assistant") {
        const text = textOf(event.message);
        if (stream) { if (text) stream.body.textContent = text; else stream.body.parentElement?.remove(); }
        else if (text) appendMessage("assistant", text);
        stream = undefined;
      }
      break;
    case "extension_ui_request": addDialog(event); break;
  }
}
function handleFrame(frame: RecordValue) {
  switch (frame.type) {
    case "snapshot":
      // A snapshot refresh must not destroy page-local UI or its event handlers.
      generated.remove();
      transcript.replaceChildren();
      for (const message of Array.isArray(frame.messages) ? frame.messages : []) showMessage(message);
      if (!transcript.children.length && generated.hidden) {
        const empty = document.createElement("p");
        empty.className = "empty-state";
        empty.textContent = "Start a conversation. Replies will appear here as they arrive.";
        transcript.append(empty);
      }
      transcript.append(generated);
      setStatus(["idle", "running", "stopping", "error"].includes(frame.state?.status) ? frame.state.status : "error");
      for (const request of Array.isArray(frame.dialogs) ? frame.dialogs : []) addDialog(request);
      break;
    case "rpc_event": handleEvent(frame.event); break;
    case "dialog_closed": {
      const index = dialogQueue.findIndex((request) => request.id === frame.id);
      if (index >= 0) {
        dialogQueue.splice(index, 1);
        if (index === 0 && dialogActive) dialog.cancel();
      }
      break;
    }
    case "host_status":
      if (["idle", "running", "stopping", "error"].includes(frame.status)) setStatus(frame.status, typeof frame.message === "string" ? frame.message : undefined);
      break;
    case "ack": {
      const kind = pending.get(frame.id);
      pending.delete(frame.id);
      if (kind === "prompt") {
        promptPending = false;
        if (frame.success && frame.data?.disposition === "handled") setStatus("idle");
      }
      if (!frame.success) {
        const recovery = state === "error" ? "error" : kind === "prompt" ? "idle" : kind === "stop" ? "running" : state;
        setStatus(recovery, String(frame.error ?? "Request failed"));
      }
      refresh();
      break;
    }
  }
}
form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = prompt.value.trim();
  if (!message || send.disabled) return;
  if (command("prompt", { message })) { prompt.value = ""; promptPending = true; setStatus("running"); }
});
prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); form.requestSubmit(); }
});
function requestStop() {
  if (!stop.disabled && command("stop")) setStatus("stopping");
}
stop.addEventListener("click", requestStop);
dialog.addEventListener("stop-request", requestStop);

const fragment = new URLSearchParams(location.hash.slice(1));
const token = fragment.get("token");
history.replaceState(null, "", location.pathname + location.search);
if (!token) {
  badge.dataset.state = "error";
  connection.textContent = "Missing access token";
  setStatus("error");
} else {
  const wsOrigin = `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}`;
  socket = new WebSocket(`${wsOrigin}/chat?token=${encodeURIComponent(token)}`);
  socket.addEventListener("open", () => { connected = true; delete badge.dataset.state; connection.textContent = "Connected"; refresh(); });
  socket.addEventListener("message", (event) => { try { handleFrame(JSON.parse(event.data)); } catch { setStatus("error", "Invalid server message"); } });
  socket.addEventListener("close", () => {
    connected = false; generation++; dialogQueue = []; dialog.cancel(); pending.clear(); promptPending = false;
    badge.dataset.state = "error"; connection.textContent = "Disconnected"; setStatus("error", "Connection lost. Reload to start again.");
  });
  socket.addEventListener("error", () => { badge.dataset.state = "error"; connection.textContent = "Connection error"; });
  // Upstream's classic bootstrap has already consumed the fragment and started
  // its bridge. Reuse it; its protocol and lifecycle are not reimplemented here.
  const bridge = (window as Window & { awr?: { status: string; connect(): Promise<void> } }).awr;
  const showBridgeStatus = () => {
    if (!connected) return;
    if (bridge?.status === "connected") { delete badge.dataset.state; connection.textContent = "Connected"; }
    else if (!bridge || bridge.status === "disconnected" || bridge.status === "closed") {
      badge.dataset.state = "error"; connection.textContent = "UI bridge unavailable";
    } else connection.textContent = "Connecting UI…";
  };
  if (bridge) void bridge.connect().then(showBridgeStatus, showBridgeStatus);
  else showBridgeStatus();
  const bridgeWatch = window.setInterval(showBridgeStatus, 1000);
  window.addEventListener("pagehide", () => window.clearInterval(bridgeWatch), { once: true });
}
