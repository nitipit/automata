---
name: automata-tmux-communication
description: Use when sending messages or replies between agents or workers through tmux, or diagnosing failed delivery.
metadata:
  automata-tools: .agents/tools/tmux-message/tmux_message.py
---

# Automata Tmux Communication

Deliver bounded messages through an authorized tmux receiver. Own transport and
its evidence, not message meaning, task acceptance or process lifecycle.

## Establish and retain the delivery path

Consult `.agents/var/skills/automata-tmux-communication/setup.md` when present before
rediscovering setup. Initially establish the intended server, exact
`session:window.pane`, resolved pane ID, receiver and permission. Ownership means
this workflow created the resource or was assigned it; familiarity is insufficient.

Inspection and sending must reach the same server. Check the tool's supported
server selection; raw tmux flags do not necessarily pass through its CLI. If the
verified server is unsupported, agree on an alternative, not the default server.

Establish a safe receiver: submitted text can execute in a shell or interfere with
human input. A process label, ownership or copy-mode handling does not prove a
queue-capable inbox. Do not dismiss prompts or inject into a busy editor. For an
expected reply, establish a reachable safe return path; never guess one from nearby
panes. One-way delivery needs no manufactured return path.

After a successful authorized exchange, retain useful verified commands, server
selection, readiness expectations, reply mechanism, evidence and invalidation or
recovery conditions in the setup recipe, within storage authority. A `sent`
receipt alone does not verify receiver handling or a return path. Record what was
actually verified; do not send extra test messages merely to complete a recipe.
Avoid duplicating standard CLI help or another capability's setup.

Keep current recipients, pane IDs, return targets and outstanding requests in task
runtime state, separate from the durable method. Names/addresses can be reused and
IDs are not permanent across server restarts. Neither record grants permission or
proves that an old recipient still exists.

## Reuse during normal work

Use the established method and current authorized targets. Apply lightweight checks
to relevant changeable prerequisites; do not repeat discovery, read help or capture
the pane before every message. Re-establish affected assumptions after a server or
receiver restart, changed target/ownership, delivery failure or readiness uncertainty.
If identity or safety is unclear, pause rather than sending or inspecting neighbors.
Repair only what is invalid and update setup knowledge after verification.

When the interface is unknown or changed, consult the mapped CLI:

```bash
uv run --script .agents/tools/tmux-message/tmux_message.py send --help
```

Send one bounded literal message. Attest `--owned-pane` only with established
ownership; let the tool handle pacing, copy-mode interruption and submission rather
than recreating them. If missing, offer installation with confirmed destination and
mode or another agreed method; never install silently.

## Interpret evidence and recover

A `sent` receipt means input/submission steps completed, not application receipt,
understanding or action. A correlated acknowledgement or reply supports receipt,
not automatic acceptance. Captured pane output is observation, not a returned reply.

On failure, inspect the transport error and relevant evidence from the owned path.
Use bounded tmux-observation only when useful for diagnosis, not as a mandatory
pre-send chain. Do not poll. If delivery may have partially succeeded, determine
what arrived before resending; never blindly duplicate a message. An uncertain
target, return path or receiver requires clarification or an agreed alternative.

## Boundaries

Do not invent participants or fixed message vocabulary. Do not attach, switch the
user's client, create sessions or manage processes to make delivery available.
Respect isolation and reporting authority; saved setup never authorizes contacting
unrelated parties. Workflow decisions remain with the participants.
