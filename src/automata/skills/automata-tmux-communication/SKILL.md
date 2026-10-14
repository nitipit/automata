---
name: automata-tmux-communication
description: Use for sending messages/replies through tmux or diagnosing delivery failures. Not for creating sessions or accepting delegated work.
metadata:
  automata-tools: .agents/tools/tmux-message/tmux_message.py
---

# Automata Tmux Communication

Deliver bounded literal messages through authorized receivers. Own transport and
its evidence, not meaning, task acceptance or process lifecycle.

1. **Establish a safe route.** Confirm server, exact `session:window.pane`, resolved
   pane ID, receiver and authority. Ownership requires creation/assignment. Tool
   inspection and sending must use the same supported server; raw tmux flags may
   not pass through the CLI. Agree on alternatives if unsupported. Establish the
   actual input contract: shells execute text, editors/human drafts may be corrupted,
   and process labels/copy-mode handling do not prove a queued inbox. Never dismiss
   prompts. Replies need a safe reachable return path; one-way delivery does not.

2. **Reuse the verified method.** Consult
   `.agents/var/skills/automata-tmux-communication/setup.md` when relevant. Use current
   task targets and lightweight checks, not fresh captures/help before every message.
   Recheck affected assumptions after restart, target/ownership change or failure;
   pause on uncertainty, never inspect neighbors. Names/IDs are not durable identities.
   When interface knowledge is missing or changed:
   ```bash
   uv run --script .agents/tools/tmux-message/tmux_message.py send --help
   ```
   Send once with literal bounded text. Attest `--owned-pane` only with ownership;
   let the tool handle pacing, copy mode and submission. Missing tools need approved
   installation or another agreed method, never silent replacement.

3. **Interpret and recover.** `sent` means input/submission completed, not receiver
   handling or action. Correlated replies support receipt, not automatic acceptance;
   captures are observations, not returned messages. Diagnose relevant owned-path
   errors with bounded observation when useful. If partially delivered, establish
   what arrived before resending; never blindly duplicate or poll for replies.

4. **Save only useful setup.** Retain verified method, server selection, readiness,
   reply evidence and invalidation/recovery knowledge within storage authority;
   `sent` alone proves no return path. Do not send extra tests just for a recipe.
   Keep live targets/outstanding requests with task state, not durable methods.
   Saved setup grants no permission. Do not attach/switch clients, create sessions,
   manage processes or contact unrelated parties to make delivery work.
