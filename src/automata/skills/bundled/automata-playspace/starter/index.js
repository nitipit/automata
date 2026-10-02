import * as adaptiveUI from "./lib/adaptive-ui.js";
import { createCacheRecovery } from "./lib/playspace.js";
import { createMessageRouterClient } from "./router/client.js";
import { createBrowserSessionAuth } from "./router/session.js";
import { createStarter } from "./page.js";

const ids = ["root", "status", "storage", "connection", "target", "code", "save", "restore",
  "pair", "connect", "disconnect", "authStatus"];
const elements = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));
const recovery = createCacheRecovery({
  cacheName: "automata-playspace-core-v1",
  key: new URL("./__playspace_core_snapshot_v1__", location.href).href,
  onState: message => { elements.storage.textContent = message; },
});
const page = createStarter({ elements, adaptiveUI, recovery,
  createClient: createMessageRouterClient, auth: createBrowserSessionAuth() });
globalThis.playspace = page;
function onPageHide(event) {
  if (!event.persisted) {
    page.dispose();
    globalThis.removeEventListener("pagehide", onPageHide);
  }
}
globalThis.addEventListener("pagehide", onPageHide);
await page.ready;
