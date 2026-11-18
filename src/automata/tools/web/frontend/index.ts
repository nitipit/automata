import sendIcon from "./_assets/gnomicon/paper-plane.svg";
import stopIcon from "./_assets/gnomicon/media-playback-stop.svg";
import editIcon from "./_assets/gnomicon/document-edit-symbolic.svg";
import { Adapter } from "@devcapsule/adapter";
import { applyBaseStyles } from "./_base.css";
import { createBrowserTrustRenewal } from "./browser-trust-renewal";
import { appStyle, appThemeStyle } from "./index.style";
import { bindTheme } from "./_theme/index";
import { Markdown } from "./_components/markdown";
import "./_components/native-dialog";
import type { NativeDialog, DialogRequest } from "./_components/native-dialog";
import { bridgeNeedsReload, bridgeWindow, closeBridge, prepareBridge, wsOrigin } from "./paired-bridge";
import { carryDrafts, clearAdmission, readAdmission, savedSessionURL, sessionId, sessionPath, takeDrafts } from "./session-navigation";

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
const modelSelect = element<HTMLSelectElement>("#model");
const thinkingSelect = element<HTMLSelectElement>("#thinking-level");
const controlsStatus = element<HTMLElement>("#runtime-controls-status");

const connection = element<HTMLElement>("#connection-status");
const sessionTitle = element<HTMLElement>("#session-name");
const titleRow = element<HTMLElement>(".session-title");
const rename = element<HTMLButtonElement>("#rename");
const renameForm = element<HTMLFormElement>("#rename-form");
const nameInput = element<HTMLInputElement>("#session-name-input");
const renameError = element<HTMLElement>("#rename-error");
const sessions = element<HTMLButtonElement>("#sessions");
const newChat = element<HTMLButtonElement>("#new-chat");
const newChatForm = element<HTMLFormElement>("#new-chat-form");
const picker = element<HTMLDialogElement>("#sessions-picker");
const pickerStatus = element<HTMLElement>("#sessions-status");
const pickerList = element<HTMLUListElement>("#sessions-list");
const pickerDirectory = element<HTMLElement>(".sessions-directory");
const pickerPlaceholder = element<HTMLElement>("#sessions-placeholder");
const pickerDetail = element<HTMLElement>("#sessions-detail");
const pickerTarget = element<HTMLElement>("#sessions-target");
const pickerPreviewLabel = element<HTMLElement>("#sessions-preview-label");
const pickerPreviewStatus = element<HTMLElement>("#sessions-preview-status");
const pickerContent = element<HTMLElement>("#sessions-content");
const pickerOpening = element<HTMLElement>("#sessions-opening");
const pickerBack = element<HTMLButtonElement>("#sessions-back");
const pickerCompact = matchMedia("(max-width: 680px)");
const pickerReload = element<HTMLButtonElement>("#sessions-reload");
const pickerPrev = element<HTMLButtonElement>("#sessions-prev");
const pickerNext = element<HTMLButtonElement>("#sessions-next");
const pickerClose = element<HTMLButtonElement>("#sessions-close");
const pickerOpen = element<HTMLButtonElement>("#sessions-open");
const drafts = takeDrafts();
if (sessionId) {
  prompt.value = drafts.get(sessionId) ?? "";
  drafts.delete(sessionId);
}
const admission = readAdmission();
let pairTicket: string | undefined;
let sessionName = "";
let firstUserPreview = "";
let firstUserSeen = false;
let renamePending = false;
let renameInitial = "";
let renameAttempt: string | undefined;
const connectButton = element<HTMLButtonElement>("#connect");
const connectionDetail = element<HTMLElement>("#connection-detail");
// Bundled, reviewed Gnomicon SVG only; never server/user markup.
rename.innerHTML = editIcon;
rename.querySelector("svg")?.setAttribute("aria-hidden", "true");
const status = element<HTMLElement>("#run-status");
const dialog = element<NativeDialog>("native-rpc-dialog");

type RecordValue = Record<string, any>;
const statuses = ["idle", "running", "stopping", "switching", "error"] as const;
let state: typeof statuses[number] = "error";
let pickerBusy = false;
let switching = false;
let previousOffset: number | undefined;
let nextOffset: number | undefined;
let pickerReceipt: string | undefined;
let selectedSession: { row: RecordValue; button: HTMLButtonElement } | undefined;
let previewRequest: string | undefined;
let previewReady = false;
let directoryScroll = 0;
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
type ControlsCommand = "set_model" | "set_thinking_level";
type Command = "prompt" | "stop" | "rename" | "list_sessions" | "preview_session" | ControlsCommand;
type ModelChoice = { provider: string; id: string; name: string };
let models: ModelChoice[] = [];
let selectedModel: ModelChoice | undefined;
let levels: string[] = [];
let selectedLevel: string | undefined;
let controlsSignature: string | undefined;
let controlsError = "";
let controlsNotice = "";
let controlsPending = false;
const pending = new Map<string, Command>();
let runView: MessageView | undefined;
let activity: HTMLElement | undefined;
let placeholder: MessageView | undefined;
// The native user echo reconciles this turn in place, before its reply.
let submittedUser: MessageView | undefined;
function discardSubmittedUser() {
  submittedUser?.node.remove(); submittedUser = undefined;
}
let runActive = false;
let runFailure = false;

