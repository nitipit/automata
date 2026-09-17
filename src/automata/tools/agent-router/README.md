# agent-router

Loopback WebSocket routing between authorized pages and agents. The router owns
identity, directed permissions and connection-bound correlation—not Chat, model
turns, Pi context buffers or UI construction. Page-to-page traffic never needs an
agent. No automatic reconnect, replay, durable queue or implicit destination.

## Setup and serve

```sh
uv run --offline --no-project --script .agents/tools/agent-router/agent_router.py setup
uv run --offline --no-project --script .agents/tools/agent-router/agent_router.py serve
uv run --offline --no-project --script .agents/tools/agent-router/agent_router.py status
```

Default setup creates `page` and `agent`, with one directed `page:agent` grant.
Custom topologies require explicit grants:

```sh
uv run --offline --no-project --script .agents/tools/agent-router/agent_router.py setup \
  --config-file /private/router.json \
  --page dashboard --page inspector --agent primary --agent reviewer \
  --allow dashboard:inspector --allow dashboard:primary \
  --allow primary:reviewer --allow reviewer:primary
uv run --offline --no-project --script .agents/tools/agent-router/agent_router.py serve \
  --config-file /private/router.json --endpoint-dir /private/endpoints --port 8787
```

Setup only creates private configuration. It neither starts processes nor creates
UI directories. A pre-existing config is never silently overwritten. Configuration
is `{v:1,participants:{id:{kind:"page"|"agent",token,allow:[destinationIds]}}}`;
review grants explicitly and restart the owned server after configuration changes.
IDs are 1–128 ASCII letters, digits, `_` or `-`; tokens must be distinct. Up to 128
participants are supported. An active identity cannot be displaced by reconnecting.

Serve publishes mode-0600 records **after binding**:

- `<endpoint-dir>/server.json`: listener/owner metadata, without participant tokens.
- `<endpoint-dir>/participants/<id>.json`: that participant's credential and URL.

Defaults are under `.agents/var/tools/agent-router/`, with configuration in
`config.json` and endpoint records in `endpoints/`. Each shutdown removes only its
own records, not configuration. Stale records require ownership inspection before
removal. A fresh setup does not depend on retained operational data.

Static hosting is optional: `--public-root /path/to/public-safe-files` mounts that
directory at `/`. There is no required directory name or Adaptive UI dependency.
The server also exposes `/assets/` browser modules and `/health`. It refuses overlap
between private configuration/endpoints and public roots, dotfiles, traversal and
escaping symlinks. Choose a public-safe root: the server cannot identify arbitrary
application secrets. Do not serve a whole workspace or repository indiscriminately.

By default, browser WebSocket Origin must equal this server's origin. For a
separately hosted frontend, explicitly pass `--origin http://127.0.0.1:3000` and
bundle/copy the browser modules into that frontend. Node clients may omit Origin,
but still require credentials. The listener binds only `127.0.0.1`.

## Browser / Node client

Import `createAgentRouterClient` from `browser/client.js` (or `/assets/client.js`
when served here). Provide the intended participant's credential out of band;
never embed credentials in public assets or fetch private endpoint files through
the static server. Do not give a page an agent's credential or the master config.

```js
const client = createAgentRouterClient({
  onMessage: async message => {
    render(message.payload); // component-owned handling, not routing policy
    if (message.expectReply) await client.respond(message.id, {handled: true});
  },
  onResponse: response => showResponse(response),
});
await client.connect(credentials); // wsUrl, participant, token; agents also sessionId
const request = client.send("inspector", {selection: "button#save"});
await request.accepted; // transport forwarding only, not recipient handling
// client.cancel(request.id) abandons correlation; it cannot retract peer actions.
```

`send(to,payload,{metadata?,expectReply?,onResponse?})` returns `{id,accepted}`.
`expectReply` defaults true. Responses may precede the accepted promise. Page
notifications may use false and allocate no reply capability; the Pi adapter
requires true for admission/receipts and ignores fire-and-forget notifications.
`respond(message.id,payload,{metadata?,final?})` sends a response; final defaults
true. Intermediate receipts use false. A reply needs no reverse grant: only the
exact recipient connection receives the original request's reply capability.
`status()` lists only the caller's granted destinations and their current presence.
`close()` invalidates pending work. Reconnect explicitly and never auto-resend
uncertain requests. The last 128 request IDs per connection detect duplicates;
this is bounded suppression, not exactly-once execution.

