# Pi NodalWire custom messaging

Opt-in trusted-local messaging between Pi sessions or external byte clients.
This integration mirrors **`pi.sendMessage(message, options)`**, not native Pi RPC.
There are no user messages, UI-only notifications, delivery presets, task manager,
authentication subsystem, automatic replies, acknowledgement packets or retries.

## Preparation

Requires Node24, Pi's TypeScript extension support, pinned **Edictor0.4.0** and
`@devcapsule/nodalwire-client`0.1.0 (native zeromq), plus a separately running relay.
Nothing is installed or started automatically. Copy to an authorized location:

```sh
uv run automata pi-extension install --extension nodalwire --target-root /chosen/extensions
cd /chosen/extensions/nodalwire
npm ci --ignore-scripts --legacy-peer-deps --no-audit --no-fund
# Only when native build preparation is authorized:
npm rebuild zeromq
```

The lock pins application/transitive packages. `--legacy-peer-deps` avoids
installing another Pi host; Pi supplies its own host libraries. Edictor is pure
CommonJS and is loaded through Node's `createRequire`; its documented named ESM
imports do not work with native Node24. Edictor is needed when the extension loads;
the native transport client remains lazily imported only on connect. Native
binaries must match the local platform. Replacing a directory copy excludes its
node_modules; prepare dependencies again. Global installation is a separate action.

Use the published Python `nodalwire` relay in its prepared environment. Configure
admission/routes deliberately; do not restart or change a shared relay implicitly.
Node clients use loopback TCP only. Names and routing policies are cooperative
labels, **not authentication or encryption**. Connect only trusted local peers.

## Connection

```sh
pi -e /chosen/extensions/nodalwire/index.ts \
  --nodalwire-name reviewer \
  --nodalwire-endpoint tcp://127.0.0.1:5555
```

Omitting `--nodalwire-name` leaves it disconnected. Loading does not start a relay,
model run, watcher or socket. Endpoint defaults to `tcp://127.0.0.1:5555`.

Operator commands:

```text
/nodalwire connect --name reviewer [endpoint]
/nodalwire status
/nodalwire disconnect
```

Endpoint may precede or follow `--name`; unknown/duplicate flags, missing names or
multiple endpoints are rejected without replacing the existing connection.

If Pi starts with an explicit `--tools` selection, include `nodalwire_connection`
and `nodalwire_send` when the agent needs them. A connected extension does not
prove its model-callable tools are exposed. Read-only reviewers can instead use
an explicitly authorized prepared client for a bounded callback.

Model tool `nodalwire_connection` takes `{action:"status"|"connect"|"disconnect",
name?,endpoint?}`. Only connect accepts name/endpoint; name is required. An exact
active route is reused; changing it requires explicit disconnect first. Concurrent
connects are rejected; cancellation/shutdown closes late client results. Startup
failure leaves Pi disconnected and usable. No automatic reconnect or replay.

## Send

```json
{
  "to": "coordinator",
  "message": {
    "content": "Review complete.",
    "display": true,
    "details": {"report": "review.md"}
  },
  "options": {"deliverAs": "followUp", "triggerTurn": true}
}
```

Pass this object to `nodalwire_send`. `to`, `message.content` and `message.display`
are required; details/options and each option member are optional. `content` is a
string or an array of Pi text/image blocks. Images are inline base64, never file
paths or remote URLs. `details` can be bounded JSON, including null/scalars/arrays.
`display:false` hides the custom message in TUI; it does not remove model context.

The receiver supplies customType `automata-pi-nodalwire`. It prefixes string
content, or prepends a text block to array content, with the actual transport
sender/recipient. Local details contain sender, recipient and an internal delivery
ticket; peer details are nested under `peerDetails`, never merged over provenance.
The ticket is local accounting, not a wire message ID or delivery guarantee.

### Native options, not presets

Options pass through unchanged, including absence. Consult installed Pi docs/API
for the supported runtime. Observed Pi1.4.0 behavior:

| Options | Busy session | Idle session |
|---|---|---|
| Omitted | Steering queue | Append without starting a run |
| triggerTurn:true, deliverAs:steer (or omitted) | Steering queue | Start a run |
| triggerTurn:true, deliverAs:followUp | Follow-up queue | Start a run |
| triggerTurn:false, deliverAs other than nextTurn | Append after current tool results | Append without starting a run |
| deliverAs:nextTurn, regardless of triggerTurn | Hold for a future separately started run | Same; no immediate display/wake |

