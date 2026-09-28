import { AgentConnection } from "./connection.js";
import { FormComponent } from "../components/form.js";

const HELD = "workspace-pending-post-v1:";
const heldKeys = () => Object.keys(localStorage).filter(key => key.startsWith(HELD));

export function createAgentConversation({ state, api, saveNow, refresh, render, controls, setStatus }) {
  const connection = new AgentConnection(value => controls.setConnection(value));
  const changed = () => { state.dirty = true; state.changeSerial++; };
  const messageAt = detail => state.value.conversations[detail.conversationId]?.messages.find(message => message.id === detail.messageId);

  async function initialize() {
    // Interrupted delivery is not a queue. Confirmed admission remains admission,
    // never becomes a claim that the agent completed the requested work.
    let interrupted = false;
    for (const conversation of Object.values(state.value.conversations)) {
      for (const message of conversation.messages) {
        for (const interaction of [message.delivery, ...Object.values(message.interactions ?? {})]) {
          if (interaction && ["pending", "forwarded"].includes(interaction.status)) {
            interaction.status = "uncertain";
            interaction.detail = "Previous connection ended; not resent";
            interrupted = true;
          }
        }
      }
    }
    if (interrupted) { changed(); render(); await saveNow(); }
    try {
      await connection.initialize(api);
      state.assignment = connection.binding;
      render();
      setStatus(connection.binding ? "Assigned to Automata · posts persist independently of this browser" : "No real agent bound · local saving only");
    } catch (error) { setStatus(`Agent unavailable · ${error.message}`, "error"); }
    try {
      for (const key of heldKeys()) {
        const held = JSON.parse(localStorage.getItem(key));
        const saved = Object.values(state.value.conversations).some(row => row.messages.some(
          m => m.role === "user" && m.operationId === held.operationId
            && JSON.stringify(m.context) === JSON.stringify(held.context)));
        if (saved) localStorage.removeItem(key);
        setStatus(saved ? "Previous input is saved · delivery not replayed" :
          `Previous save uncertain (${held.operationId}) · retained in browser storage; not replayed`, "error");
      }
    } catch { setStatus("Pending input recovery requires review; nothing replayed", "error"); }
  }

  async function post(content, detail = null, originalDraft = null) {
    if (!state.ready || state.sendPending || state.conflicted) return;
    const conversationId = detail?.conversationId ?? state.value.view.selectedConversationId;
    const operationId = crypto.randomUUID();
    const envelope = { operationId, context: { projectId: state.value.projectId, conversationId }, content };
    state.sendPending = true;
    controls.setLocked(true);
    clearTimeout(state.timer);
    try {
      if (!await saveNow()) throw new Error("Local drafts not saved; input was not posted");
      // Persist the operation identity before HTTP. Unknown saves are never retried
      // automatically; same-ID reconciliation is a deliberate operator action.
      if (heldKeys().length) throw new Error("A previous uncertain save needs review before another input");
      localStorage.setItem(HELD + operationId, JSON.stringify(envelope));
      state.uncertainSend = operationId;
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);
      let receipt;
      try {
        receipt = await api("/api/conversation-posts", { method: "POST", body: JSON.stringify(envelope), signal: controller.signal });
      } finally { clearTimeout(timeout); }
      if (receipt.status !== "saved" || receipt.operationId !== operationId) throw new Error("Invalid save receipt");
      localStorage.removeItem(HELD + operationId);
      state.uncertainSend = null;
      await refresh();
      const conversation = state.value.conversations[conversationId];
      if (originalDraft !== null && conversation.draft === originalDraft) conversation.draft = "";
      changed(); render();
      const findInteractions = () => {
        const row = state.value.conversations[conversationId];
        const message = row.messages.find(m => m.id === receipt.messageId);
        const form = detail ? messageAt(detail)?.interactions?.[detail.componentId] : null;
        return [message?.delivery, form].filter(Boolean);
      };
      try {
        setStatus("Saved · awaiting agent admission, not task completion", "pending");
        const admission = await connection.deliver({ ...envelope, receipt, postTo: "workspace-app" });
        for (const interaction of findInteractions()) Object.assign(interaction, admission, {
          detail: "Agent admitted input; progress/results arrive as independent saved posts" });
        changed(); render(); await saveNow();
        setStatus("Saved · agent admitted input · awaiting independent posts");
      } catch (error) {
        for (const interaction of findInteractions()) Object.assign(interaction, {
          status: "uncertain", detail: String(error.message).slice(0, 1000) });
        changed(); render(); await saveNow();
        setStatus(`Saved · agent delivery uncertain · ${error.message} · no replay`, "error");
      }
    } catch (error) {
      // A definite validation rejection permits a new corrected input. Network
      // failures keep the exact envelope/ID for deliberate reconciliation.
      if (error.status === 422 || error.status === 403) {
        localStorage.removeItem(HELD + operationId); state.uncertainSend = null;
      }
      setStatus(`${error.message} · no automatic replay`, "error");
    } finally {
      state.sendPending = false;
      controls.setLocked(state.conflicted);
    }
  }

  async function send(text) {
    if (!text) return;
    // The composer trims message content, not its durable draft (Enter adds a
    // newline). Compare against the exact raw snapshot so a saved trailing newline
    // clears, while a newer draft adopted during the request is never erased.
    const draft = state.value?.conversations[state.value.view.selectedConversationId]?.draft;
    const originalDraft = typeof draft === "string" && draft.trim() === text ? draft : null;
    await post([{ id: "text", type: "text", version: 1, data: { text } }], null, originalDraft);
  }

  function draft(detail) {
    const message = messageAt(detail);
    const description = message?.content?.find(item => item.id === detail.componentId && item.type === "form");
    if (!description || state.conflicted) return;
    message.interactions ??= {};
    const previous = message.interactions[detail.componentId];
    if (previous && previous.status !== "draft") return;
    try {
      const values = FormComponent.validateValues(FormComponent.validateData(description.data), detail.values, false);
      message.interactions[detail.componentId] = { status: "draft", values };
      changed();
      clearTimeout(state.timer);
      state.timer = setTimeout(saveNow, 250);
    } catch (error) { setStatus(error.message, "error"); }
  }

  async function submit(detail) {
    if (state.sendPending || state.conflicted) return;
    const message = messageAt(detail);
    const description = message?.content?.find(item => item.id === detail.componentId && item.type === "form");
    if (!description) return;
    const previous = message.interactions?.[detail.componentId];
    if (previous && previous.status !== "draft") return;
    try {
      const values = FormComponent.validateValues(FormComponent.validateData(description.data), detail.values);
      await post([{ id: "response", type: "form-response", version: 1, data: {
        messageId: message.id, componentId: description.id, definition: description.data, values,
      } }], detail);
    } catch (error) { setStatus(error.message, "error"); }
  }
  return { initialize, send, draft, submit,
    boardEvent: payload => connection.requestBoard(payload),
    launch: () => connection.launch(), disconnect: () => connection.disconnect() };
}