Payload: any interoperable JSON, including null, up to 32 KiB and depth 32.
Metadata: opaque application JSON up to 16 KiB. Complete text frames: 64 KiB.
Validation retains finite/safe JS numbers, duplicate-wire-key rejection on the
server, and the non-lossy JSON restrictions documented in [LEGACY.md](LEGACY.md).
There are at most 64 pending reply capabilities involving each connection, 64
client transport requests, and 32 outbound Pi requests. Final response, explicit
cancel, or either endpoint's disconnect releases correlation. No time-based expiry
silently discards next-prompt context; inspect/cancel/close bounded pending work.

## Pi adapter and Chat

Install the `agent-router` Pi extension bundle. `agent_router` is the primary tool;
`agent_browser_bridge` remains a compatibility alias sharing the same state.

- `open`: optional `endpoint` selects a private **agent** credential file. Defaults
  to `AUTOMATA_AGENT_ROUTER_ENDPOINT`, then the default `agent.json` endpoint.
  It binds the current Pi session; it never starts a server or another agent.
- `route`: explicit `to`, complete `payload`, optional Pi `delivery` options. Returns
  an outgoing id after transport acknowledgment, not a model/peer answer.
- `receive`: use the outgoing id as `replyTo`. Pending returns the latest bounded
  receipt; terminal returns/consumes the reply. Replies do not launch another model
  turn. Use normal coordination rather than busy-polling.
- `cancel`: outgoing id as `replyTo`; releases correlation, not recipient effects.
- `send` / `reject`: exact pending **inbound** id as `replyTo`, and `payload` or
  `reason`. The canonical message includes authenticated participant provenance.
- `status`, `inspect_context`, `clear_context`, `close`: session-owned inspection
  and lifecycle. Session switch, fork, tree navigation, reload or exit invalidates
  the binding and ephemeral context; late replies cannot bind to replacements.

`browser/pi-client.js` exports `createAgentRouterChatClient({to,onMessage,onState,
onDelivery})`. Connect with the **page** credential. It retains `sendMessage`,
`inspectContext`, `clearContext`, reply callbacks and Pi delivery options from the
[existing Chat contract](LEGACY.md#delivery-options-and-buffered-context). Initial
remote busy state is unknown in v2; the Pi adapter checks actual admission state
and returns an explicit rejection when immediate delivery is unavailable.

Generic clients can send Pi metadata as `{pi:{delivery:{role,deliverAs,slot?,
triggerTurn?}}}` or `{pi:{kind:"context_control",action:"inspect"|"clear",slot?}}`.
Pi receipts live in response metadata under `pi`; component replies remain complete
payloads. Canonical Pi admission—not a router acknowledgment—confirms `attached`.
Named context slots and remote inspection/clear are scoped to the authenticated
sender (and sending agent session). The receiving Pi tool can inspect/clear all
its own pending context. A page reconnect can inspect retained context, but cannot
recreate invalidated reply channels or retract already admitted historical data.

## Migration and implementation boundaries

- Canonical tool/skill/extension names are `agent-router`, `automata-agent-router`,
  and `agent-router/` respectively. The installer supports Pi's native `index.ts`
  bundles as well as existing single-file extensions.
- Do not load the old `agent-browser-bridge.ts` alongside the new extension: both
  would register the compatibility tool name. Inspect local changes and remove
  the old installation only within an approved migration. No automatic uninstall.
- Existing v1 browser clients can use the explicitly selected `legacy-serve`
  command or the bundled `agent_browser_bridge.py serve` entry. See [LEGACY.md](LEGACY.md).
  They cannot speak v2 merely by changing their URL; upgrade credentials/client
  together. The v1 adapter does not gain multiparty routing.
- Python responsibilities: `protocol.py` validates JSON, `router.py` owns routing,
  `server.py` owns ASGI/static boundaries, `cli.py` owns process/endpoint lifecycle,
  `legacy.py` owns v1 single-pair behavior. Pi transport and context/admission live
  in separate extension modules. No application payload is executed by the router.

Authorized connectivity is not permission to delegate work or execute peer-supplied
instructions. Distinguish connection, forwarding, Pi admission, reply emission and
component handling; none imply the next outcome automatically.
