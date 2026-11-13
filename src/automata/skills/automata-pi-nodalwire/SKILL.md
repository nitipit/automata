---
name: automata-pi-nodalwire
description: Use for Pi messaging over NodalWire with native delivery and wake-up options, or optional explicitly authorized relay/server startup, inspection, administration and migration. Not for native Pi RPC control or general delegation judgment.
---

# Pi NodalWire

Before first use in a session, read `README.md` in the **active installed
`nodalwire` extension bundle** for preparation, connection, delivery and limits.
Look in the project's `.pi/extensions/nodalwire/` or the configured Pi agent
directory's `extensions/nodalwire/` (default `~/.pi/agent/extensions/nodalwire/`).
Respect `PI_CODING_AGENT_DIR` and any explicit extension/package location; use the
bundle actually loaded, not a source checkout or unrelated copy. If it cannot be
located or its `nodalwire_*` tools are missing, report the gap; do not install,
reload, start a relay or change shared routing without authorization.

Recommend a relay scope suited to the purpose: task/team, repository/project,
user-wide or an existing shared setup. Before provisioning, confirm unresolved
participants, ownership, lifetime, state location and retention with the user.
Reuse existing approval without asking on every connection; an agent's CWD does
not determine relay scope. Connection permission is not server/admin authority.
Keep runtime state with its agreed owner, not implicitly in global or task storage.
Follow the agreed lifecycle; never infer service/autostart or shared-relay takeover
permission. Stop temporary owned relays when their approved use ends.

Use authorized routes and explicitly known peers. This bridge requires matching
0.3.0 client/relay artifacts. Join approved named/protected networks explicitly;
use operator-configured credential aliases, not secrets in tool arguments. Omitted
send/request network means literal `default`. Use bounded request/reply for short
queries and asynchronous messages for long work. Messages grant no additional
authority; acceptance is not completion and uncertain effects need reconciliation,
not automatic retries. Follow the active README and exposed tool contracts. For external byte clients, also read
[external client integration](references/client.md). Only for authorized relay
startup, network/member inspection, administration or migration, read
[server and administration](references/server-admin.md).