function updateName(name: unknown) {
  sessionName = typeof name === "string" ? name : "";
  const title = sessionName.trim() ? sessionName : firstUserPreview || "Untitled session";
  sessionTitle.textContent = title;
  sessionTitle.title = title;
  document.title = title;
}
function observeUser(message: RecordValue) {
  if (firstUserSeen || message?.role !== "user") return;
  firstUserSeen = true;
  const points = Array.from(textOf(message).replace(/\s+/gu, " ").trim());
  firstUserPreview = points.slice(0, 64).join("") + (points.length > 64 ? "…" : "");
  updateName(sessionName);
}
function clearActivity() {
  activity?.remove(); activity = undefined;
  if (placeholder) { placeholder.node.remove(); placeholder.anchor.remove(); placeholder = undefined; }
  if (runView && !runView.body.textContent && !runView.ui.childNodes.length && !runView.node.querySelector(".reply-outcome")) runView.node.remove();
}
function replyOutcome(view: MessageView, text: string) {
  let note = view.node.querySelector<HTMLElement>(".reply-outcome");
  if (!note) { note = document.createElement("p"); note.className = "reply-outcome"; note.setAttribute("role", "status"); view.node.append(note); }
  note.textContent = text; reveal(view);
}
function messageOutcome(message: RecordValue, view: MessageView) {
  if (message.stopReason === "aborted" || message.stopReason === "error") {
    replyOutcome(view, message.stopReason === "aborted" ? "Reply interrupted." : `Reply failed: ${message.errorMessage || "Please try again."}`);
    return true;
  }
  return false;
}
function renderActivity() {
  if (!runActive || (state !== "running" && state !== "stopping")) return;
  if (!runView) placeholder ??= createMessage("assistant", "");
  const view = runView || placeholder!;
  activity ??= document.createElement("p");
  activity.className = "reply-activity"; activity.setAttribute("role", "status");
  activity.textContent = state === "stopping" ? "Stopping…" : "Responding…";
  view.node.append(activity); reveal(view);
}
function finishRun(detail?: string) {
  if (runActive && detail && !runFailure) {
    if (runView) replyOutcome(runView, detail);
    else status.textContent = detail;
  }
  discardSubmittedUser();
  clearActivity(); runActive = false; runView = undefined;
}

