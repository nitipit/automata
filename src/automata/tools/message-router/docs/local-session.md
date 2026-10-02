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
