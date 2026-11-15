import { Adapter } from "@devcapsule/adapter";
import { applyBaseStyles } from "./_base.css";
import { appStyle, appThemeStyle } from "./index.style";
import { bindTheme } from "./_theme/index";
import { Markdown } from "./_components/markdown";
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
const appHost = element<AutomataApp>("automata-app");
const unbindAppTheme = bindTheme(appHost, theme => { appHost.css = appThemeStyle(theme); });
window.addEventListener("pagehide", unbindAppTheme, { once: true });
const transcript = element<HTMLElement>("#transcript");
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
type MessageView = { node: HTMLElement; body: HTMLElement; ui: HTMLElement; anchor: Comment };
let stream: { view: MessageView; blocks: Map<number, string>; message: RecordValue } | undefined;
const owners = new Map<string, MessageView | null>();
const liveOwners = new Set<string>();
const liveBlocks = new Map<string, HTMLElement>();
const finishedContexts = new Set<string>();
const ownerWaiters = new Map<string, Set<() => void>>();
let ownerWaiterCount = 0;
let dialogQueue: RecordValue[] = [];
const seenDialogs = new Set<string>();
let dialogActive = false;
let generation = 0;
let socket: WebSocket | undefined;
const pending = new Map<string, "prompt" | "stop">();

