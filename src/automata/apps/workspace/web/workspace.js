import { Base } from "/lib/adaptive-ui.js";
import "./work-surface.js";
import "./conversation-view.js";
import "./bottom-controls.js";
import { createAgentConversation } from "/modules/agent/conversation.js";

const agents = {
  "agent-a": { name: "Aster", conversation: "conversation-aster" },
  "agent-b": { name: "Mira", conversation: "conversation-mira" },
};

class WorkspaceRoot extends Base {
  static { this.css = "display:block; width:100%; height:100%; min-height:0;"; }

  constructor() {
    super();
    this.attachShadow({ mode: "open" }).innerHTML = `
      <link rel="stylesheet" href="/workspace-root.css">
      <div class="app">
        <main class="workspace" aria-label="Project workspace">
          <wsp-surface></wsp-surface>
          <wsp-conversation id="conversation-panel" hidden></wsp-conversation>
        </main>
        <wsp-controls></wsp-controls>
      </div>`;
  }
}

WorkspaceRoot.define("wsp-root");
const root = document.querySelector("wsp-root").shadowRoot;
const controls = root.querySelector("wsp-controls");
const conversationView = root.querySelector("wsp-conversation");
const state = {
  value: null, ready: false, timer: null, saveChain: Promise.resolve(),
  sendPending: false, dirty: false, changeSerial: 0, conflicted: false,
  uncertainSend: null, conversationOpen: false,
};

function setStatus(message, kind = "") { controls.setStatus(message, kind); }
function currentConversation() {
  return state.value.conversations[state.value.view.selectedConversationId];
}
function render() {
  if (!state.ready) return;
  const conversation = currentConversation();
  const name = agents[conversation.agentId].name;
  controls.present(state.value, name);
  controls.setConversationOpen(state.conversationOpen);
  conversationView.present(conversation, name);
  conversationView.hidden = !state.conversationOpen;
}
function setConversationOpen(open) {
  if (state.conversationOpen === open) return;
  state.conversationOpen = open;
  conversationView.hidden = !open;
  controls.setConversationOpen(open);
  if (open) conversationView.focusHeading();
  else controls.focusConversationToggle();
}
async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "content-type": "application/json", ...options.headers },
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(result.detail || `Request failed (${response.status})`);
    error.status = response.status;
    error.currentRevision = result.currentRevision;
    throw error;
  }
  return result;
}

function saveNow() {
  clearTimeout(state.timer);
  if (!state.ready || state.conflicted) return Promise.resolve(false);
  const save = state.saveChain.catch(() => {}).then(async () => {
    if (state.conflicted) return false;
    const serialAtSend = state.changeSerial;
    setStatus("Saving…");
    try {
      const saved = await api("/api/state", { method: "PUT", body: JSON.stringify(state.value) });
      state.value.revision = saved.revision;
      if (state.changeSerial === serialAtSend) {
        state.dirty = false;
        setStatus("All changes saved");
      } else {
        setStatus("Unsaved changes", "pending");
      }
      return true;
    } catch (error) {
      state.dirty = true;
      if (error.status === 409) {
        state.conflicted = true;
        controls.setConflict(true);
        setStatus(`Conflict · local edits kept; server is revision ${error.currentRevision}. Copy local changes before reloading.`, "error");
      } else {
        setStatus(`Save failed · ${error.message} · changes retained here`, "error");
      }
      return false;
    }
  });
  state.saveChain = save;
  return save;
}
function scheduleSave() {
  state.dirty = true;
  state.changeSerial++;
  if (state.conflicted) {
    setStatus("Conflict · local edits kept. Copy them before reloading; no overwrite was sent.", "error");
    return;
  }
  setStatus("Unsaved changes", "pending");
  clearTimeout(state.timer);
  state.timer = setTimeout(saveNow, 250);
}
function selectAgent(agentId) {
  const conversationId = agents[agentId]?.conversation;
  if (!state.ready || !conversationId || state.sendPending || state.uncertainSend) return;
  currentConversation().draft = controls.draftText;
  state.value.view.selectedConversationId = conversationId;
  render();
  scheduleSave();
}
const agentConversation = createAgentConversation({ state, api, saveNow, render, controls, setStatus });
conversationView.addEventListener("component-draft", event => agentConversation.draft(event.detail));
conversationView.addEventListener("component-submit", event => void agentConversation.submit(event.detail));
async function copyRecovery() {
  const local = {
    artifact: state.value.artifact,
    conversations: Object.fromEntries(Object.entries(state.value.conversations).map(([id, row]) => [id, {
      draft: row.draft, messages: row.messages,
    }])),
  };
  try {
    await navigator.clipboard.writeText(JSON.stringify(local, null, 2));
    setStatus("Local edits copied. You can now reload to adopt the server revision.");
  } catch {
    setStatus("Copy failed. Preserve this tab and its unsaved draft before reloading.", "error");
  }
}

controls.addEventListener("conversation-toggle", () => {
  setConversationOpen(!state.conversationOpen);
});
controls.addEventListener("draft-change", (event) => {
  if (!state.ready) return;
  currentConversation().draft = event.detail;
  scheduleSave();
});
controls.addEventListener("draft-blur", () => { if (state.dirty) void saveNow(); });
controls.addEventListener("agent-change", (event) => selectAgent(event.detail));
controls.addEventListener("send-message", (event) => void agentConversation.send(event.detail));
controls.addEventListener("copy-recovery", () => void copyRecovery());
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.conversationOpen) {
    event.preventDefault();
    setConversationOpen(false);
  }
});
window.addEventListener("beforeunload", (event) => {
  if (!state.dirty && !state.conflicted && !state.uncertainSend && !state.sendPending) return;
  event.preventDefault();
  event.returnValue = "";
});

try {
  state.value = await api("/api/state");
  state.ready = true;
  render();
  await agentConversation.initialize();
} catch (error) {
  setStatus(`Load failed · ${error.message} · editing disabled`, "error");
  controls.setLocked(true);
}
