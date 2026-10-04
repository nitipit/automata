---
name: automata-message-router
description: Use when exchanging bounded JSON between configured nodes in a trusted Router network/application, or configuring, connecting, discovering permitted destinations, and recovering those connections.
metadata:
  automata-tools: .agents/tools/message-router/message_router.py
---

# Automata Message Router

Connect the intended participants, verify targeted delivery and meaningful handling,
and recover without confusing transport state with application outcomes. The Router
is transport, not an agent launcher, task manager or shared transcript. Participants
own payload meaning and action authority.

## Choose or reuse the intended connection

Consult saved setup before rediscovering commands. Reuse the shared service and
shipped browser/Node client, or an actually exposed agent adapter; check current
status, endpoints and ownership, not merely a listening port or old record.
Installing this skill or the shell CLI does not expose an agent tool or model wakeup.
An active agent may use an owned shell process with authorized loopback access,
private credentials and a live connection; do not invent a tool, inject history,
attach to an unrelated daemon or add a polling service as a fallback.

Use explicit configured identities, not page directories or whichever agent is
online. An agent adapter must bind the actual current session under its admission
contract; opening a client starts neither a server nor another agent. Revalidate
bindings after session changes. Authentication and authenticated provenance do not
grant shell, file, external-action or delegation authority.

This is a small trusted-network/application tool, not a public authentication
platform. Use loopback unless broader access is authorized. Provision each client's
own credentials privately, outside public assets and logs; serve only public-safe
files. Generic nodes need no pairing. Optional browser-session pairing remains a
separate supported path, not an admission prerequisite or automatic reconnect.
[Connect](references/connect.md) owns client recipes and optional pairing mechanics;
[Configure](references/configure.md) owns provisioning and migration.

After successful setup discovery, retain verified startup, connection, status and
owned cleanup commands with prerequisites, working directories and variable inputs
in approved owner-scoped data. Report the recipe location; do not duplicate tool
docs or retain live session IDs or pairing secrets there. Keep live endpoint state
separate for reconnection and cleanup. Saved setup is not permission. Repair only
invalid prerequisites within authority; missing installation needs authorization.

## Interpret identity, policy and presence separately

A **Node** is an identified endpoint—browser, agent or application—connected
independently to one central Router with its own private credential. Unknown nodes
are not admitted. Each node has one **Network**, a logical routing group defaulting
to `default`, not a LAN, VPN or sandbox. The service is not a participant.

Central policy decides who may initiate: same-Network peers default to allow,
cross-Network to deny; exact directed `allow` pairs permit exceptions, and `block`
pairs override both. Clients need no duplicate ACL. Version-1 configs retain only
their explicit grants; adopting Network defaults requires deliberate migration.
A reply is a connection-bound capability for an existing request, not a reverse
initiation grant. Status lists only destinations the caller may initiate toward.
Permission and current presence are separate; neither proves handler readiness.
[Discover](references/discover.md) owns the status view and examples.

## Exchange with exact correlation and reply ownership

Send complete bounded JSON to an explicit authorized destination. Register
correlation and inbound/response handling before sending; responses may precede
the forwarding receipt. **Forwarded is not handled:** distinguish server receipt,
adapter admission and component/model action. Consume requested terminal replies
through the same client; do not busy-poll or count logs as application handling.

For an inbound reply-capable request, respond or reject using the exact delivered
message ID and the complete component reply through the documented client/adapter.
Do not manufacture IDs, confuse sender correlation with the inbound route ID, or
silently change legacy delivery semantics. `expectReply: false` creates no return
capability; do not reply, and check adapter admission because some adapters ignore
one-way messages. Keep the connection open while interaction continues.

Retain pending correlation until `final: true`, `route_closed` or explicit cancel;
nonterminal progress may be applied only under the component's contract. Cancellation
abandons the reply capability, not recipient actions. Connection loss invalidates
capabilities; a replacement connection cannot recover them. [Send](references/send.md)
owns API/ID examples, component correlation and adapter receipt interpretation.

For context delivery, respect the adapter's actual queue, steering, admission and
turn-trigger limits. Pending data is not conversation history. Buffered, queued or
attached receipts do not prove handling; outbound replies do not automatically
trigger another model turn. Use canonical message/tool records, not duplicate
transcripts.

## Verify, recover and close within ownership

Verify a correlated exchange on the intended route, separating connection, server
receipt, adapter admission, reply delivery and actual handling. For UI exchanges,
verify the originating component applies the valid reply and represents failures
or uncertainty; a transport receipt or terminal-only answer is not end-to-end proof.
Check busy/disconnect behavior when relevant.

On rejection, uncertainty or stale evidence, diagnose the affected route and repair
only authorized setup. Never blindly replay an uncertain send or reconnect/replay
automatically. Revalidate endpoints and policy, reconnect explicitly when appropriate,
and update repaired recipes after verification. In-memory correlation and bounded
duplicate detection promise neither durable queues/history nor exactly-once business
execution. [Handle failures](references/failures.md) owns rejection, cancellation
races and route-closure details.

When interaction ends, close its binding and stop only owned Router services no
longer needed. Preserve pages and evidence; closing or stopping does not authorize
deletion. UI construction, browser control, delegation and installation remain
separate capabilities; command/protocol mechanics belong to the tool, and task
policy stays with the task. References are on-demand Markdown guides; their fixed
examples and optional Skill Builder rendering never connect to a live Router.
