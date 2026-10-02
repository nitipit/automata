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
is launched by the builder. First use opens **disconnected**. Chat dominates the
page; the header shows the explicit target and transport state. Connect opens a
native modal with one primary next action for browser approval or connection.
The selected agent is prominent; its editable ID and private-code fallback live
under Advanced. Page ID remains a compact, visible, read-only secondary row. Tools contains
Save/Restore, component contracts, draft safety notes and clearly labelled Demo
choices. Demo replies are **local, not live**; try “form” or “json”. Demo Form also
switches to local mode before adding its example, so it cannot submit to a live
agent. All content is ps-text/ps-json/ps-form through the generic component path,
never HTML execution.

## Optional live connection

The builder copies maintained Router browser modules into `router/` with the
starter; use `--router-source <message-router-tool>` for non-sibling inputs. It
also publishes `catalog.json` with registry-derived source links and admitted
examples, without credentials or actual user state.

For persistent browser pairing, the operator explicitly starts the existing local
Router with `--auth-dir <private-directory>`. Open Connect and click **Start
pairing**, then **Copy message to send agent**. Send the visible `Please approve
pairing RP-…` message to the agent to request approval for an existing configured
page using private `approve-request`. Copy never sends anything; if clipboard
access fails, select and copy the visible message manually. You need neither a
Page ID nor a private code. Click **Check approval** to claim the approved pairing,
then **Connect to <agent>** separately. A known-approved but unclaimed request
makes Check approval primary instead of asking the agent again. **Choose agent**
opens Advanced when the target is missing/invalid. Once connected, **Done** only
dismisses the dialog. The existing `pair` command and private-code form remain a
secondary fallback under Advanced.
A paired browser shows its session status instead of the pairing controls. A separate readonly
Page ID row displays only the authenticated server status participant; otherwise
it reads “Not approved yet”. This identifies the browser page, not the editable
Agent target, and is never guessed from target/preferences. Startup only checks auth
status; it never opens a socket or starts/binds an agent. A restored valid cookie
allows explicit reconnect after service/browser restart; native agent bindings
must still be established explicitly. No events/requests/reply capabilities replay.
An offline agent presence snapshot is informational, not a stale send gate; after
it binds, only a new explicit send is attempted.

Pairing requests last five minutes, with bounded server state and **no background
polling**. Every check/claim is explicit; each fetch times out after five seconds
without promising rollback. Double clicks reuse the pending binding. Refresh
restores its display from the dedicated `automata-router-request-v1` sessionStorage
entry, not from drafts. The 256-bit short-lived requester capability is never the
public locator and never enters snapshots, URLs or logs. Tabs may share cookies or
clone sessionStorage; no tab-isolation claim is made. Unavailable transient storage
blocks request creation without disabling private-code pairing.

**Cancel pairing request** cancels that exact server request. Dialog Close/Done/Escape
only dismiss and fence pending UI work. Approval chooses an existing configured
page and cannot replace a connected peer, unexpired page session or reservation.
An incoming cookie for any already-paired page must have its approval explicitly removed before
claiming another page. The UI checks existing session status before claiming.

Requests do not survive Router restart. Expired/cancelled requests offer **Start
new pairing**, requiring fresh operator approval. Service/storage uncertainty or
a redeemed request without a cookie offers **Check session status** and operator
repair guidance, not another claim or a confident new-request instruction. The
request client retains its bounded binding; the UI never automatically retries.
For a lost claim response, **Check session status** recovers a delivered cookie.
If the server committed a session without delivering the cookie, ask the operator
to explicitly revoke the orphaned page session before a fresh request; claiming
again never reissues the cookie. No automatic retry, claim, connection or work replay.

The last validated target ID is saved only when Connect is explicitly clicked,
under a directory-scoped `automata-playspace-chat-target-v1` localStorage preference,
separate from draft snapshots. A new page restores that input only, never selects
from presence, opens a socket or sends. No code, cookie or token enters this
storage. Malformed/blocked storage retains the current input and shows a limitation;
select the target again after restart if it could not be saved.

Close, Done and Escape fence pending Pair/Connect results. Closing retires an
opening connection, but keeps an already-established transport; it is not a hidden
Disconnect. Pair requests already submitted can still finish setting the cookie,
but never chain a Connect; reopening checks status. A stale completion cannot clear
a newer pairing code or release a newer pending action. Target edits cancel pending
Connect and retire the old live binding, so sends cannot silently use the old agent.
Pending requests are interrupted/uncertain, not replayed or proof of undo.
Native modal focus returns to the header trigger. If paired status arrives while
a pairing control owns focus, focus moves to the next enabled primary action (or
focusable status while busy), never a collapsed Advanced field. Unaffected focus
is retained. Current Close also fences pending
cache Restore without disconnecting an established transport. External native
closes retire opening activity synchronously through dialog `beforetoggle`;
queued `close` notifications never cancel/refocus a newer explicit intent. This
requires a browser supporting native dialog `beforetoggle` (verified on the parent
preview's Chrome); older-browser lifecycle acceptance is not claimed. Tools closes
on actions or Escape; safety explanations remain discoverable in details.

Disconnect keeps approval and local drafts. **Remove browser approval** is a
separate destructive action under Advanced: it revokes that cookie session,
clears it and disconnects without erasing drafts. After confirmed revocation, a
terminal requester binding is cleared locally so a fresh pairing can be requested. Codes and permanent
Router tokens never enter snapshots. Authenticated, offline/expired and failures
are visible separately from transport/agent admission. Cookie auth requires the
exact local HTTP `127.0.0.1:<port>` origin. HttpOnly/SameSite=Strict is not Secure
over HTTP or isolation between ports; same-user processes and same-origin scripts
are not sandboxed. See the Router tool's `docs/local-session.md` for private
lifecycle, revocation, storage and limitations.

For an existing authorized **direct-token** integration only (not UI fallback),
after an authorized credential and explicit agent participant are established,
trusted page setup can call `window.playspaceChat.connect(credentials, to)`.
The validated explicit target is reflected in the header/input without saving a
preference; only the UI Connect action saves that preference. Credentials follow the client's `{wsUrl,participant,token,sessionId?}` contract;
never put tokens in URLs/public files/cache/logs. The helper only connects. A user
must explicitly Send or submit a Form. An optional trusted `createClient` factory
may replace dynamic import. Components and events route as complete distinct
payloads, not history wrappers. The page does not redefine their validators.

## Composer

The Playspace Chat textarea grows with typing/paste and restored drafts up to
30vh, then scrolls internally. Deletion, sent-draft clearing, rejection restoration
and native form reset remeasure it; newer unsent edits are preserved. Native
textarea keyboard behavior is unchanged. Width/viewport changes remeasure wrapping;
height-only observer notifications are ignored, and disposal releases resources.
The starter keeps an initially compact composer. DOM-fake tests verify lifecycle
and values, not real wrapping/overflow; browser acceptance must measure those.

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