function setUIAvailable(available: boolean) {
  for (const block of liveBlocks.values()) block.inert = !available;
}
function canSend() { return connected && state === "idle" && !promptPending && !controlsPending && !switching; }
function readModel(value: unknown): value is ModelChoice {
  if (!value || typeof value !== "object") return false;
  const model = value as Partial<ModelChoice>;
  return typeof model.provider === "string" && !!model.provider && typeof model.id === "string" && !!model.id && typeof model.name === "string";
}
const modelKey = (model: ModelChoice) => JSON.stringify([model.provider, model.id]);
const modelLabel = (model: ModelChoice) => `${model.name || model.id} · ${model.provider}`;
const levelLabel = (level: string) => level === "xhigh" ? "Extra high" : level.charAt(0).toUpperCase() + level.slice(1);
function controlOptions(select: HTMLSelectElement, choices: [string, string][], selected: string | undefined, label: string) {
  const options = choices.map(([value, text]) => new Option(text, value));
  if (!selected || !choices.some(([value]) => value === selected)) {
    const current = new Option(label, selected ?? "");
    current.disabled = true;
    options.unshift(current);
  }
  select.replaceChildren(...options);
  select.value = selected ?? "";
}
function applyControls(value: RecordValue | null = {}) {
  value ??= {};
  const found = Array.isArray(value.modelChoices) && Array.isArray(value.thinkingLevels);
  const choices: ModelChoice[] = found ? value.modelChoices.filter(readModel) : [];
  const current = found && readModel(value.model) ? value.model : undefined;
  const allowed = found ? value.thinkingLevels.filter((item: unknown): item is string => typeof item === "string" && !!item) : [];
  const level = found && typeof value.thinkingLevel === "string" ? value.thinkingLevel : undefined;
  const error = !found ? "Message settings unavailable." : typeof value.controlsError === "string" ? value.controlsError : "";
  const signature = JSON.stringify([choices, current, allowed, level, error]);
  if (signature === controlsSignature) return;
  controlsSignature = signature;
  models = choices; selectedModel = current; levels = allowed; selectedLevel = level; controlsError = error;
  controlOptions(modelSelect, models.map(model => [modelKey(model), modelLabel(model)]),
    current && modelKey(current), current ? `Current: ${modelLabel(current)}` : "Unavailable");
  controlOptions(thinkingSelect, levels.map(item => [item, levelLabel(item)]),
    level, level ? `Current: ${levelLabel(level)}` : "Unavailable");
}
function refreshControls() {
  const inactive = !canSend() || dialogActive;
  modelSelect.disabled = inactive || !!controlsError || !models.length;
  thinkingSelect.disabled = inactive || !!controlsError || !levels.length;
  const note = !connected ? "" : controlsNotice || controlsError || (!models.length ? "No pinned models configured." : !levels.length ? "Thinking levels unavailable." : "");
  if (controlsStatus.textContent !== note) controlsStatus.textContent = note;
}
function changeControls(type: ControlsCommand, data: RecordValue) {
  if (!canSend() || dialogActive || controlsError) return;
  controlsPending = !!command(type, data);
  controlsNotice = controlsPending ? "Applying message settings…" : "Connection unavailable. No change was confirmed.";
  refresh();
}
modelSelect.addEventListener("change", () => {
  const candidate = models.find(model => modelKey(model) === modelSelect.value);
  modelSelect.value = selectedModel ? modelKey(selectedModel) : "";
  if (candidate && modelKey(candidate) !== modelSelect.value) {
    changeControls("set_model", { provider: candidate.provider, modelId: candidate.id });
  }
});
thinkingSelect.addEventListener("change", () => {
  const level = thinkingSelect.value;
  thinkingSelect.value = selectedLevel ?? "";
  if (level !== selectedLevel && levels.includes(level)) changeControls("set_thinking_level", { level });
});
function canStop() { return connected && !switching && state !== "stopping" && (state === "running" || promptPending); }
function renderComposerAction() {
  const mode = state === "stopping" ? "stopping" : canStop() ? "stop" : "send";
  if (send.dataset.action !== mode) {
    send.dataset.action = mode;
    send.innerHTML = mode === "send" ? sendIcon : stopIcon;
    send.firstElementChild?.setAttribute("aria-hidden", "true");
    send.title = mode === "send" ? "Send message" : mode === "stop" ? "Stop response" : "Stopping…";
    send.setAttribute("aria-label", send.title);
  }
  send.disabled = mode === "stopping" || (mode === "send" && (!canSend() || !prompt.value.trim()));
}
function refresh() {
  renderComposerAction();
  refreshControls();
  prompt.disabled = !connected || switching || state === "switching";
  sessions.disabled = !canSend() || renamePending || dialogActive;
  newChat.disabled = !connected || !pairTicket || switching || state === "error";
  rename.disabled = !connected || state === "switching" || state === "error" || switching;
  nameInput.readOnly = renamePending;
  pickerClose.disabled = pickerBack.disabled = switching;
  pickerOpen.disabled = sessions.disabled || pickerBusy || !pickerReceipt || !previewReady || !selectedSession || !!selectedSession.row.current;
  pickerPrev.disabled = pickerNext.disabled = pickerReload.disabled = pickerBusy || switching;
}
function setStatus(next: typeof state, detail?: string) {
  const previous = state;
  const hadReply = runActive && !!runView;
  state = next;
  if (next === "stopping" || next === "switching" || next === "error") notifyOwnerWaiters();
  if (next === "running" && !runActive) {
    runActive = true; runView = undefined; runFailure = false; status.textContent = "";
  }
  if (next === "idle" || next === "error") finishRun(next === "error" ? detail || "Reply unavailable. Check the connection." : previous === "stopping" ? "Reply interrupted." : undefined);
  else renderActivity();
  if (detail && next === "error" && !hadReply) status.textContent = detail;
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
      if (!connected || state === "stopping" || state === "switching" || state === "error" ||
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
  const epoch = generation;
  return {
    blockId: toolCallId,
    toolCallId,
    get materialized() { return epoch === generation && liveBlocks.has(toolCallId); },
    ready(timeoutMs: number) {
      return epoch === generation ? waitForOwner(toolCallId, timeoutMs) : Promise.reject(new Error("Session changed"));
    },
    finish() { if (epoch === generation) finishedContexts.add(toolCallId); },
    get root() {
      if (epoch !== generation) throw new Error("Session changed");
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
    placeholder.textContent = "Interactive content from this reply is inactive after reload or a session switch.";
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
  observeUser(message);
  const text = textOf(message);
  const view = createMessage(message.role, text);
  if (message.role === "assistant") registerOwners(message, view);
  if (text || message.role === "user") reveal(view);
  if (message.role === "assistant") messageOutcome(message, view);
  return view;
}
function transmit(message: RecordValue): boolean {
  if (!connected || !socket || socket.readyState !== WebSocket.OPEN) return false;
  socket.send(JSON.stringify(message));
  return true;
}
function command(type: Command, extra: RecordValue = {}) {
  const id = crypto.randomUUID();
  if (!transmit({ type, id, sessionId, ...extra })) return undefined;
  pending.set(id, type);
  return id;
}
function resetPickerChoice() {
  selectedSession?.button.setAttribute("aria-pressed", "false");
  selectedSession = previewRequest = undefined;
  previewReady = false;
  delete picker.dataset.detail;
  pickerDetail.hidden = pickerContent.hidden = pickerOpening.hidden = true;
  pickerPlaceholder.hidden = false;
  pickerTarget.textContent = pickerPreviewStatus.textContent = "";
  delete pickerPreviewStatus.dataset.ready;
  for (const field of ["modified", "model", "tokens", "user", "assistant"]) {
    element(`#sessions-${field}`).textContent = "";
  }
}
function loadSessions(offset = 0, moveFocus = false) {
  pickerReceipt = undefined;
  resetPickerChoice();
  pickerList.replaceChildren();
  directoryScroll = 0;
  pickerPrev.hidden = pickerNext.hidden = pickerReload.hidden = true;
  if (moveFocus) pickerClose.focus();
  pickerStatus.textContent = "Loading project sessions…";
  pickerBusy = !!command("list_sessions", { offset });
  if (!pickerBusy) pickerStatus.textContent = "Connection unavailable.";
  refresh();
}
function formatModified(value: unknown, detail = false): string {
  const date = typeof value === "string" ? new Date(value) : null;
  if (!date || Number.isNaN(+date)) return "";
  const today = new Date();
  return date.toLocaleString(undefined, detail
    ? { dateStyle: "medium", timeStyle: "short" }
    : date.toDateString() === today.toDateString() ? { timeStyle: "short" }
    : { month: "short", day: "numeric", ...(date.getFullYear() === today.getFullYear() ? {} : { year: "numeric" }) });
}
function selectSession(row: RecordValue, button: HTMLButtonElement) {
  if (switching || pickerBusy) return;
  if (selectedSession?.button === button && picker.dataset.detail) return;
  const scroll = pickerDirectory.scrollTop;
  resetPickerChoice();
  directoryScroll = scroll;
  selectedSession = { row, button };
  button.setAttribute("aria-pressed", "true");
  pickerTarget.textContent = row.label;
  pickerPreviewLabel.textContent = row.current ? "CURRENT SESSION" : "SESSION PREVIEW";
  pickerPlaceholder.hidden = true;
  pickerDetail.hidden = false;
  pickerOpening.hidden = !!row.current;
  picker.dataset.detail = "true";
  if (pickerCompact.matches) pickerTarget.focus({ preventScroll: true });
  element("#sessions-preview-scroll").scrollTop = 0;
  element(".sessions-preview").scrollTop = 0;
  previewRequest = pickerReceipt && row.modified ? command("preview_session", {
    sessionId: row.id, fromSessionId: sessionId, receipt: pickerReceipt,
  }) : undefined;
  pickerPreviewStatus.textContent = previewRequest ? "Loading preview…" : row.current
    ? "No saved preview is available for the current session." : "Preview unavailable.";
  refresh();
}
function renderPreview(data: RecordValue) {
  if (!selectedSession) return;
  element("#sessions-modified").textContent = formatModified(selectedSession.row.modified, true) || "Unavailable";
  element("#sessions-model").textContent = data.model || "Unavailable";
  element("#sessions-tokens").textContent = Number.isSafeInteger(data.tokens) ? data.tokens.toLocaleString() : "Unavailable";
  element("#sessions-user").textContent = data.user || "No saved user text.";
  element("#sessions-assistant").textContent = data.assistant || "No saved assistant text for this turn.";
  pickerContent.hidden = false;
  pickerPreviewStatus.dataset.ready = "true";
  pickerPreviewStatus.textContent = "Preview ready.";
}
function renderSessions(data: RecordValue) {
  pickerReceipt = data.receipt;
  nextOffset = typeof data.nextOffset === "number" ? data.nextOffset : undefined;
  previousOffset = typeof data.previousOffset === "number" ? data.previousOffset : undefined;
  pickerNext.hidden = nextOffset === undefined;
  pickerPrev.hidden = previousOffset === undefined;
  const rows = Array.isArray(data.sessions) ? [...data.sessions] : [];
  if (data.current) rows.unshift({ label: sessionTitle.textContent, ...data.current });
  pickerStatus.textContent = !data.persistent ? "This chat has no persistent session store."
    : data.sessions?.length ? "" : "No other saved sessions on this page.";
  for (const row of rows) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    const headline = document.createElement("span");
    const title = document.createElement("strong");
    const stamp = document.createElement("time");
    const snippet = document.createElement("small");
    button.type = "button";
    button.setAttribute("aria-pressed", "false");
    if (row.current) button.setAttribute("aria-current", "true");
    title.textContent = row.label;
    headline.className = "sessions-row-title";
    stamp.textContent = formatModified(row.modified);
    if (row.modified) stamp.dateTime = row.modified;
    headline.append(title, stamp);
    snippet.textContent = row.current ? ["Current session", row.snippet].filter(Boolean).join(" · ")
      : row.unavailable || row.snippet || "No saved user text";
    button.append(headline, snippet);
    button.disabled = !!row.unavailable;
    button.addEventListener("click", () => selectSession(row, button));
    item.append(button);
    pickerList.append(item);
  }
}
function addDialog(request: RecordValue) {
  if (!request || typeof request.id !== "string") return;
  if (request.method === "notify") { status.textContent = String(request.message ?? ""); return; }
  if (request.method === "setStatus") { status.textContent = String(request.statusText ?? ""); return; }
  if (request.method === "set_editor_text") { prompt.value = String(request.text ?? ""); renderComposerAction(); return; }
  if (!["confirm", "select", "input", "editor"].includes(request.method)) return;
  if (seenDialogs.has(request.id)) return;
  seenDialogs.add(request.id);
  dialogQueue.push(request);
  void nextDialog();
}
async function nextDialog() {
  if (dialogActive || !connected || !dialogQueue.length) return;
  dialogActive = true;
  refresh();
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
  refresh();
  void nextDialog();
}
function handleEvent(event: RecordValue) {
  if (!event || typeof event.type !== "string") return;
  switch (event.type) {
    case "agent_start": if (state !== "stopping" && state !== "error") setStatus("running"); break;
    case "session_info_changed": updateName(event.name); break;
    case "agent_settled":
      promptPending = false;
      if (state !== "stopping" && state !== "error") setStatus("idle");
      break;
    case "message_start":
      if (event.message?.role === "assistant") {
        const view = createMessage("assistant", "");
        clearActivity();
        runView = view; runFailure = false;
        registerOwners(event.message, view, true);
        stream = { view, blocks: new Map(), message: event.message };
        renderActivity();
      }
      else if (event.message?.role === "user" && submittedUser) {
        observeUser(event.message);
        submittedUser.body.textContent = textOf(event.message);
        submittedUser = undefined;
      } else showMessage(event.message);
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
          runFailure = messageOutcome(event.message, stream.view) || runFailure;
        } else {
          const view = showMessage(event.message);
          if (view) { registerOwners(event.message, view, true); runView = view; runFailure = messageOutcome(event.message, view) || runFailure; }
        }
        stream = undefined;
        renderActivity();
      }
      break;
    case "extension_ui_request": addDialog(event); break;
  }
}
function handleFrame(frame: RecordValue) {
  switch (frame.type) {
    case "snapshot": {
      discardSubmittedUser();
      applyControls(frame.state);
      // Only the route's own snapshot can reach this point. Rebuild native text
      // and ownership, retaining page-local blocks from this same connection.
      const focused = document.activeElement instanceof HTMLElement &&
        ([...liveBlocks.values()].some(block => block.contains(document.activeElement)) ||
          !!stream?.view.body.contains(document.activeElement))
        ? document.activeElement : null;
      clearActivity();
      firstUserPreview = ""; firstUserSeen = false;
      updateName(frame.state?.sessionName);
      if (!["running", "stopping"].includes(frame.state?.status)) stream = undefined;
      runView = undefined; runActive = false; runFailure = false;
      transcript.replaceChildren();
      owners.clear();
      const messages = Array.isArray(frame.messages) ? frame.messages : [];
      for (const message of messages) {
        const view = showMessage(message);
        if (message.role === "user") runView = undefined;
        else if (message.role === "assistant") runView = view;
      }
      const snapshotView = stream?.view || runView;
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
      runActive = ["running", "stopping"].includes(frame.state?.status);
      runView = runActive ? snapshotView : undefined;
      runFailure = !!runView?.node.querySelector(".reply-outcome");
      setStatus(statuses.includes(frame.state?.status) ? frame.state.status : "error");
      for (const request of Array.isArray(frame.dialogs) ? frame.dialogs : []) addDialog(request);
      break;
    }
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
      if (Array.isArray(frame.modelChoices) && Array.isArray(frame.thinkingLevels)) applyControls(frame);
      if (statuses.includes(frame.status)) setStatus(frame.status, typeof frame.message === "string" ? frame.message : undefined);
      else refreshControls();
      break;
    case "ack": {
      const kind = pending.get(frame.id);
      pending.delete(frame.id);
      if (!kind) break;
      if (kind === "set_model" || kind === "set_thinking_level") {
        controlsPending = false;
        controlsNotice = frame.success ? "" : `Could not apply message settings: ${frame.error || "Try again."}`;
        refresh();
        break;
      }
      if (kind === "preview_session") {
        if (!picker.open || previewRequest !== frame.id) break;
        previewRequest = undefined;
        previewReady = true;
        if (frame.success) renderPreview(frame.data ?? {});
        else pickerPreviewStatus.textContent = String(frame.error ?? "Preview unavailable.");
        refresh();
        break;
      }
      if (kind === "list_sessions") {
        pickerBusy = false;
        if (picker.open && frame.success) renderSessions(frame.data ?? {});
        else if (picker.open) pickerOpenFailure(String(frame.error ?? "Sessions request failed."));
        refresh();
        break;
      }
      if (kind === "prompt") {
        promptPending = false;
        if (frame.success && frame.data?.disposition === "handled") setStatus("idle");
      }
      if (kind === "rename") {
        renamePending = false;
        if (frame.success) {
          updateName(frame.data?.sessionName);
          closeRename(document.activeElement === nameInput);
        } else renameError.textContent = `Could not rename: ${frame.error || "Try again."}`;
        refresh(); break;
      }
      if (!frame.success) {
        status.textContent = String(frame.error ?? "Request failed");
        const recovery = state === "error" ? "error" : kind === "prompt" ? "idle" : kind === "stop" ? "running" : state;
        setStatus(recovery);
      }
      refresh();
      break;
    }
  }
}
sessions.addEventListener("click", () => {
  if (sessions.disabled || picker.open || pickerBusy) return;
  picker.showModal();
  loadSessions();
});
pickerClose.addEventListener("click", () => picker.close());
picker.addEventListener("cancel", event => { if (switching) event.preventDefault(); });
picker.addEventListener("close", () => {
  if (picker.open) return;
  resetPickerChoice();
  pickerList.replaceChildren();
  pickerReceipt = undefined;
  if (!sessions.disabled) sessions.focus();
});
pickerBack.addEventListener("click", () => {
  const selectedButton = selectedSession?.button;
  resetPickerChoice();
  pickerDirectory.scrollTop = directoryScroll;
  selectedButton?.focus({ preventScroll: true });
  refresh();
});
pickerCompact.addEventListener("change", () => {
  if (!picker.open || !selectedSession) return;
  if (pickerCompact.matches && pickerDirectory.contains(document.activeElement)) pickerTarget.focus({ preventScroll: true });
  if (!pickerCompact.matches && document.activeElement === pickerBack) pickerTarget.focus({ preventScroll: true });
});
pickerPrev.addEventListener("click", () => { if (previousOffset !== undefined) loadSessions(previousOffset, true); });
pickerNext.addEventListener("click", () => { if (nextOffset !== undefined) loadSessions(nextOffset, true); });
pickerReload.addEventListener("click", () => loadSessions(0, true));
function pickerOpenFailure(message: string) {
  pickerStatus.textContent = message;
  if (state === "error") status.textContent = message;
  pickerReceipt = undefined;
  pickerPrev.hidden = pickerNext.hidden = true;
  pickerReload.hidden = state === "error";
  refresh();
  (pickerReload.hidden ? pickerClose : pickerReload).focus();
}
async function openSelectedSession() {
  if (pickerOpen.disabled || !pickerReceipt || !selectedSession || !sessionPath ||
      !sessionId || !admission || !pairTicket) return;
  const target = selectedSession.row.id;
  const ticket = pairTicket;
  switching = true;
  pickerStatus.textContent = "Opening session…";
  pickerTarget.focus({ preventScroll: true });
  refresh();
  let error = "Could not confirm the open. Reload Sessions before trying again.";
  try {
    const response = await fetch(`${sessionPath}/open`, {
      method: "POST", cache: "no-store", redirect: "error",
      headers: { Authorization: `Bearer ${admission}`, "Content-Type": "application/json" },
      body: JSON.stringify({ ticket, nonce: crypto.randomUUID(), receipt: pickerReceipt, sessionId: target, inactiveConfirmed: true }),
      signal: AbortSignal.any([lifecycle.signal, AbortSignal.timeout(60000)]),
    });
    const result = await response.json();
    if (disposed || ticket !== pairTicket) return;
    if (!response.ok) {
      if (typeof result.error === "string") error = result.error;
    } else if (result.sessionId === target && typeof target === "string") {
      const url = savedSessionURL(result.url, target);
      if (url) {
        const outgoingDrafts = new Map(drafts);
        if (prompt.value) outgoingDrafts.set(sessionId, prompt.value);
        if (carryDrafts(target, outgoingDrafts)) {
          location.assign(url.href);
          return;
        }
        error = "Could not carry drafts to the next session. Copy or clear your draft before opening.";
      }
    }
  } catch { /* The open may have been prepared; never retry automatically. */ }
  if (disposed || ticket !== pairTicket) return;
  switching = false;
  pickerOpenFailure(error);
}
pickerOpen.addEventListener("click", () => { void openSelectedSession(); });
newChatForm.addEventListener("submit", event => {
  if (newChat.disabled || !sessionId || !admission || !pairTicket) event.preventDefault();
});
newChatForm.addEventListener("formdata", event => {
  if (!sessionId || !admission || !pairTicket) return;
  // Stay out of URL parameters and DOM inputs. The browser submits the form
  // directly from this trusted action; noopener prevents cloned storage.
  event.formData.set("sourceSessionId", sessionId);
  event.formData.set("admission", admission);
  event.formData.set("ticket", pairTicket);
  event.formData.set("nonce", crypto.randomUUID());
});
function clearRenameError() {
  renameError.textContent = "";
  nameInput.removeAttribute("aria-invalid");
}
function closeRename(restoreFocus: boolean) {
  renameForm.hidden = true;
  delete titleRow.dataset.editing;
  clearRenameError();
  if (restoreFocus && !rename.disabled) rename.focus({ preventScroll: true });
}
function editName() {
  if (rename.disabled || !renameForm.hidden) return;
  renameInitial = sessionTitle.textContent?.trim() ?? "";
  renameAttempt = undefined;
  nameInput.value = renameInitial;
  renameForm.hidden = false;
  titleRow.dataset.editing = "";
  clearRenameError();
  nameInput.focus({ preventScroll: true });
  nameInput.select();
}
function saveName(fromBlur: boolean) {
  if (renameForm.hidden || renamePending) return;
  const name = nameInput.value.trim();
  if (fromBlur && name === renameAttempt) return;
  if (name === renameInitial) { closeRename(!fromBlur); return; }
  if (!name) {
    renameError.textContent = "Enter a session name.";
    nameInput.setAttribute("aria-invalid", "true");
    return;
  }
  renameAttempt = name;
  if (!rename.disabled && command("rename", { name })) {
    renamePending = true;
    clearRenameError();
    refresh();
  } else renameError.textContent = "Connection unavailable. Reconnect before saving.";
}
rename.addEventListener("click", editName);
sessionTitle.addEventListener("click", editName);
nameInput.addEventListener("input", () => { renameAttempt = undefined; clearRenameError(); });
nameInput.addEventListener("blur", () => saveName(true));
nameInput.addEventListener("keydown", event => {
  if (event.isComposing) return;
  if (event.key === "Escape" && !renamePending) {
    event.preventDefault();
    closeRename(true);
  }
});
renameForm.addEventListener("submit", event => { event.preventDefault(); saveName(false); });
form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = prompt.value.trim();
  if (!message || !canSend()) return;
  if (command("prompt", { message })) {
    submittedUser = createMessage("user", message);
    reveal(submittedUser);
    prompt.value = ""; promptPending = true; setStatus("running");
  }
});
prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); form.requestSubmit(); }
});
function requestStop() {
  if (canStop() && command("stop")) setStatus("stopping");
}
prompt.addEventListener("input", renderComposerAction);
send.addEventListener("click", () => { if (canStop()) requestStop(); else if (canSend()) form.requestSubmit(); });
dialog.addEventListener("stop-request", requestStop);

