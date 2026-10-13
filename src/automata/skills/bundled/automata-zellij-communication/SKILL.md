---
name: automata-zellij-communication
description: Use when sending messages or replies between agents or workers through Zellij, or diagnosing uncertain delivery to a terminal pane.
---

# Automata Zellij Communication

Deliver bounded terminal messages through an authorized route. Own transport and
its evidence, not message meaning, delegation or process lifecycle.

## Establish a safe route

Consult existing setup knowledge in an appropriate, authorized location. Reuse the
established convention, keeping reusable methods separate from current recipients
and outstanding requests. Installing this skill supplies guidance, not a transport
tool or permission to contact a worker.

Establish the exact named session, explicit `terminal_N` pane ID, intended receiver
and sending authority. Ownership requires creation or assignment. Names and IDs can
be reused after restarts; familiarity does not establish identity.

When identity is unknown or invalidated, use the authorized session's
`action list-panes --json`. Match numeric `id` with `is_plugin: false`, intended
command and CWD. Plugin and terminal panes can share a number. Do not inspect
neighbors to find a convenient receiver.

Verify the input contract and a clear entry field with no competing human input.
A shell can execute a message; an editor or prompt can be corrupted. A working
agent is safe only when its queued-input behavior is established, not merely
because its process is running. Idle and working Pi delivery were verified: the
running command finished before the queued message was handled. That one-sender,
clear-input proof does not establish concurrency safety or safety for other
interfaces or human drafts.

For a reply, establish an authorized, reachable return session and terminal pane
with the same checks. One-way messages need no invented return path.

## Send text and submit

Use the verified route across either the same or different sessions:

```bash
zellij --session "$RECEIVER_SESSION" action paste \
  --pane-id "$RECEIVER_PANE" "$MESSAGE" &&
zellij --session "$RECEIVER_SESSION" action send-keys \
  --pane-id "$RECEIVER_PANE" "Enter"
```

Keep the message one bounded literal argument. Both calls must target the same
session and terminal pane. `paste` uses bracketed paste where supported; it does
not guarantee a safe inbox or submit automatically. Confirm the receiver's submit
key. Check local help when the CLI is unknown or changed.

Use one writer per receiving pane through paste and submission. These are separate
operations, not an atomic transaction or a lock. If exclusive writing cannot be
established, do not send. Different receivers can operate independently.

CLI-generated modified keys may differ from physical keyboard input. Enter is
verified for this route; do not assume other key combinations work equivalently.

## Receipt and recovery

Successful CLI exit means the operation was accepted, not that the receiver handled
or accepted the task. A correlated acknowledgement supports receipt; a screen
capture alone is not a returned reply. Receipt does not establish understanding,
acceptance or completion of the delegated task.

On failure or partial delivery, inspect only relevant evidence from the owned
route before retrying. Determine what arrived or interleaved; never blindly resend.
Pause if identity, readiness, return path or writer ownership is uncertain. Do not
poll for replies, dismiss prompts, switch focus or create workers to repair a route.

Retain useful verified methods and limits only within storage authority. Saved
knowledge grants no sending authority. Revalidate only affected assumptions after
restarts, changed receivers or delivery failures.
