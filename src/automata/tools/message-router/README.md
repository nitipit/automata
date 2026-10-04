# message-router

Small loopback WebSocket router for a trusted network/application. A **Node** is
an identified endpoint: a browser, agent or ordinary application process. Each
connects independently with its configured private credential. A **Network** is
a named logical routing group, not a LAN, VPN or sandbox. Unknown nodes are not
admitted. No public-application authentication platform is provided.

The router owns identity, central initiation policy and connection-bound
correlation—not Chat, model turns, Pi context buffers or UI construction. Nodes
name explicit destinations and exchange bounded JSON. No automatic reconnect,
replay, durable queue or implicit destination.

## Setup and serve

```sh
uv run --offline --no-project --script .agents/tools/message-router/message_router.py setup
uv run --offline --no-project --script .agents/tools/message-router/message_router.py serve
uv run --offline --no-project --script .agents/tools/message-router/message_router.py status
```

Default setup creates one generic `node` in the `default` Network. Add the nodes
your application needs; same-Network peers may communicate without explicit grants:

```sh
uv run --offline --no-project --script .agents/tools/message-router/message_router.py setup \
  --config-file /private/router.json \
  --node dashboard --node inspector --node primary --node reviewer \
  --network primary:work --network reviewer:work \
  --allow dashboard:primary --block inspector:dashboard
uv run --offline --no-project --script .agents/tools/message-router/message_router.py serve \
  --config-file /private/router.json --endpoint-dir /private/endpoints --port 8787
```

Setup only creates private configuration. It neither starts processes nor creates
UI directories. A pre-existing config is never silently overwritten. Configuration
version 2 is:

```json
{
  "v": 2,
  "nodes": {
    "dashboard": {"token": "<private distinct 32–256 character token>"},
    "inspector": {"token": "<another private token>"},
    "primary": {"token": "<another private token>", "network": "work"},
    "reviewer": {"token": "<another private token>", "network": "work"}
  },
  "allow": ["dashboard:primary"],
  "block": ["inspector:dashboard"]
}
```

`network` defaults to `default`; each node has exactly one Network. Networks are
inferred from node assignments, so no separate registry is needed. `kind` defaults
to `node`; optional `page` (browser-session adapter) and `agent` (requires session
provenance) labels do not change routing permission. CLI `--page`/`--agent` select
those adapters; generic nodes need neither label nor a pairing ceremony.

Central policy for **new requests**, in precedence order:

1. An exact directed `block` pair denies, including an explicit `allow` pair.
2. An exact directed `allow` pair permits (including across Networks).
3. Other peers in the same Network are permitted; cross-Network routing is denied.

Pairs are `source:destination` node IDs, not network names, wildcard roles or client
ACLs. The caller itself is excluded from the default peer set; explicit self-allow
is possible. Replies use the original connection-bound capability and need no
reverse initiation permission. `allow` and `block` may be omitted. Edit the private
config and restart the owned router to change admission or policy; clients cannot
change their own membership/rules.

IDs and Network names are 1–128 ASCII letters, digits, `_` or `-`; tokens must be
distinct 32–256-character ASCII strings. Up to 128 nodes are supported. An active
identity cannot be displaced by reconnecting. Invalid/mixed configuration fails
clearly before starting the listener.

Serve publishes mode-0600 records **after binding**:

- `<endpoint-dir>/server.json`: listener/owner metadata, without participant tokens.
- `<endpoint-dir>/participants/<id>.json`: that node's credential, Network and URL.
  The `participants` directory and wire `participant` field are retained to keep
  actual clients/endpoint selection interoperable; neither limits nodes to agents.

The historical state default remains `.agents/var/tools/agent-router/`, with
configuration in `config.json` and endpoint records in `endpoints/`; the rename
neither migrates data nor creates a second configuration. `AUTOMATA_MESSAGE_ROUTER_STATE`
selects another default root; `AUTOMATA_AGENT_ROUTER_STATE` remains a fallback.
Explicit CLI paths override either. Each shutdown removes only its own records,
not configuration. Stale records require ownership inspection before removal.
A fresh setup does not depend on retained operational data.

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

## Optional persistent browser pairing

`serve --auth-dir <private-0700-directory>` enables same-process local pairing.
Browsers can request a five-minute pairing locator without knowing a Page ID.
Explicit user instruction authorizes private `approve-request` for an existing
configured page; only the high-entropy requester binding can claim the session.
Manual approval checks never connect. Private `pair` remains a code fallback;
`revoke` manages established sessions. `/session/ws` uses a persistent HttpOnly
cookie without a permanent client token. Reconnect, service restart and agent binding remain explicit; saved
requests and reply capabilities never replay. Auth paths are excluded from public
roots. See [local session setup, API, revocation and limits](docs/local-session.md).
Plain HTTP cookies are not Secure or port-isolated; same-origin scripts and
same-user local processes remain outside this security boundary.

## Browser / Node client

