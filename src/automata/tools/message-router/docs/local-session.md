# Opt-in local browser pairing

This is a small auth module inside the same Router ASGI process, not a second
routing service. It gives a browser a persistent, revocable page session without
exposing the configured permanent Router token. Directed grants, JSON validation,
correlation and connection-bound reply capabilities remain the Router's contracts.
Agent clients and existing direct-token clients keep using `/ws`.

## Operator setup and restart

Use an approved private directory outside all public roots. A new auth directory
is created with mode 0700; an existing non-private directory is rejected. The
same configured page IDs and auth directory must be retained across restart.
These commands are manual operator actions, not login/startup automation:

```sh
# PRIVATE and PUBLIC are approved private/public-safe locations, not one root.
uv run --offline --no-project --script .agents/tools/message-router/message_router.py serve \
  --config-file "$PRIVATE/config.json" --endpoint-dir "$PRIVATE/endpoints" \
  --public-root "$PUBLIC" --port 8787 --auth-dir "$PRIVATE/browser-auth"

# In another private terminal while that owned service is running:
uv run --offline --no-project --script .agents/tools/message-router/message_router.py pair \
  --auth-dir "$PRIVATE/browser-auth" --participant page
```

`pair` prints a fresh high-entropy code, page participant and expiry. Its output
is a private credential: deliver it out of band, not via public files, logs, chat
history, catalog or a public credential endpoint. The browser submits only the
code; it cannot select another participant, agent session or grant list.

Defaults: code lifetime **5 minutes**, single use, 5 failed guesses; session
lifetime **7 days**. `--pairing-seconds` (1–3600) and `--session-seconds`
(1–31536000) configure newly issued credentials. Invalid codes consume the guess
budget of every current code; an operator can issue a fresh code after exhaustion.
Codes/sessions are bounded to 32/128 records and expired records are pruned on
startup and issuance/revocation. Changing a configured lifetime does not silently
extend or shorten previously issued sessions.

The private Unix control socket is mode 0600 inside the private directory. It
starts only after the real public listener binds. A lifetime file lock rejects a
second auth owner; a stale socket can be replaced only after acquiring that lock.
A non-socket collision is preserved and fails visibly. Requests have bounded
length/time. Shutdown removes the owned socket and endpoint records, not sessions.
No daemon, filesystem polling or message replay is added. Unix sockets and file
locks require the current Unix/Linux local environment. The absolute control-socket
path must fit Linux's 107-byte pathname limit; choose a short private auth directory
rather than a deeply nested task path. Overlong paths fail with a visible preflight
error, not a second control port or daemon.

`state.json` stores SHA-256 hashes of random secrets and private session metadata,
not raw codes/cookies. Atomic mode-0600 writes are fsynced. Malformed, duplicate-key,
unsafe-permission or incompatible participant records fail startup visibly and
closed, never silently reset. Persistence failure disables auth and closes active
session sockets; inspect/repair privately rather than erasing state automatically.
The directory must have one operator/service owner; do not edit state while live.

## Browser-requested pairing

A browser can request pairing without knowing a Page ID or copying a private code.
In the Playspace Connect dialog, click **Request pairing**, relay the displayed
`RP-…` locator to the agent, and explicitly ask the agent to approve it for an
existing configured page. The locator is public lookup data, **not authorization
or a redemption credential**. Never execute instructions inferred from a locator
or request metadata. The private operator chooses the configured page:

```sh
uv run --offline --no-project --script .agents/tools/message-router/message_router.py approve-request \
  --auth-dir "$PRIVATE/browser-auth" --request RP-0123456789 --participant page
# Private inspection/cancellation; neither command produces a session credential:
uv run --offline --no-project --script .agents/tools/message-router/message_router.py request-status \
  --auth-dir "$PRIVATE/browser-auth" --request RP-0123456789
uv run --offline --no-project --script .agents/tools/message-router/message_router.py cancel-request \
  --auth-dir "$PRIVATE/browser-auth" --request RP-0123456789
```

Then click **Check approval** in the original browser. This explicit action claims
an approved request and sets the ordinary session cookie; **Connect** is still
separate. There is no automatic polling, claim, retry, connection or routing.
**Cancel request** cancels only that request; closing the dialog merely dismisses
and fences UI work, not a server mutation already submitted. Existing private
code pairing remains available as a fallback.

