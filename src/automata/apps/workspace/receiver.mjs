// Backend service adapter, using the maintained router client without wire forks.
// stdin/stdout is private to its owning Python process; never exposed over HTTP.
import { createInterface } from "node:readline";
import { pathToFileURL } from "node:url";

const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
let client, credentials, stopped = false, timer, attempts = 0, opening = false;
const emit = value => process.stdout.write(JSON.stringify(value) + "\n");
function retry() {
  if (stopped || timer || opening || attempts >= 6) return;
  timer = setTimeout(() => { timer = null; void connect(); }, Math.min(1000 * 2 ** attempts++, 15000));
}
async function connect() {
  if (opening || stopped) return;
  opening = true;
  try { await client.connect(credentials); attempts = 0; emit({ type: "state", phase: "connected" }); }
  catch { emit({ type: "state", phase: "offline" }); }
  finally { opening = false; if (!client.isConnected()) retry(); }
}
lines.on("line", async line => {
  try {
    if (line.length > 128 * 1024) throw new Error("frame too large");
    const value = JSON.parse(line);
    if (value.type === "start" && !client) {
      const { createMessageRouterClient } = await import(pathToFileURL(value.clientModule).href);
      credentials = value.credentials;
      client = createMessageRouterClient({
        onMessage: message => {
          if (!message.expectReply) return;
          emit({ type: "post", id: message.id, provenance: message.from, payload: message.payload });
        },
        onState: event => {
          if (event.status === "disconnected") { emit({ type: "state", phase: "offline" }); retry(); }
        },
      });
      await connect();
    } else if (value.type === "receipt" && client) {
      try { await client.respond(value.id, value.payload); }
      catch { /* Save may have succeeded after disconnect. Retry same operation ID. */ }
    }
  } catch { emit({ type: "state", phase: "failed" }); }
});
lines.on("close", () => {
  stopped = true; clearTimeout(timer); client?.close(); process.exit(0);
});