function setUIAvailable(available: boolean) {
  for (const block of liveBlocks.values()) block.inert = !available;
}
function refresh() {
  send.disabled = !connected || state !== "idle" || promptPending;
  prompt.disabled = !connected;
  stop.disabled = !connected || (state !== "running" && !promptPending);
}
function setStatus(next: typeof state, detail?: string) {
  state = next;
  if (next === "stopping" || next === "error") notifyOwnerWaiters();
  status.textContent = detail || ({ idle: "Ready", running: "Responding…", stopping: "Stopping…", error: "Unavailable" }[next]);
  refresh();
}
function createMessage(role: string, text: string): MessageView {
  const node = document.createElement("article");
  node.className = `message ${role === "user" ? "user" : "assistant"}`;
  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "Automata";
  const body = role === "assistant" ? new Markdown() : document.createElement("div");
  body.className = "message-body";
  if (body instanceof Markdown) body.source = text;
  else body.textContent = text;
  const ui = document.createElement("div");
  ui.className = "message-ui";
  node.append(label, body, ui);
  const anchor = document.createComment("message");
  transcript.append(anchor);
  return { node, body, ui, anchor };
}
function reveal(view: MessageView) {
  if (!view.node.isConnected) {
    transcript.querySelector(".empty-state")?.remove();
    if (view.anchor.isConnected) view.anchor.replaceWith(view.node);
    else transcript.append(view.node);
  }
  transcript.scrollTop = transcript.scrollHeight;
}
function notifyOwnerWaiters(id?: string) {
  if (id !== undefined) ownerWaiters.get(id)?.forEach(check => check());
  else for (const waiters of ownerWaiters.values()) waiters.forEach(check => check());
}
function registerOwners(message: RecordValue, view: MessageView, live = false) {
  if (!Array.isArray(message?.content)) return;
  for (const part of message.content) {
    if (part?.type !== "toolCall" || typeof part.id !== "string" || !part.id) continue;
    if (live) liveOwners.add(part.id);
    const prior = owners.get(part.id);
    // Ambiguous IDs must never target a different message.
    if (prior && prior !== view) {
      owners.set(part.id, null);
      liveBlocks.get(part.id)?.remove();
    }
    else if (prior !== null) owners.set(part.id, view);
    notifyOwnerWaiters(part.id);
  }
}
function waitForOwner(toolCallId: string, timeoutMs: number): Promise<void> {
  if (!Number.isFinite(timeoutMs) || timeoutMs < 1 || timeoutMs > 1000) return Promise.reject(new Error("Invalid owner readiness deadline"));
  if (ownerWaiterCount >= 32) return Promise.reject(new Error("Too many owner readiness waits"));
  return new Promise((resolve, reject) => {
    let settled = false;
    const checks = ownerWaiters.get(toolCallId) ?? new Set<() => void>();
    ownerWaiters.set(toolCallId, checks);
    ownerWaiterCount++;
    const cleanup = () => {
      if (settled) return;
      settled = true;
      clearTimeout(deadline);
      clearInterval(watch);
      checks.delete(check);
      if (!checks.size) ownerWaiters.delete(toolCallId);
      ownerWaiterCount--;
    };
    const check = () => {
      if (!connected || state === "stopping" || state === "error" ||
          (window as Window & { awr?: { status: string } }).awr?.status !== "connected") {
        cleanup(); reject(new Error("Browser connection unavailable"));
      } else if (owners.get(toolCallId) === null) {
        cleanup(); reject(new Error("Assistant tool-call owner is ambiguous"));
      } else if (owners.has(toolCallId) && liveOwners.has(toolCallId)) {
        cleanup(); resolve();
      }
    };
    const deadline = window.setTimeout(() => { cleanup(); reject(new Error("Assistant tool-call owner not available before deadline")); }, timeoutMs);
    const watch = window.setInterval(check, 25);
    checks.add(check);
    check();
  });
}
function context(toolCallId: string) {
  if (typeof toolCallId !== "string" || !toolCallId) throw new Error("A tool call ID is required");
  return {
    blockId: toolCallId,
    toolCallId,
    get materialized() { return liveBlocks.has(toolCallId); },
    ready(timeoutMs: number) { return waitForOwner(toolCallId, timeoutMs); },
    finish() { finishedContexts.add(toolCallId); },
    get root() {
      const owner = owners.get(toolCallId);
      if (!owner) throw new Error("Assistant tool-call owner is unavailable or ambiguous");
      let block = liveBlocks.get(toolCallId);
      if (!block) {
        if (finishedContexts.has(toolCallId)) throw new Error("Initial UI root must be created before execution finishes");
        block = document.createElement("div");
        block.className = "generated-content";
        block.setAttribute("role", "region");
        block.setAttribute("aria-label", "Interactive content");
        block.dataset.blockId = toolCallId;
        block.inert = !connected || (window as Window & { awr?: { status: string } }).awr?.status !== "connected";
        liveBlocks.set(toolCallId, block);
      }
      owner.ui.querySelectorAll<HTMLElement>(".inactive-ui").forEach(node => {
        if (node.dataset.blockId === toolCallId) node.remove();
      });
      if (block.parentElement !== owner.ui) owner.ui.append(block);
      reveal(owner);
      return block;
    },
  };
}
(window as Window & { automataUI?: { context: typeof context } }).automataUI = { context };
function inactiveBlock(toolCallId: string, blockId: string) {
  if (toolCallId !== blockId) return;
  const owner = owners.get(toolCallId);
  if (!owner) {
    const notice = document.createElement("p");
    notice.className = "inactive-ui";
    notice.textContent = "Inactive interactive content has no available assistant owner in this history.";
    transcript.append(notice);
    return;
  }
  const live = liveBlocks.get(toolCallId);
  if (owner.ui.querySelectorAll<HTMLElement>(".inactive-ui").length &&
      [...owner.ui.querySelectorAll<HTMLElement>(".inactive-ui")].some(node => node.dataset.blockId === blockId)) return;
  if (live) owner.ui.append(live);
  else {
    const placeholder = document.createElement("div");
    placeholder.className = "inactive-ui";
    placeholder.dataset.blockId = blockId;
    placeholder.textContent = "Interactive content from this reply is inactive after reload.";
    owner.ui.append(placeholder);
  }
  reveal(owner);
}
function textOf(message: RecordValue): string {
  if (typeof message.content === "string") return message.content;
  if (!Array.isArray(message.content)) return "";
  return message.content.filter((part: RecordValue) => part?.type === "text" && typeof part.text === "string").map((part: RecordValue) => part.text).join("");
}
function showMessage(message: RecordValue) {
  if (message?.role !== "user" && message?.role !== "assistant") return undefined;
  const text = textOf(message);
  const view = createMessage(message.role, text);
  if (message.role === "assistant") registerOwners(message, view);
  if (text || message.role === "user") reveal(view);
  return view;
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
      if (event.message?.role === "assistant") {
        const view = createMessage("assistant", "");
        registerOwners(event.message, view, true);
        stream = { view, blocks: new Map(), message: event.message };
      }
      else showMessage(event.message);
      break;
    case "message_update": {
      const update = event.assistantMessageEvent;
      if (!stream || !update) break;
      if (update.partial?.role === "assistant") {
        stream.message = update.partial;
        registerOwners(update.partial, stream.view, true);
      }
      const index = Number(update.contentIndex ?? 0);
      if (update.type === "text_delta") stream.blocks.set(index, (stream.blocks.get(index) ?? "") + String(update.delta ?? ""));
      if (update.type === "text_end") stream.blocks.set(index, String(update.content ?? ""));
      const text = [...stream.blocks.entries()].sort((a, b) => a[0] - b[0]).map(([, value]) => value).join("");
      (stream.view.body as Markdown).source = text;
      if (text) reveal(stream.view);
      break;
    }
    case "message_end":
      if (event.message?.role === "assistant") {
        const text = textOf(event.message);
        if (stream) {
          registerOwners(event.message, stream.view, true);
          (stream.view.body as Markdown).source = text;
          if (text || stream.view.ui.childNodes.length) reveal(stream.view);
        } else {
          const view = showMessage(event.message);
          if (view) registerOwners(event.message, view, true);
        }
        stream = undefined;
      }
      break;
    case "extension_ui_request": addDialog(event); break;
  }
}
function handleFrame(frame: RecordValue) {
  switch (frame.type) {
    case "snapshot":
      // Rebuild native text/ownership, retaining page-local block nodes by ID.
      const focused = document.activeElement instanceof HTMLElement &&
        ([...liveBlocks.values()].some(block => block.contains(document.activeElement)) ||
          !!stream?.view.body.contains(document.activeElement))
        ? document.activeElement : null;
      transcript.replaceChildren();
      owners.clear();
      const messages = Array.isArray(frame.messages) ? frame.messages : [];
      for (const message of messages) showMessage(message);
      if (stream) {
        // Keep an unfinished live reply; snapshot history contains completed messages.
        transcript.append(stream.view.anchor);
        registerOwners(stream.message, stream.view, true);
        if (stream.view.body.textContent || stream.view.ui.childNodes.length) reveal(stream.view);
      }
      for (const message of messages) {
        const ui = message?.details?.ui;
        if (message?.role === "toolResult" && typeof message.toolCallId === "string" &&
            ui?.toolCallId === message.toolCallId && typeof ui.blockId === "string") {
          inactiveBlock(message.toolCallId, ui.blockId);
        }
      }
      // Live nodes may precede their tool result in a snapshot.
      for (const [id, block] of liveBlocks) {
        const owner = owners.get(id);
        if (owner) { owner.ui.append(block); reveal(owner); }
      }
      if (focused?.isConnected) focused.focus({ preventScroll: true });
      if (!transcript.children.length) {
        const empty = document.createElement("p");
        empty.className = "empty-state";
        empty.textContent = "Start a conversation. Replies will appear here as they arrive.";
        transcript.append(empty);
      }
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
    notifyOwnerWaiters();
    setUIAvailable(false);
    badge.dataset.state = "error"; connection.textContent = "Disconnected"; setStatus("error", "Connection lost. Reload to start again.");
  });
  socket.addEventListener("error", () => { badge.dataset.state = "error"; connection.textContent = "Connection error"; });
  // Upstream's classic bootstrap has already consumed the fragment and started
  // its bridge. Reuse it; its protocol and lifecycle are not reimplemented here.
  const bridge = (window as Window & { awr?: { status: string; connect(): Promise<void> } }).awr;
  const showBridgeStatus = () => {
    if (!connected) return;
    setUIAvailable(bridge?.status === "connected");
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