updateName(sessionName);
// An admission link pasted into the same path can be hash-only navigation.
window.addEventListener("hashchange", () => {
  if (new URLSearchParams(location.hash.slice(1)).has("admission")) location.reload();
});

const lifecycle = new AbortController();
const browserTrust = sessionPath && createBrowserTrustRenewal({
  sessionPath,
  getWriter: () => connected && admission && pairTicket ? { admission, ticket: pairTicket } : undefined,
});
let connecting = false;
let terminal = !admission || !sessionPath;
let disposed = false;
let connectionEpoch = 0;
let snapshotReceived = false;
const delay = (ms: number) => new Promise<void>(resolve => window.setTimeout(resolve, ms));
function showConnection(label: string, detail = "") {
  connection.textContent = label;
  connectionDetail.textContent = detail;
  connectButton.hidden = connected;
  connectButton.disabled = connecting || terminal || bridgeNeedsReload();
  connectButton.textContent = "Retry connection";
}
function disconnectView() {
  const wasActive = runActive;
  const hadReply = !!runView;
  const previousNotice = status.textContent;
  connected = false; snapshotReceived = false; pairTicket = undefined; generation++;
  browserTrust?.stop();
  dialogQueue = []; seenDialogs.clear(); dialog.cancel(); pending.clear(); promptPending = false;
  controlsNotice = controlsPending ? "Connection lost. Confirm settings after reconnecting before trying again." : "";
  controlsPending = false;
  applyControls();
  const wasSwitching = switching;
  switching = pickerBusy = false;
  if (picker.open) picker.close();
  notifyOwnerWaiters(); setUIAvailable(false);
  stream = undefined;
  liveBlocks.clear(); liveOwners.clear(); finishedContexts.clear();
  renamePending = false;
  if (!renameForm.hidden) renameError.textContent = "Connection lost. Confirm the saved name after reconnecting before retrying.";
  setStatus("error", "Connection lost; reply interrupted.");
  // Connection notices belong to the header/detail, not stale input errors.
  if (wasSwitching) status.textContent = "Connection lost while opening a session. No open request was resent.";
  else if (!wasActive) status.textContent = previousNotice;
  else if (!hadReply) status.textContent = "Reply interrupted before a response arrived.";
}
function closeConnections() {
  pairTicket = undefined;
  const previous = socket; socket = undefined;
  previous?.close();
  closeBridge();
}
async function openChat(epoch: number, ticket: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const candidate = new WebSocket(`${wsOrigin}${sessionPath}/chat?${new URLSearchParams({ token: ticket })}`);
    socket = candidate;
    const deadline = window.setTimeout(() => { candidate.close(); reject(new Error("Connection timed out")); }, 10000);
    candidate.addEventListener("message", event => {
      if (socket !== candidate || epoch !== connectionEpoch || disposed) return;
      try {
        const frame = JSON.parse(event.data);
        if (frame.type === "snapshot") {
          if (frame.state?.sessionId !== sessionId || bridgeWindow.awr?.status !== "connected") {
            throw new Error("Session snapshot does not match the admitted route");
          }
          snapshotReceived = connected = true;
        } else if (!snapshotReceived) throw new Error("Expected the session snapshot first");
        handleFrame(frame);
        if (snapshotReceived && connected) { clearTimeout(deadline); resolve(); }
      } catch { clearTimeout(deadline); candidate.close(); reject(new Error("Invalid server message")); }
    });
    candidate.addEventListener("close", () => {
      clearTimeout(deadline);
      if (socket !== candidate || epoch !== connectionEpoch || disposed) return;
      socket = undefined;
      const established = snapshotReceived;
      disconnectView();
      // A failed transport pair is not evidence against the saved credential.
      reject(new Error("Chat connection closed"));
      if (established && !connecting) void reconnect();
    });
    candidate.addEventListener("error", () => { /* close/deadline handles recovery */ });
  });
}
async function reconnect() {
  if (connecting || terminal || disposed || bridgeNeedsReload()) return;
  connecting = true;
  const epoch = ++connectionEpoch;
  if (connected || snapshotReceived) disconnectView();
  showConnection("Connecting…", "Connecting to this session; no messages are resent.");
  let detail = "Connection unavailable. Check that the existing host is running, then Retry connection.";
  for (let attempt = 0; attempt < 5 && !terminal && !disposed; attempt++) {
    closeConnections();
    if (attempt) await delay([0, 500, 2000, 4000, 5000][attempt]);
    if (disposed || epoch !== connectionEpoch) break;
    try {
      const response = await fetch(`${sessionPath}/chat/connection`, {
        method: "POST", headers: { Authorization: `Bearer ${admission}` }, cache: "no-store", redirect: "error",
        signal: AbortSignal.any([lifecycle.signal, AbortSignal.timeout(5000)]),
      });
      if (disposed || epoch !== connectionEpoch) break;
      if (response.status === 403) {
        terminal = true; clearAdmission();
        detail = "Access credential rejected or expired. Open this session again from the existing host."; break;
      }
      if (response.status === 410) {
        terminal = true; detail = "The Web Chat host shut down."; break;
      }
      if (response.status === 409) {
        const { code } = await response.json();
        if (code === "writer_active") {
          detail = "This session is open in another tab. Close that tab before retrying here."; break;
        }
        detail = code === "pair_reserved" ? "A connection is still being established. Wait briefly, then Retry connection."
          : "The previous connection is still stopping. Wait briefly, then Retry connection.";
        continue;
      }
      if (!response.ok) continue;
      const { ticket } = await response.json();
      if (disposed || epoch !== connectionEpoch) break;
      if (typeof ticket !== "string" || !/^[A-Za-z0-9_-]{1,256}$/.test(ticket)) continue;
      const bridge = await prepareBridge(ticket);
      if (disposed || epoch !== connectionEpoch) break;
      await bridge.connect();
      if (disposed || epoch !== connectionEpoch) break;
      if (bridge.status !== "connected") continue;
      await openChat(epoch, ticket);
      if (disposed || epoch !== connectionEpoch) break;
      pairTicket = ticket;
      connected = true; connecting = false;
      browserTrust?.start();
      setUIAvailable(true); refresh(); showConnection("Connected"); return;
    } catch {
      if (bridgeNeedsReload()) {
        detail = "The UI bridge did not load. Reload this tab to reconnect to the same session."; break;
      }
      // Bounded transport/admission retries; never replay commands.
    }
  }
  closeConnections(); connecting = false; connected = false;
  refresh(); showConnection("Disconnected", detail);
}
connectButton.addEventListener("click", () => { void reconnect(); });
if (terminal) {
  showConnection("Disconnected", "Missing access credential. Open the admission URL from the existing host; connecting never starts a new agent.");
  setStatus("error");
} else void reconnect();
const bridgeWatch = window.setInterval(() => {
  if (!connected || connecting || disposed) return;
  if (bridgeWindow.awr?.status !== "connected") {
    disconnectView(); closeConnections(); void reconnect();
  }
}, 250);
window.addEventListener("pagehide", () => {
  browserTrust?.dispose();
  disposed = true; connectionEpoch++; lifecycle.abort(); window.clearInterval(bridgeWatch); closeConnections();
}, { once: true });
window.addEventListener("pageshow", event => {
  if (event.persisted && disposed) location.reload();
});
