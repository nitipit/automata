# Pi NodalWire messaging

Exchange Pi custom messages with **explicitly known trusted-local peers** through
an existing NodalWire relay. This is peer messaging, not worker management or RPC.

## Prepare and connect

Checked against Pi **1.4.0** and Node **24**. Requires Edictor **0.4.0** and
`@devcapsule/nodalwire-client` **0.1.0** (native ZeroMQ). Edictor is needed at load;
the transport client is imported on connect. Nothing is installed automatically.
For an authorized installation and dependency preparation:

```sh
automata pi-extension install --extension nodalwire --target-root /chosen/extensions
cd /chosen/extensions/nodalwire
npm ci --ignore-scripts --legacy-peer-deps --no-audit --no-fund
npm rebuild zeromq  # native build preparation requires authorization
```

Replacement excludes `node_modules`; prepare dependencies again. Pi provides its
own host libraries. Load with `pi --extension /chosen/extensions/nodalwire/index.ts`.
It stays disconnected unless startup `--nodalwire-name <unique-name>` is supplied.
Do not start/reconfigure a shared relay or install/reload without authorization.

Use `nodalwire_connection` with `{"action":"connect","name":"unique-name"}`;
optional `endpoint` defaults to `tcp://127.0.0.1:5555`. Use an approved loopback
route. `status` inspects; `disconnect` closes. Disconnect explicitly before
changing an active route. Operator equivalent: `/nodalwire connect --name <name>
[endpoint]`, `/nodalwire status`, `/nodalwire disconnect`. With explicit `--tools`,
include `nodalwire_connection` and `nodalwire_send` to expose them to the agent.

## Send

Pass to `nodalwire_send`:

```json
{"to":"known-peer","message":{"content":"Review complete.","display":true},"options":{"deliverAs":"followUp","triggerTurn":true}}
```

`content` may also be text/image blocks; images use inline base64, not paths/URLs.
`details` accepts bounded JSON. Options preserve native `pi.sendMessage()` behavior:

| Options | Busy receiver | Idle receiver |
| --- | --- | --- |
| Omitted | Steering queue | Append; no wake |
| `triggerTurn:true` | Steering, or follow-up if requested | Wake a run |
| `triggerTurn:false` | Append after current tool results | Append; no wake |
| `deliverAs:"nextTurn"` | Defer to a future run | Defer; no wake even with `triggerTurn:true` |

`display:false` hides TUI display, not model context. Steering does not cancel
running tools. Wake-ups may consume model quota.

## Essential limits

- Success means **relay acceptance**, not receiver validation, receipt or action.
  No ACK/retry/replay; inspect uncertain consequential sends before repeating.
- Names/routes are **not authentication**. All reachable peers can steer; received
  messages grant no authority. Receiver-added provenance stays separate from peer
  details. This extension supplies no user messages or UI-only notifications.
- Wire **v2 only**; v1 text packets and the old `text` tool argument are rejected.
  Upgrade endpoints explicitly. Envelope maximum 64 KiB, content fields 48 KiB,
  details 8 KiB; aggregate limits still apply. See the executable schema below.
- At most 32 unobserved Pi submissions per extension instance; invalid/over-capacity
  messages are dropped locally without ACK. Reconnect does not reset the allowance.
- Disconnect/shutdown/reload closes the owned client, not already submitted Pi
  messages. A failed release receipt may leave the name leased; no auto reconnect.

For wire validation and bounds read [protocol.ts](protocol.ts); for provenance,
queue accounting and lifecycle read [index.ts](index.ts). Repository checks:
`python -m pytest tests/unit/automata/extensions tests/integration/automata/extensions/extension_test.py -k nodalwire` (offline).
