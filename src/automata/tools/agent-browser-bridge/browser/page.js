import { createAgentBrowserBridgeClient } from "/assets/client.js";

/** Mount a tiny transport-only page for smoke checks and tool examples. */
export function mountAgentBrowserBridgePage(root = document.querySelector("main")) {
  if (!root) throw new Error("A page root is required");
  const status = document.createElement("p");
  const input = document.createElement("textarea");
  const button = document.createElement("button");
  button.textContent = "Send";
  root.replaceChildren(status, input, button);
  const setStatus = (state) => {
    status.textContent = state.status === "replied"
      ? state.text
      : state.error?.message ?? state.message ?? state.status;
  };
  const client = createAgentBrowserBridgeClient({
    onState: setStatus,
    onMessage: (envelope) => setStatus({ status: "replied", text: JSON.stringify(envelope.payload) }),
  });
  button.addEventListener("click", () => {
    try {
      client.sendMessage({ text: input.value, context: { componentId: "agent-browser-bridge-page" } });
      input.value = "";
    } catch (error) {
      setStatus({ status: "error", error });
    }
  });
  client.connect();
  return client;
}
