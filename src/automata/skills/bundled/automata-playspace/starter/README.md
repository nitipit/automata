# Playspace Chat starter

Optional thin **JavaScript** composition of the maintained Playspace components.
See [../README.md](../README.md) for TypeScript source ownership, component/event
contracts, APIs, runtime validation, build path and focused checks. The starter
owns page layout, routing and persistence wiring, not component schemas.

Build/copy public assets with:

```sh
python <playspace-skill>/scripts/build.py --runtime-root "$PUBLIC" --validate
```

Serve only that public-safe root on an owned loopback origin. No browser/server
is launched by the builder. Open `index.html` and try “form” or “json”. All content
is ps-text/ps-json/ps-form through the generic component path, never HTML execution.
Sample agent mode is visibly **local, not live**, and sends nothing remotely.

## Optional live connection

The builder copies maintained Router browser modules into `router/` with the
starter; use `--router-source <message-router-tool>` for non-sibling inputs. It
also publishes `catalog.json` with registry-derived source links and admitted
examples, without credentials or actual user state.

For persistent browser pairing, the operator explicitly starts the existing local
Router with `--auth-dir <private-directory>` and privately provisions a single-use
code with its `pair` command. Enter the code into Pair browser, select an explicit
target participant ID, then click Connect paired session. Startup only checks auth
status; it never opens a socket or starts/binds an agent. A restored valid cookie
allows explicit reconnect after service/browser restart; native agent bindings
must still be established explicitly. No events/requests/reply capabilities replay.
An offline agent presence snapshot is informational, not a stale send gate; after
it binds, only a new explicit send is attempted.

The last validated target ID is saved only when Connect is explicitly clicked,
under a directory-scoped `automata-playspace-chat-target-v1` localStorage preference,
separate from draft snapshots. A new page restores that input only, never selects
from presence, opens a socket or sends. No code, cookie or token enters this
storage. Malformed/blocked storage retains the current input and shows a limitation;
select the target again after restart if it could not be saved.

Disconnect keeps pairing and local drafts. Forget pairing revokes that cookie
session, clears it and disconnects without erasing drafts. Codes and permanent
Router tokens never enter snapshots. Authenticated, offline/expired and failures
are visible separately from transport/agent admission. Cookie auth requires the
exact local HTTP `127.0.0.1:<port>` origin. HttpOnly/SameSite=Strict is not Secure
over HTTP or isolation between ports; same-user processes and same-origin scripts
are not sandboxed. See the Router tool's `docs/local-session.md` for private
lifecycle, revocation, storage and limitations.

For an existing authorized **direct-token** integration only (not UI fallback),
after an authorized credential and explicit agent participant are established,
trusted page setup can call `window.playspaceChat.connect(credentials, to)`.
Credentials follow the client's `{wsUrl,participant,token,sessionId?}` contract;
never put tokens in URLs/public files/cache/logs. The helper only connects. A user
must explicitly Send or submit a Form. An optional trusted `createClient` factory
may replace dynamic import. Components and events route as complete distinct
payloads, not history wrappers. The page does not redefine their validators.

## Recovery

The starter envelope is `{version:2,mode:'sample'|'live',chat:ChatSnapshotV2}`.
Cache namespace is **automata-playspace-chat-v2**, same-origin directory-local key
**__playspace_chat_snapshot_v2__**. The old v1 namespace/key remain untouched;
there is no migration/import or silent deletion. The page visibly labels v2 and
old cache not imported. The coordinator should preserve an open v1 draft before
an authorized upgrade/reload.

Writes are ordered for this page; `save()` resolves after the write. Await it
before claiming persistence. One writer per key: Cache Storage is not a multi-tab
transaction service. Failed storage/malformed restoration preserve current drafts
and cache. Refresh restores history, composer, Form drafts/readonly submissions,
and separate inert event records; events and pending requests **never replay**.
Live mode restores disconnected with no credentials or reply capabilities. Local
sample mode can be selected/recovered without a remote connection.

History is display-only, not model context. Cache is exact-origin/profile scoped,
disposable, not a backup; eviction/site-data clearing/origin/profile changes can
lose drafts. Do not enter secrets. Refresh recovery is not proof of browser-restart
recovery.

`window.playspaceChat` exposes trusted composition/testing helpers: chat, contracts,
snapshot, save, restore, connect and dispose. Call `dispose()` before retiring the
page; replacement generations ignore stale sample/live replies. Retirement does
not authorize clearing browser data or deleting task evidence.
