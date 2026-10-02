/** Page composition wires transport; Chat still owns payloads and admission state.
 * No implicit connection, retry, replay, persisted credentials or model history.
 */
export function bindChatTransport(chat, { sampleReply, createLiveClient, onState = () => {} }) {
  let mode = "sample";
  let client;
  let generation = 0;
  let alive = true;
  function notify(message) { if (alive) onState(message); }
  function retire() {
    generation++;
    const previous = client;
    client = undefined;
    previous?.close();
    chat.interrupt("Outstanding request interrupted/uncertain · no automatic replay");
  }
  function sample() {
    retire();
    mode = "sample";
    chat.setConnection(true);
    chat.setAgentBusy(false);
    chat.setStatus("Sample agent mode · local replies only · no remote connection");
    notify("SAMPLE AGENT · offline demonstration, not a live agent");
  }
  function disconnected() {
    retire();
    mode = "live";
    chat.setConnection(false);
    notify("LIVE DISCONNECTED · connection credentials are never recovered from cache");
  }
  async function connect(credentials, to) {
    if (!alive) return false;
    disconnected();
    const epoch = generation;
    const current = () => alive && generation === epoch;
    chat.setStatus("Connecting to explicitly selected agent…");
    notify("LIVE · connecting to selected participant");
    try {
      client = createLiveClient({ to,
        onState(state) {
          if (!current()) return;
          switch (state.status) {
            case "connected":
              chat.setConnection(true);
              chat.setAgentBusy(state.agentBusy === true);
              notify("LIVE · authenticated transport; agent admission still required");
              break;
            case "sending": chat.setStatus("Sending · transport receipt pending"); break;
            case "accepted": chat.setStatus("Forwarded · waiting for agent admission"); break;
            case "admitted": chat.setStatus("Agent admitted · waiting for reply"); break;
            case "rejected": chat.reject("Agent/route rejected request · no automatic retry"); break;
            case "disconnected":
              chat.setConnection(false);
              chat.interrupt("Delivery interrupted/uncertain · no automatic replay");
              notify("LIVE DISCONNECTED · prior effects/reply may be uncertain");
              break;
            case "error":
              chat.interrupt("Router failure · delivery may be uncertain · no automatic replay");
              break;
          }
        },
        onMessage(message) {
          if (!current()) return;
          if (message?.v !== 1 || message.kind !== "reply") {
            chat.interrupt("Invalid reply envelope · no automatic retry");
            return;
          }
          chat.receiveMessage(message.payload);
        },
      });
      await client.connect(credentials);
      if (!current()) return false;
      return true;
    } catch {
      if (current()) {
        chat.setConnection(false);
        chat.interrupt("Connection failed · nothing automatically retried");
        notify("LIVE DISCONNECTED · explicit authorized connection required");
      }
      return false;
    }
  }
  const onMessage = event => {
    if (!alive || event.target !== chat) return;
    const payload = event.detail.content;
    const epoch = generation;
    try {
      if (mode === "sample") {
        const reply = sampleReply(payload);
        chat.markSent();
        // Asynchronous boundary exercises replacement/stale-result protection.
        Promise.resolve(reply).then(value => {
          if (alive && generation === epoch) chat.receiveMessage(value);
        }, () => {
          if (alive && generation === epoch) chat.reject("Sample reply failed · no automatic retry");
        });
      } else {
        if (!client?.isConnected()) throw new Error("disconnected");
        client.sendMessage(payload);
        chat.markSent();
      }
    } catch {
      chat.reject("Send failed or uncertain · no automatic retry; check connection state");
    }
  };
  chat.addEventListener("agent-message", onMessage);
  return {
    sample, disconnected, connect,
    getMode: () => mode,
    dispose() {
      alive = false;
      generation++;
      chat.removeEventListener("agent-message", onMessage);
      client?.close();
      client = undefined;
    },
  };
}
