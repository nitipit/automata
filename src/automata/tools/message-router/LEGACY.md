# Version-one bridge compatibility

The single-pair protocol remains available through `agent_browser_bridge.py` in
the **message-router** tool, with the Pi `agent_browser_bridge` compatibility alias.
This is not multiparty routing; new integrations should use [message-router](README.md).

## Setup, status, serve

From a project containing the installed tool:

```bash
uv run --offline --no-project --script .agents/tools/message-router/agent_browser_bridge.py setup \
  --runtime-root /path/to/legacy-ui
uv run --offline --no-project --script .agents/tools/message-router/message_router.py status \
  --endpoint-file .agents/var/tools/agent-browser-bridge/endpoint.json
uv run --offline --no-project --script .agents/tools/message-router/agent_browser_bridge.py serve \
  --runtime-root /path/to/legacy-ui \
  --session-id chat \
  --port 8787
```

`--session-id` names the public static `/sessions/chat/` route; the Pi control
handshake separately binds the actual existing Pi session id. Only an explicit legacy `--runtime-root` opts into `lib/` and `sessions/` layout.
There is no implicit Adaptive UI root. `setup` never starts a server, Pi, or browser. `serve` is the only command that starts a listener. It publishes a
private endpoint record at `.agents/var/tools/agent-browser-bridge/endpoint.json`
by default and removes only its own record on shutdown.

Browser messages use `{v:1,id,kind:"message",payload}` and replies use
`{v:1,id,kind:"reply",correlationId,payload}`. `payload` may be any bounded JSON
value, including `null`; it is never projected onto transport-owned text fields.
The browser API is `sendMessage(payload)`. Payload JSON is limited to 32 KiB,
complete frames to 64 KiB, and nesting to 32 levels (root at depth zero).
Objects, arrays, strings, numbers, booleans and null are supported; an absent
payload is rejected. Numbers use JavaScript finite-number semantics; integers
outside ±(2^53−1) are rejected, and numeric formatting/negative zero are not
preserved. JSON values, not original lexical formatting or key order, are the
contract. Duplicate wire object keys, non-finite numbers, non-JSON objects,
cycles, sparse arrays and lossy extra array properties are rejected. Escaped
Unicode, including lone surrogate code units, remains JSON data. Limits apply
to compact UTF-8 serialization at each endpoint, not to static UI assets.

Pi replies use `action=send`, exact `replyTo`, and `payload`; there is no `text`
argument or `chat.*` compatibility protocol. A transport receipt is not Pi
admission: admission is confirmed only by the matching canonical Pi user-message
event. Intercepted/failed asynchronous preparation leaves admission unknown.
Reply delivery means transport emission, not proof of component handling. Do not
automatically retry uncertain sends; reconnecting does not replay them.

## Delivery options and buffered context

`client.sendMessage(payload)` remains the single-request Chat API. An optional
second argument selects Pi delivery explicitly:

```js
client.sendMessage({text: "Please consider this"}, {
  role: "user", deliverAs: "steer",
});
client.sendMessage({selection: "button#save"}, {
  role: "context", deliverAs: "nextTurn", slot: "selection",
});
client.sendMessage({note: "additional evidence"}, {
  role: "context", deliverAs: "nextTurn", // no slot: append, not replace
});
client.inspectContext();       // metadata for pending nextTurn entries
client.clearContext("selection"); // omit slot to clear all pending nextTurn data
```

| Role | `deliverAs` | Behavior |
| --- | --- | --- |
| `user` (default) | `immediate` (default) | Idle-only; starts a turn. |
| `user` | `steer`, `followUp` | Pi's steering or follow-up queue while streaming; starts a turn when idle. |
| `context` | `immediate` | Idle-only; records contextual data, no turn by default. |
| `context` | `steer`, `followUp` | Native Pi custom-message delivery; see `triggerTurn` below. |
| `context` | `nextTurn` | Retain until the next prompt starts; never interrupt or start a turn. |

Only contextual messages accept `triggerTurn`. Omitting it preserves Pi's native
behavior: while streaming, steer/followUp use their respective queues; while idle,
context records without starting a turn. `true` also starts a turn when idle.
`false` does not interrupt streaming: Pi records the custom message after the current
turn's tool results, rather than steering/following up. `nextTurn` rejects `true`.
User messages always trigger processing and reject `nextTurn` and `triggerTurn`.
`slot` is valid only for context/nextTurn. Unknown options and invalid combinations
fail before submission. User input never expands slash commands or templates.

Context has its own `onDelivery({id, status, details})` callback, separate from
Chat's `onState` and `onMessage` callbacks. Context is not a request for a component
reply; use user messages for request/reply. The one-pending-user-message rule still
applies even to steer/followUp. Context can arrive while a user reply is pending.

- `buffered`: retained in the current Pi extension, not yet in conversation.
- `queued`: submitted to Pi's custom-message API; not admission proof.
- `attached`: its canonical custom message was confirmed by a message event or
  a record on the active session branch. Idle/deferred Pi appends bypass extension
  message events, so the extension also reconciles those records after submission,
  before model context preparation, and when the agent settles. This is **not**
  proof of an LLM request succeeding or the model acting on it.
- `replaced`, `cleared`, `rejected`, `inspected`: explicit buffer/control outcomes.
- `uncertain`: transport/disconnection prevented confirmation; never auto-resend.

The Pi tool adds `inspect_context` and `clear_context`, with optional `slot`, and
includes buffer metadata in `status`. Inspection returns IDs, slots and byte sizes,
not a duplicate of all payloads. The footer shows the number of pending nextTurn
entries. Limits: 16 total retained/queued context items and 32 KiB combined canonical
context; 32 outstanding context transport requests. Existing per-payload/frame limits
still apply. A rejected replacement leaves the previous slot intact.

The extension snapshots nextTurn entries in `before_agent_start` and removes only
matching versions after observing the canonical custom message. Intercepted prompts
do not consume them; newer updates remain for a later prompt. Slots keep their queue
position when replaced. Clear/replacement affects pending data, not a snapshot already
being attached or historical conversation. No durable queue or exactly-once guarantee.
Pending nextTurn buffers are ephemeral: close, reload, session switch/fork, tree
navigation, or process exit discards them. Clearing/closing cannot retract context
already handed to Pi's native steer/followUp queues. A browser reconnect does not replay data or recreate a lost buffer;
explicit inspection can discover what the still-bound Pi session retains.

On the wire, options are a `delivery` object beside `payload` in a version-1 message.
Buffer controls use `{v:1,id,kind:"context_control",action:"inspect"|"clear",slot?}`;
responses use `context_result` with `id`, `status`, and bounded `details`. The control
handshake advertises `deliveryOptions:1`; the server exposes it to the browser only
for a supporting Pi extension. Upgrade client, server, and extension together;
unsupported delivery must not silently become a normal user message. The bridge
never projects payload fields into policy, evaluates scripts, or accepts a system role.
Treat browser context as untrusted evidence; selecting data is not action authority.

The server mounts only `/lib/*`, `/sessions/<session-id>/*`, `/assets/*` (the
bridge browser modules), and `/health`. The endpoint record is not public.
Create the browser page under `sessions/<session-id>/` and import
`/assets/client.js`; use `sendMessage(payload)` for generic JSON delivery.