All reachable peers may steer; there is no additional sender allowlist. Steering
is not cancellation: it does not stop an already-running tool. Message content
and sender labels grant no additional task authority. Custom content eventually
enters model context; it is not a sandbox.

## Version-2 wire schema

External clients send UTF-8 JSON bytes shaped exactly as:

```json
{
  "version": 2,
  "message": {"content": "Review complete.", "display": true},
  "options": {"deliverAs": "followUp", "triggerTurn": true}
}
```

`protocol.ts` contains the executable **Edictor Model/defineField schema**, shared
by encode/decode. It defines text/image blocks, Message, Options and Envelope.
Use `encodeMessage(message, options?)` / `decodeMessage(bytes)` or equivalent
validation. The wrapper additionally checks own fields against Edictor's public
schema: Edictor strict mode alone admits inherited Object names such as __proto__.
No second handwritten field list is maintained.

Unknown fields, versions, options, malformed UTF-8/JSON and invalid content are
rejected. There is no role, customType, sender, type discriminator, acknowledgement,
RPC command or mandatory ID. Native options are not rewritten or constrained into
new combinations. Version1 `{version:1,type:"message",text}` packets are rejected,
not silently converted; upgrade both endpoints explicitly. The old `text` send-tool
argument is likewise replaced by the structured message/options interface.

### Explicit bounds

- Entire encoded envelope: **64KiB**, checked before UTF-8/JSON parsing.
- Each content string/text/image-data field: **48KiB UTF-8**; optional text signatures
  use the same limit. Image data must be nonempty padded base64 and MIME image/*.
- At most **64 content blocks**; an image MIME string is at most128bytes.
- Peer details: **8KiB encoded JSON**, depth16 and at most2048 visited values.
- Aggregate limits still apply: multiple individually valid fields may exceed64KiB.
- No fragmentation, truncation, remote image fetch or promise of large image support.
  Structural image validation is not proof that a provider will decode an image.

At most **32 unobserved Pi submissions per loaded extension instance** are admitted.
Native `message_end` observations release their local tickets. Receiving continues
while Pi is busy, so a queued follow-up does not hold later steering behind a
settlement wait. Over-capacity packets are dropped locally, without ACK/retry;
client/native queues retain their own bounded backpressure. Invalid-input warnings
are generic, payload-free and limited to once per second.

This is not a total Pi history/context/disk bound. Reconnection does not reset
outstanding tickets. Already submitted native Pi messages cannot be recalled by
disconnect; a reload creates new instance accounting and does not provide a global
pending-queue guarantee across extension instances. Session shutdown/reload closes
the owned transport; it does not claim removal of already accepted Pi messages.

## Outcomes and cleanup

Sending success confirms **relay queue acceptance only**, not receiver validation,
Pi insertion, model processing or task success. Invalid/over-capacity packets are
reported locally; no rejection reply is sent. Timeouts/cancellation can occur after
forwarding, so do not blindly retry consequential messages. No discovery/broadcast.

There is no automatic reply, event mirroring, task-success classification, worker
shutdown or lifecycle decision. Explicit disconnect and session shutdown/reload
close the owned connection idempotently. Failure of a release receipt means local
closure, not proof that the relay released its name; a lease may remain.

## Verification

Prepare dependencies in an isolated copy, then point the wrapper at its modules:

```sh
NODALWIRE_TEST_NODE_MODULES=/prepared/copy/node_modules \
  python -m pytest tests/integration/automata/extensions/nodalwire_test.py -q
```

`PI_TEST_PACKAGE_ROOT` selects an installed Pi package; prerequisites otherwise
skip explicitly. Tests use fake transport and execute the installed Pi message
method with inert collaborators for option-branch comparisons. They do not start
models or prove full live-runtime timing, network delivery, security or production
readiness. Package/installer tests check copied schema/manifests and no generated
dependency trees. The optional `nodalwire_live_trial.py` uses real model inference
and must be separately authorized; adapting its v2 payloads is not a trial result.
