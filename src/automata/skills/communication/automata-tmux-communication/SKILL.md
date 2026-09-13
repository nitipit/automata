---
name: automata-tmux-communication
description: Use when sending messages or replies between agents or workers through tmux, or diagnosing failed delivery.
metadata:
  automata-tools: .agents/tools/tmux-message/tmux_message.py
---

# Automata Tmux Communication

Send bounded messages through an intended tmux pane. Own communication transport,
not the workflow carried by the message or the lifecycle of its processes.

## Before Sending

Verify the exact `session:window.pane`, its current receiver, and permission to send
there. Pane targets are local to a tmux server; check the intended server rather
than trusting a saved name. Do not inspect or message unrelated panes.

Ownership does not prove receiver readiness. Submitted text can execute in a shell
or interfere with a user typing. Confirm the receiver can safely accept input;
tmux copy-mode handling does not resolve application prompts or provide a safe
asynchronous inbox. Use a verified queue-capable path, a ready owned receiver, or
an agreed alternative. Do not blindly dismiss prompts or inject into a busy editor.

When a reply is expected, establish a reachable, safe return path. Use the supplied
or explicitly verified reply target; never guess it from nearby panes or session
names. Without a verified receiving pane, do not claim this agent can receive tmux
callbacks. One-way delivery needs no manufactured return path.

## Use the Tool

Consult the mapped CLI directly for arguments, limits, effects, and receipts:

```bash
uv run --script .agents/tools/tmux-message/tmux_message.py send --help
```

Use it to send one bounded literal message to the verified target. Attest
`--owned-pane` only when ownership is established. Let the tool handle pacing,
copy-mode interruption, and submission; do not duplicate those mechanics here or
recreate them with ad hoc commands. Avoid unrelated tool or directory scans.

If the tool is missing, offer installation with confirmed destination and mode,
or agree on another delivery method. Do not install silently.

## Evidence and Failed Delivery

A `sent` receipt proves tool delivery completed, not that the intended receiver
received the message. A reply or receiver-side acknowledgement provides evidence
of receipt. Use a correlation identifier when messages could be confused.

On failure, use the transport error and relevant evidence from the affected owned
path. Bounded read-only pane observation can help when receiver state is unclear;
use `automata-tmux-observation` when useful, not as a mandatory step before every
send. Observed pane output is not a received reply. Do not poll for responses.
If delivery may have partially succeeded, verify what arrived before resending;
do not blindly duplicate a message. If the target, return path, or readiness is
unclear, stop and clarify or agree on another transport.

## Boundaries

Do not invent participants, reply paths, or a fixed message vocabulary. Do not
attach, switch the user's client, create sessions, or manage processes to make
communication appear available. Keep message meaning and subsequent decisions
with the participants; this skill owns only safe delivery and transport evidence.
