# Pi NodalWire messaging

Exchange Pi custom messages with **explicitly known trusted-local peers** through
an approved NodalWire relay. This is peer messaging, not worker management or RPC.

## Prepare and connect

Requires Node **24**, Edictor **0.4.0**, `@devcapsule/nodalwire-client` **0.3.0**
(native ZeroMQ), and a matching NodalWire **0.3.0 relay** (Python **3.12+**).
Edictor loads with the extension; transport loads on connect. Nothing installs
or starts automatically. Pi **1.5.2** loader/native routing is covered by the
repository tests; that is not a full CLI/model-backed timing guarantee.

For an authorized installation into a chosen extension directory:

```sh
automata pi-extension install --extension nodalwire --target-root /chosen/extensions
cd /chosen/extensions/nodalwire
npm ci --ignore-scripts --legacy-peer-deps --no-audit --no-fund
npm rebuild zeromq  # native preparation requires authorization
```

Replacement excludes `node_modules`; prepare dependencies again. Pi supplies its
host libraries. Load with `pi -e /chosen/extensions/nodalwire/index.ts`. It remains
disconnected unless startup `--nodalwire-name <unique-name>` is supplied. After an
SDK upgrade, start a **fresh Pi process**: `/reload` can retain imported native
modules. Upgrade all messaging peers and relay together; NWM3 cannot mix with AR2.
Config version 2 and separate authenticated NA1 administration remain unchanged.

Call `nodalwire_connection` with `{"action":"connect","name":"unique-name"}`;
optional `endpoint` defaults to `tcp://127.0.0.1:5555`. Use an approved loopback
route. `status` inspects; `disconnect` closes. Disconnect before changing an active
route. Operator equivalent: `/nodalwire connect --name <name> [endpoint]`,
`/nodalwire status`, `/nodalwire disconnect`. Explicit tool allowlists must include
the needed `nodalwire_*` tools. No relay discovery, startup or administration is added.

## Networks and credentials

An **open default** autojoins. Every named network, even open, and a protected
default require `nodalwire_network` with `{"action":"join","network":"team"}`.
A connected client may have no memberships. Joining never selects a send network:
pass `network` explicitly to send/request; omission always means literal `default`.
`{"action":"leave","network":"team"}` invalidates local reply references for that
network, not accepted traffic. Receipts describe an instant, not future membership.

For protected joins, an operator supplies `--nodalwire-credentials /approved/aliases.json`:

```json
{"aliases":{"team-access":{"endpoint":"tcp://127.0.0.1:5555","network":"team","env":"NW_TEAM_JOIN"}}}
```

The operator supplies the referenced environment value privately. The alias file
contains **references, not credentials**; it must be a regular non-symlink file,
owned by the current user and not group/world-writable on POSIX (0600 recommended).
Join with `credentialRef:"team-access"`; endpoint/network must match exactly.
Never put credentials, arbitrary paths or environment-variable names in tool
arguments. Missing/invalid references fail without a credentialless fallback.
No shell resolver or credential persistence. Same-user code is not sandboxed;
JavaScript strings cannot guarantee secure erasure. See [safety.ts](safety.ts).

## Send, request and reply

```json
{"to":"known-peer","network":"team","message":{"content":"Review complete.","display":true},"options":{"deliverAs":"followUp","triggerTurn":true}}
```

Use that shape with `nodalwire_send`. `message` mirrors `pi.sendMessage`: required
text or inline text/image blocks and `display`, optional bounded JSON `details`.
Images are base64, not paths/URLs. Success returns native `id` after **relay
acceptance**, not receiver validation, receipt, action or durability.

`nodalwire_request` uses the same fields plus optional `timeoutSeconds` (default 30,
integer 1–120; at most 4 in flight). Use short queries, not long assignments. Content
should explicitly ask for a native reply: request intent is not inferred from IDs.
The receiver sees native provenance and an opaque `replyRef` in its content prefix.
Call `nodalwire_reply` with `{"replyRef":"<issued-reference>","message":{"content":"Done.","display":true}}`.
It fixes recipient/network/correlation; routing overrides are rejected.
References are single-use, expire after 5 minutes, clear on disconnect and are bounded
at 128; at capacity messages still arrive without a reference. Encoding/pre-abort
failures do not consume one; dispatch consumes it even on uncertain failure.
See [reply-references.ts](reply-references.ts) for exact lifecycle rules.

SDK correlation matches sender/network/reply_to; it is not identity authentication.
Matched replies return through the request tool only, not duplicate Pi messages.
Tool content is bounded to 50 KiB aggregate with explicit truncation; the original
reply remains in tool result details. Text is truncated on character boundaries,
and image blocks are omitted whole rather than corrupted. Invalid matched v2 replies fail safely. Unmatched/late valid replies remain ordinary
messages and may wake the receiver. Timeouts/cancellation can follow real delivery
or action: **no ACK, retry, replay or automatic reconnect**. Inspect uncertain
consequential effects before repeating.

## Pi delivery and limits

| Options | Busy receiver | Idle receiver |
| --- | --- | --- |
| Omitted | Steering queue | Append; no wake |
| `triggerTurn:true` | Steering, or requested follow-up | Wake a run |
| `triggerTurn:false` | Append after tool results | Append; no wake |
| `deliverAs:"nextTurn"` | Defer | Defer; never wake |

Options are not rewritten. A non-waking/nextTurn request can time out while its
recipient has not run. `display:false` is not model-context privacy. Names are
routing labels, not authentication; reachable peers can steer and messages grant
no authority. This bridge supplies no user messages or UI-only notifications.

Application envelope **v2** is unchanged by NWM3. Native `id/network/reply_to` stays
outside that envelope; receiver provenance is separate from peer details. Bounds:
packet 64 KiB, content fields 48 KiB, details 8 KiB, and 32 unobserved Pi submissions per
instance. Reconnect does not reset that allowance or the in-flight request cap.
Disconnect closes owned transport, not already submitted Pi messages; unconfirmed
release may leave a name leased. Wire schema: [protocol.ts](protocol.ts); core
routing and tool contracts: [index.ts](index.ts).

## Verification

Offline: `python -m pytest tests/unit/automata/extensions tests/integration/automata/extensions/extension_test.py -k nodalwire`
with prepared Edictor/typebox via `PI_EXTENSION_TEST_NODE_MODULES` and installed Pi
via `PI_TEST_PACKAGE_ROOT`. Opt-in `tests/integration/automata/extensions/nodalwire_live_trial.py`
uses current repository source, published 0.3.0 transport, an explicit expected Pi
version and owned ephemeral relays. It covers membership, metadata, request/reply,
uncertainty and cleanup with inert run/queue collaborators; no provider/model call.
Read its help for required prepared paths. Testing does not authorize deployment.
