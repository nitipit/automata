// Board-owned demo. No host imports, credentials, filesystem or conversation API.
let count = 0;
let generation = null;
let operationId = null;
const notify = document.querySelector("#notify");
function update(value) {
  count = value;
  document.querySelector("output").textContent = `Count: ${count}`;
}
document.querySelector("#add").addEventListener("click", () => update(count + 1));
document.querySelector("#reset").addEventListener("click", () => update(0));
notify.addEventListener("click", () => {
  if (!generation) return;
  operationId = crypto.randomUUID();
  parent.postMessage({ kind: "workspace.board-proposal", version: 1, generation,
    componentId: "demo-counter", operationId, text: `The webboard counter is ${count}.` }, "*");
  document.querySelector("#reply").textContent = "Review and confirm in the host below.";
});
window.addEventListener("message", event => {
  if (event.source !== parent || event.origin !== location.origin) return;
  const value = event.data;
  if (value?.kind === "workspace.board-init" && value.version === 1
      && typeof value.generation === "string" && !generation) {
    const port = event.ports[0];
    if (!port) return;
    generation = value.generation;
    port.onmessage = ({ data: reply }) => {
      if (reply?.kind === "workspace.board-result" && reply.version === 1
          && reply.generation === generation && reply.operationId === operationId
          && typeof reply.text === "string" && reply.text.length <= 4000) {
        document.querySelector("#reply").textContent = reply.text;
      }
    };
    notify.disabled = false;
  }
});