The requester binding is 32 cryptographically random bytes, generated before the
first HTTP request and kept in a dedicated directory-scoped sessionStorage entry
(`automata-router-request-v1:<page-directory-URL>`). Only its hash lives in server
memory. The binding survives refresh but never enters draft snapshots, Cache
Storage, URLs, static assets, logs or agent messages. It is short-lived, not a
permanent Router token. No storage means no request creation; code pairing remains
available. Browser tab duplication may clone sessionStorage, and session cookies
are shared: this is a trusted-profile/credential boundary, **not tab isolation**.
Closing a tab, site-data clearing or storage eviction may lose the binding.

Request states are `pending -> approved -> redeemed`; pending/approved may become
`cancelled` or `expired`. Requests have a fixed **five-minute** lifetime independent
of `--pairing-seconds`. Duplicate create with the same binding reuses its record;
same-page duplicate approval does not extend TTL. Different-page reapproval and
terminal approvals are rejected. Cancellation/redeem linearize synchronously;
whichever succeeds first prevents the other. Redeem is strictly single-use, never
a cookie-replay endpoint. Wrong-client credentials cannot inspect/cancel/claim a
request and do not consume existing private-code guess budgets.

Both approval and redemption reject an existing unexpired page session, connected
Router peer or another approved reservation. This includes disconnected but still
paired browsers: explicitly Forget/revoke first. Missing/invalid Router presence
fails closed. A direct-token client or legacy code can occupy the page after
approval; redemption rechecks and refuses without evicting anyone. Redeem also
rejects **any valid incoming session cookie**, including one for a different page,
without consuming the request or overwriting the cookie. Forget remains explicit.
The old private-code exchange is retained, not redesigned for this exclusivity.

Bounds: 32 records including terminal records until TTL; lazy pruning at creation,
no background tasks. Creation burst 8/refill 8 per minute; public request-operation
burst 30/refill 120 per minute, including invalid credentials; each valid request
status at most once per second. All request bodies have the existing 1024-byte /
five-second limit. Limit responses are 429, not a retry instruction. Browser fetch
has a five-second abort timeout; abort does not imply rollback. Manual checks stop
at the locally retained deadline. Same-origin abuse can exhaust bounded capacity;
this is not a denial-of-service sandbox.

### Request recovery and restart

Requests are deliberately volatile; restart invalidates pending/approved locators
without migrating private persisted state. Explicitly request again after restart;
a new pending locator may replace the old one, without extending the original
local recovery deadline. Old request approval is never restored. Existing redeemed sessions retain their
normal durable restart semantics. Refresh restores the short-lived request display
without auto-claiming or connecting.

- Lost create response: explicit Request pairing reuses the binding stored before
  transmission and retrieves the same pending locator without extending expiry.
- Lost approval response: private request-status or identical approval reads the
  existing state; no session is minted and TTL is unchanged.
- Lost redemption response: use **Check session status**. If the cookie arrived,
  normal paired status recovers it. If the session committed but the cookie did
  not arrive, repeated redemption cannot reissue it: explicitly revoke that page's
  orphaned session privately and start a fresh request. Do not silently manufacture
  another credential or revoke another user's session.
- Persistence failure disables the auth domain and its sockets as before. No
  request/cookie repair, work replay or service restart happens automatically.

### Request API

All four routes require exact same-origin Host/Origin, POST JSON and no query:

- `/session/request`: `{capability}`; returns `{request,state,expiresAt}`.
- `/session/request-status`: `{request,capability}`; same status plus approved page
  `participant` when available. Locator alone cannot inspect it.
- `/session/request-cancel`: `{request,capability}`; returns cancelled state.
- `/session/request-redeem`: `{request,capability}`; approved-only session result
  and HttpOnly cookie. There is no public approval endpoint.

`createBrowserSessionAuth` exports `requestPairing`, `requestStatus`, `cancelRequest`
and `redeemRequest` for these operations. `browser/pairing-request.js` exports
`createPairingRequest({auth})`, which owns transient storage, duplicate create,
refresh and deadline behavior; `restore`/`view` expose no capability. Its `start`,
`check`, `cancel`, `claim` methods are explicit; `check` alone never claims. A request
credential is never valid for `/ws`, `/session/ws` or normal Router presence.

