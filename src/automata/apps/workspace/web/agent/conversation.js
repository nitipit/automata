import { AgentConnection } from "./connection.js";
import { FormComponent } from "../components/form.js";

export function createAgentConversation({ state, api, saveNow, render, controls, setStatus }) {
  const connection = new AgentConnection(value => controls.setConnection(value));
  const changed = () => { state.dirty = true; state.changeSerial++; };
  const messageAt = detail => state.value.conversations[detail.conversationId]?.messages.find(message => message.id === detail.messageId);

  async function initialize() {
    // Interrupted operations are visible uncertainty, never executable work queues.
    let interrupted = false;
    for (const conversation of Object.values(state.value.conversations)) {
      for (const message of conversation.messages) {
        for (const interaction of [message.delivery, ...Object.values(message.interactions ?? {})]) {
          if (interaction && ["pending", "forwarded", "attached"].includes(interaction.status)) {
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
      setStatus(connection.binding ? "Assigned to Automata · connect explicitly to send" : "No real agent bound · sending unavailable");
    } catch (error) { setStatus(`Agent unavailable · ${error.message}`, "error"); }
  }

  async function exchange(conversation, payload, interaction) {
    state.sendPending = true;
    controls.setLocked(true);
    changed();
    render();
    if (!await saveNow()) {
      interaction.status = "failed";
      interaction.detail = "Not sent: local pending record could not be saved";
      changed(); render();
      state.sendPending = false;
      controls.setLocked(state.conflicted);
      return;
    }
    setStatus("Local record saved · awaiting real agent", "pending");
    try {
      const reply = await connection.request(payload, receipt => {
        // Admission/forwarding are not completion; the durable pending record is
        // deliberately conservative if this tab dies before the terminal reply.
        setStatus(`Local record saved · ${receipt?.status ?? "agent receipt"} · awaiting response`, "pending");
      });
      interaction.status = "completed";
      interaction.detail = "Real agent replied";
      interaction.participant = reply.participant;
      if (reply.sessionId) interaction.sessionId = reply.sessionId;
      conversation.messages.push({
        id: `reply-${payload.operationId}`, operationId: payload.operationId, role: "agent",
        text: reply.content.filter(item => item.type === "text").map(item => item.data.text).join("\n").slice(0, 6000),
        content: reply.content, interactions: {},
        author: { agentId: reply.agentId, participant: reply.participant, sessionId: reply.sessionId },
        provenance: "assigned-agent-response",
      });
      changed(); render();
      if (await saveNow()) setStatus("Saved · real agent reply received");
      else setStatus("Agent replied · reply retained here but NOT saved", "error");
    } catch (error) {
      interaction.status = "uncertain";
      interaction.detail = String(error.message).slice(0, 1000);
      changed(); render();
      const saved = await saveNow();
      setStatus(`Delivery uncertain · ${error.message} · no automatic retry${saved ? "" : " · state NOT saved"}`, "error");
    } finally {
      state.sendPending = false;
      controls.setLocked(state.conflicted);
    }
  }

  async function send(text) {
    if (!text || !state.ready || state.sendPending || state.conflicted) return;
    const conversation = state.value.conversations[state.value.view.selectedConversationId];
    if (!connection.isBound(conversation.id)) {
      setStatus("No connected real agent bound to this conversation · nothing sent", "error");
      return;
    }
    const operationId = crypto.randomUUID();
    const message = { id: `message-${operationId}`, operationId, role: "user", text,
      content: [{ id: "text", type: "text", version: 1, data: { text } }],
      delivery: { status: "pending", operationId, detail: "Awaiting transport; not an acknowledgement" } };
    conversation.messages.push(message);
    conversation.draft = "";
    clearTimeout(state.timer);
    await exchange(conversation, {
      kind: "workspace.message", version: 1, projectId: state.value.projectId,
      conversationId: conversation.id, agentId: connection.binding.agentId,
      operationId, messageId: message.id, content: message.content,
    }, message.delivery);
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
    const conversation = state.value.conversations[detail.conversationId];
    const message = messageAt(detail);
    const description = message?.content?.find(item => item.id === detail.componentId && item.type === "form");
    if (!description || !connection.isBound(conversation.id)) {
      setStatus("No connected real agent for this form · nothing submitted", "error");
      return;
    }
    message.interactions ??= {};
    const previous = message.interactions[detail.componentId];
    if (previous && previous.status !== "draft") return;
    try {
      const values = FormComponent.validateValues(FormComponent.validateData(description.data), detail.values);
      const operationId = crypto.randomUUID();
      const interaction = { status: "pending", operationId, values, detail: "Awaiting agent; do not submit again" };
      message.interactions[detail.componentId] = interaction;
      clearTimeout(state.timer);
      await exchange(conversation, {
        kind: "workspace.form-submit", version: 1, projectId: state.value.projectId,
        conversationId: conversation.id, agentId: connection.binding.agentId,
        operationId, messageId: message.id,
        componentId: description.id, componentType: "form", componentVersion: 1, values,
      }, interaction);
    } catch (error) { setStatus(error.message, "error"); }
  }
  return { initialize, send, draft, submit,
    connect: () => connection.connect(), disconnect: () => connection.disconnect() };
}
