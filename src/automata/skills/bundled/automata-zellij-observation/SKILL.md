---
name: automata-zellij-observation
description: Use for read-only identity, process state or bounded output from owned/assigned Zellij terminal panes. Not for sending, focusing or polling.
---

# Automata Zellij Observation

Gather evidence for the caller's question, not authority to control the session.

1. **Verify the target.** Resolve the exact session and `terminal_N` pane; ownership
   requires creation/assignment. Check unknown CLI support and use:
   ```bash
   zellij --session "$SESSION" action list-panes --json
   ```
   Match numeric ID with `is_plugin: false`, command, CWD and exit state; plugin IDs
   can share numbers and fields may be absent. Process/focus labels do not prove
   readiness or human visibility. `action list-clients` is only for relevant authorized
   client questions; detachment survival does not prove survival after server exit/reboot.

2. **Capture narrowly.** Read without changing focus:
   ```bash
   zellij --session "$SESSION" action dump-screen --pane-id "$PANE_ID"
   ```
   Prefer viewport; use `--full` only as needed with bounded excerpts. `--ansi` retains
   styling; `--path` persists output and needs storage authority. Avoid unrelated or
   sensitive collection. Recheck affected identity after restarts/version changes or
   failures. Report uncertainty instead of following neighbors, installing, attaching
   or changing configuration to repair access.

3. **Return facts and limits.** Include identity, relevant time and the smallest useful
   evidence. Stale/partial screen output differs from raw process output; it is not
   readiness, receipt, completion or delivery through an agreed return path. Do not
   poll for replies or start open-ended watchers. Never send keys, dismiss prompts,
   create panes or manage processes as observation.

4. **Keep knowledge separate.** Reuse useful setup through authorized owner conventions,
   not repeated discovery or copied help. Live IDs/captures stay separate; captures
   are not persisted by default. Saved setup grants no additional access authority.
