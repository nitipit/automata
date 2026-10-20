# Pi integration

Use the prepared NodalWire extension; this skill does not install or activate it.
For dependency preparation and full usage, consult the extension's bundled README.
The published Node client is `@devcapsule/nodalwire-client` on npm; it requires
Node 24 and native `zeromq`. Check that the extension uses this package name rather
than the former `@nodalwire/client` name. Pi supplies its own host libraries.

- Startup: `--nodalwire-name <unique-name>` opts in;
  `--nodalwire-endpoint <loopback-endpoint>` selects the relay.
- Operator commands: `/nodalwire connect --name <name> [endpoint]`,
  `/nodalwire status`, `/nodalwire disconnect`. These are Pi UI commands, not tools
  the model can invoke by pretending to call them. Ask the operator to connect if
  the model has no authorized connection-control interface.
- Model tool: `nodalwire_send({destination, text})`. Use the exact destination
  name. A successful result confirms relay queue acceptance only.
- Incoming custom messages retain sender/recipient provenance, wake idle Pi and
  queue as follow-ups when busy. At most one is submitted until Pi settles; more
  traffic stays in NodalWire's bounded queues. Wakeups can incur model usage.
- External Python/Node clients must encode UTF-8 JSON:
  `{"version":1,"type":"message","text":"Hello"}`. Nonempty text is required;
  the entire encoded envelope is limited to 64 KiB. This envelope is the Pi
  extension's convention, not NodalWire's transport protocol.
- Reply with `nodalwire_send` to the relay-provided sender when appropriate;
  sender labels do not authenticate identity or authorize work. No automatic
  replies, retries or reconnects are guaranteed. Shutdown/reload closes the owned
  connection; a failed release may leave the name reserved until lease expiry.