For an active agent using ordinary process tools, see the installed
[task-local Node request/reply recipe](docs/node-client.md). It reuses this client,
not a new service, and does not wake an idle model.

Import `createMessageRouterClient` from `browser/client.js` (or `/assets/client.js`
when served here). Provide the intended participant's credential out of band;
never embed credentials in public assets or fetch private endpoint files through
the static server. Do not give a page an agent's credential or the master config.

```js
const client = createMessageRouterClient({
  onMessage: async message => {
    render(message.payload); // component-owned handling, not routing policy
    if (message.expectReply) await client.respond(message.id, {handled: true});
  },
  onResponse: response => showResponse(response),
});
await client.connect(credentials); // wsUrl, participant, token; node sessionId optional
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
`status()` lists only destinations permitted by the same central policy used for
routing, including their Network and current presence. Blocked nodes are absent,
not revealed as offline. v2 config adds authenticated `network` to hello/status and
sender provenance; generic sender kind is `node`. Node `sessionId` is optional;
`agent` requires it and `page` forbids it. These are adapter contracts, not ACLs.
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

Install the `message-router` Pi extension bundle. `message_router` is the primary
tool; `agent_router` and `agent_browser_bridge` remain compatibility aliases sharing
one adapter and binding. Only the primary name is exposed by default; explicitly
selected compatibility-only tool sets remain supported.

- `open`: optional `endpoint` selects a private **node or agent** credential file. Defaults
  to `AUTOMATA_MESSAGE_ROUTER_ENDPOINT`, then `AUTOMATA_AGENT_ROUTER_ENDPOINT`, then
  the historical `.agents/var/tools/agent-router/endpoints/participants/agent.json`.
  A failed explicit selection never falls back to another credential.
  It binds the current Pi session (including for a generic node), not a caller-
  supplied session; it never starts a server or another agent. Page credentials
  cannot be opened by Pi.
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

`browser/pi-client.js` exports `createMessageRouterChatClient({to,onMessage,onState,
onDelivery})`. Connect with the **page** credential, or explicit `connectSession` after local
pairing; `status()` still returns only granted destinations. It retains `sendMessage`,
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

- Canonical tool/skill/extension names are `message-router`, `automata-message-router`,
  and `message-router/` respectively; CLI entry is `message_router.py`. The installer
  supports Pi's native `index.ts` bundles as well as existing single-file extensions.
- Do not load `agent-router/` or the older `agent-browser-bridge.ts` alongside the
  new extension: they register overlapping tool names. During an authorized sync,
  inspect local changes, retire old installed packages, install the renamed ones,
  then reload Pi or start a fresh session. Installers do not uninstall old names.
  Reload discards in-memory bindings and pending context; do not replay messages.
- Existing config `{v:1,participants:{id:{kind,token,allow:[ids]}}}` remains supported
  with **only its original explicit grants**, not same-Network defaults. No automatic
  migration, rotation or widening occurs. To opt into v2, deliberately move entries
  to `nodes`, retain tokens and adapter kinds, choose Network assignments, and
  review allowed defaults plus directed `allow`/`block` pairs. Do not merely change
  `v`: mixed/old per-node `allow` fields are rejected. Preserve an explicit-only
  topology by assigning each node its own Network and translating its old grants
  into central `allow` pairs. Restart explicitly after reviewing the result.
- Existing browser imports `createAgentRouterClient` and `createAgentRouterChatClient`
  remain aliases of the renamed exports. Wire version 2, `participant` fields,
  credential paths and state locations are retained. Generic-node consumers need
  the updated client/Pi adapter accepting kind `node`; old page/agent clients may
  retain their labels. New `setup` emits v2, with generic `node` rather than the old
  implicit page/agent pair. Provision those adapters explicitly when required.
  Saved recipes may still live under the old owner name; update command paths when
  revalidating them, without moving or deleting their data merely for this rename.
- Existing v1 browser clients can use the explicitly selected `legacy-serve`
  command or the bundled `agent_browser_bridge.py serve` entry. See [LEGACY.md](LEGACY.md).
  They cannot speak v2 merely by changing their URL; upgrade credentials/client
  together. The v1 adapter does not gain multiparty routing.
- Python responsibilities: `config.py` validates admission and compiles central
  policy, `protocol.py` validates JSON, `router.py` owns routing,
  `server.py` owns ASGI/static boundaries and the shared socket loop, `cli.py` owns
  process/endpoint lifecycle, `auth_store.py`/`auth.py` own opt-in private session
  state and same-origin/operator admission; `auth_requests.py` owns volatile request
  states/budgets/exclusive claims and `auth_request_http.py` strict request packets.
  `auth_socket.py` owns session-bound
  output/supervision/retirement, `legacy.py` owns v1 single-pair behavior. Pi transport and context/admission live
  in separate extension modules. No application payload is executed by the router.

Authorized connectivity is not permission to delegate work or execute peer-supplied
instructions. Distinguish connection, forwarding, Pi admission, reply emission and
component handling; none imply the next outcome automatically.
