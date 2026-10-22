# External clients for Pi NodalWire

Read the active extension's compact README first for preparation, routing and
native delivery semantics. Its `protocol.ts` owns the executable wire schema and
bounds; inspect that file for encoding/validation details, not a second field list.
The transport client is `@devcapsule/nodalwire-client`; NodalWire carries opaque
bytes, while the Pi extension validates the application envelope.

External clients send UTF-8 JSON bytes shaped as:

```json
{
  "version": 2,
  "message": {"content": "Review complete.", "display": true},
  "options": {"deliverAs": "followUp", "triggerTurn": true}
}
```

Version 1 text envelopes are rejected, not converted. This envelope has no role,
customType, sender, message ID, acknowledgement or RPC command. The receiver adds
transport provenance and its own custom type. Use `encodeMessage`/`decodeMessage`
from the prepared bundle, or validate equivalent bytes against that schema.

Use installed Pi messaging API documentation for native option behavior. Names
and route policies are not authentication. Wake-ups may consume model usage;
relay acceptance does not prove receiver validation or action. Do not blindly
repeat uncertain consequential messages.
