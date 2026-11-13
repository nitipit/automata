# External clients for Pi NodalWire

Read the active extension's compact README first for preparation, routing and
native delivery semantics. Its `protocol.ts` owns the executable wire schema and
bounds; inspect that file for encoding/validation details, not a second field list.
The transport client is `@devcapsule/nodalwire-client`; NodalWire carries opaque
bytes, while the Pi extension validates the application envelope. Use matching
published **0.3.0** client/relay artifacts. The expanded Pi tools support explicit network membership, per-call network
selection and native request/reply; consult the active bundle because an older
installed bridge may still support only open `default`.

External clients connect, send UTF-8 JSON bytes, then close their owned connection.
For example, in a prepared Node.js environment where the client is resolvable:

```js
import { randomUUID } from "node:crypto";
import { Node } from "@devcapsule/nodalwire-client";

const client = await Node.connect(
  `sender-${randomUUID()}`, "tcp://127.0.0.1:5555",
);
try {
  await client.send("known-pi-peer", Buffer.from(JSON.stringify({
    version: 2,
    message: { content: "Review complete.", display: true },
    options: { deliverAs: "followUp", triggerTurn: true },
  }), "utf8"));
} finally {
  await client.close();
}
```

The endpoint and destination are examples, not approved routes. The receiver must
already be connected under the chosen destination name. This example wakes an idle
receiver; use only with authority for that effect. Consult the installed client's
README for transport API details; this reference does not provide a send CLI.

Pi application version 2 is unchanged by upstream NWM3. Send JSON bytes directly
with `send` for asynchronous delivery; the bridge never generates an automatic
response. NWR1 codecs were removed upstream; native `id`/`reply_to`
are separate transport metadata, not payload fields. `send` returns an accepted
message-ID string, not proof of receipt or work. The expanded Pi send tool
returns that accepted ID; it is distinct from local Pi submission accounting.
Version 1 text envelopes are rejected, not converted. This envelope has no role,
customType, sender, message ID, acknowledgement or RPC command. The receiver adds
transport provenance and its own custom type. Use `encodeMessage`/`decodeMessage`
from the prepared bundle, or validate equivalent bytes against that schema.

For native request/reply, use SDK `request`/`reply` with the same v2 bytes. The Pi
recipient replies using its receiver-issued `replyRef`; request content should
explicitly ask for that response. Native IDs alone do not mark request intent.
Matched replies return through the requesting API, while unmatched/late replies
remain ordinary incoming messages. The example above intentionally uses ordinary
`send`, so no reply is promised.

Use installed Pi messaging API documentation for native option behavior. Names
and route policies are not authentication. Wake-ups may consume model usage;
relay acceptance does not prove receiver validation or action. Do not blindly
repeat uncertain consequential messages.