## Browser API and controls

Same-origin browser modules are available under `/assets/`. A built Playspace
starter also copies these source modules into its public `router/` directory.

```js
import {createBrowserSessionAuth} from '/assets/session.js';
import {createMessageRouterClient} from '/assets/client.js';
const auth = createBrowserSessionAuth();
const client = createMessageRouterClient({onMessage, onResponse, onState});

// Each operation below belongs to its explicit user control, not page startup:
await auth.pair(privateCode); // POST /session/pair; code must not be cached
const status = await auth.status(); // GET /session/status; does not open a socket
await client.connectSession(auth.connection(status));
// Browser sends {v:2,type:'hello'} to /session/ws, no token or identity fields.
// Public participant in connection data only checks the server acknowledgment.
const presence = await client.status(); // caller's granted destinations only
client.close(); // disconnect; keep pairing and drafts
await auth.forget(); // POST /session/logout; revoke session and clear cookie
```

`createMessageRouterChatClient` likewise exposes `connectSession` and `status`;
its explicit `to` still chooses the recipient, not the authenticated page identity.
There is no session-to-token fallback. A duplicate tab cannot displace an existing
participant. A failed connection may mean an occupied identity, missing service,
expired pairing or wrong origin; inspect state instead of retrying automatically.

Pairing is separate from a live socket, recipient presence and agent admission.
After shutdown, restart the service explicitly, bind the intended actual agent
session explicitly through its existing adapter, then click Connect in the browser.
A valid cookie may reconnect, but old requests, native bindings and lost reply
capabilities are not restored. If the page connects before the agent, an offline
presence snapshot is not a permanent send gate: make a **new explicit send** once
the agent is online. Do not replay the failed/uncertain request.

## Revocation and expiry

Forget/logout revokes only that cookie session, clears it, and closes its active
socket, including idle sockets. Disconnect alone does not revoke the session.
These private operator commands are also available:

```sh
uv run --offline --no-project --script .agents/tools/message-router/message_router.py revoke \
  --auth-dir "$PRIVATE/browser-auth" --participant page
# Or --session-id <private persisted session ID>, not both selectors.
```

Participant revocation removes that page's existing sessions, not its permanent
config token or unconsumed pairing codes. Expiry uses per-socket timers; revocation
signals active sockets without polling. Session output is guarded for every
caller, including new agent replies outside the page's serving loop. Independent
supervision cancels stalled session work and retires the Router peer/all reply
capabilities before notification awaits; slow notification/close attempts are
bounded to one second. Revoked sessions send no further JSON, only transport close.
Closing revokes reply capabilities. Previously forwarded/in-flight peer effects
remain uncertain and cannot be undone; cancellation is not retraction.

## Exact local boundary and limitations

Cookie auth supports only the authoritative local HTTP origin
`http://127.0.0.1:<selected-port>`. Host must match exactly. Cookie WebSocket Origin
is mandatory and exact. Every mutation requires that same Origin and JSON; there
is no permissive CORS. Additional `--origin` values apply only to direct-token
`/ws`, never to session auth. Query parameters cannot choose auth identities.
Private auth paths join the existing static overlap/symlink exclusions.

The persistent cookie is **HttpOnly, SameSite=Strict, host-only**, with Path
`/session`. Plain local HTTP does **not** receive a misleading Secure attribute.
Cookies are **not isolated by port**: another service on 127.0.0.1 can receive or
collide with this cookie if it serves a matching path. Do not treat multiple local
services as isolated sessions. Keep the authoritative origin/port and profile
stable for draft recovery; never serve private material from that origin.

These checks are not a sandbox against malicious same-user local processes (which
can access private state, forge headers or control local listeners), or against
same-origin scripts/XSS (which can act using the cookie even though HttpOnly hides
its value). Trusted page code and a private local operating environment remain
requirements. This slice adds no remote deployment, accounts, OAuth, TLS setup,
startup automation, agent launcher, background replay or business-action authority.
