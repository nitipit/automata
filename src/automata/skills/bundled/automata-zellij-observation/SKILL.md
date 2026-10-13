---
name: automata-zellij-observation
description: Use when gathering read-only identity, process state, or bounded output evidence from an owned or assigned Zellij terminal pane.
---

# Automata Zellij Observation

Gather bounded evidence from an owned or assigned terminal pane. Observation grants
no authority to send, focus, start or stop anything; the caller interprets results.

## Establish the target

Consult existing setup knowledge in an appropriate, authorized location. Reuse the
established storage convention; retain useful methods only within storage authority.
Keep current IDs and captures separate from reusable knowledge. Do not create records
just to repeat CLI help, and do not persist captures by default.

Resolve the exact named session and explicit `terminal_N` pane. Ownership requires
creation or assignment, not a familiar name. Check Zellij and relevant CLI support
when unknown or changed; installing this skill does not install the program.

Begin with metadata from the authorized session:

```bash
zellij --session "$SESSION" action list-panes --json
```

Match numeric `id` with `is_plugin: false`, expected command, CWD and exit state.
Plugin and terminal panes can share a number; command fields may be absent. A process
label or focus field does not prove readiness or what a human sees.

Use `action list-clients` only when the question requires client evidence for that
session. Pane existence does not prove client attachment; continuing activity after
detachment does not prove survival after server exit or reboot.

## Capture what answers the question

Read the viewport without changing focus:

```bash
zellij --session "$SESSION" action dump-screen --pane-id "$PANE_ID"
```

Prefer the viewport to full scrollback. Use `--full` only when needed and bound the
returned excerpt. `--ansi` preserves styling; `--path` saves output and requires
storage authority. Do not collect unrelated or sensitive output for convenience.

Re-establish affected assumptions after restarts, version changes, mismatches or
failed lookups. Report unavailable sessions, refusals and uncertain outcomes rather
than assuming the process ended or following nearby targets. Never install, attach,
switch focus or change configuration to repair an observation failure.

## Report evidence, not completion

Return session and terminal pane identity, observation time when relevant, and the
smallest useful excerpt. Output can be stale, incomplete or differ from raw process
output. Separate observation from inferred readiness, message receipt and task
completion. Captured acknowledgement text is not delivery through an agreed return
route.

Do not poll because a worker has not replied or start an open-ended watcher.
Observation never authorizes sending keys, dismissing prompts, creating panes or
managing processes. Saved setup knowledge grants no additional authority.
