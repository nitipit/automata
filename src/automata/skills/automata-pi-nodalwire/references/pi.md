# Pi NodalWire integration

The bundled `nodalwire` extension README is authoritative for its version-2
Edictor schema, dependency preparation, commands, parameters and bounds. The
published transport client is `@devcapsule/nodalwire-client` (Node24/native zeromq);
Edictor0.4.0 validates the application envelope. Skill availability does not prove
installation, connection or runtime readiness.

- Startup opt-in: `--nodalwire-name <unique-name>` and optional
  `--nodalwire-endpoint <loopback-endpoint>`.
- Operator: `/nodalwire connect --name <name> [endpoint]`, `status`, `disconnect`.
- Agent: `nodalwire_connection({action, name?, endpoint?})` and
  `nodalwire_send({to, message, options?})`.
- Native `pi.sendMessage()` options are preserved, including omitted values;
  `nextTurn` remains deferred even with `triggerTurn:true`. `display` controls
  visibility independently. Use installed Pi docs, not protocol-specific presets.

External peers send UTF-8 JSON bytes shaped as:

```json
{
  "version": 2,
  "message": {"content": "Review complete.", "display": true},
  "options": {"deliverAs": "followUp", "triggerTurn": true}
}
```

Version1 text envelopes are not silently converted. The version2 envelope has no
role, customType, sender, message ID, acknowledgement or RPC command. The receiver
adds provenance and supplies its own custom type. Non-Pi applications may use the
same bytes; NodalWire itself remains an opaque byte transport.

All participants must be trusted local peers. Routing/admission policies are not
authentication; all reachable peers can request steering. Wakeups may incur model
usage. Relay send acceptance is not proof that receiver validation or delivery
succeeded. Never retry uncertain consequential messages without evidence.
