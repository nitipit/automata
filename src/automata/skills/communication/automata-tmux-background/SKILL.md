---
name: automata-tmux-background
description: Use when an agent needs to start, inspect, reuse, or stop a persistent command in a detached tmux session without changing the active terminal view.
---

# Automata Tmux Background

Use tmux to keep an authorized command running in the background. Operate tmux
non-interactively through explicit owned targets; never move the user or agent into another
session, window, or pane.

## Scope

This skill owns the background lifecycle of persistent commands:

- detecting tmux and relevant existing sessions;
- creating a dedicated detached session;
- verifying startup, command, working directory, and initial output;
- inspecting or reusing an explicitly owned background target; and
- stopping and cleaning up that owned session when authorized.

It does not own the command's application behavior, inter-agent communication, task
acceptance, terminal layout, configuration, or interactive viewing.

Use a direct shell command for short-lived checks. Use this skill when the process should
continue independently of the invoking shell command or needs later status and output
inspection.

## Authorization and Selection

Authorization to start the underlying persistent command includes permission to place that
command in a dedicated background session. Do not request separate ceremonial confirmation
for tmux. Still ask when the process itself was not authorized, installation is required, or
starting it has a material unresolved consequence.

Confirm tmux is available; do not install it or change terminal configuration without user
approval:

```bash
command -v tmux
tmux list-sessions
```

Session listing may be used to avoid name collisions and find an explicitly owned reusable
session. Do not inspect pane content or processes in unrelated sessions.

Choose a clear task-specific session name. A session is owned only when the current workflow
created it or the user explicitly assigned it. Do not infer ownership from a familiar name.

## Background-Only Invariant

Create and manage processes without changing any active client view.

Never execute interactive or client-navigation commands as part of this workflow, including:

```bash
tmux
tmux attach-session
tmux switch-client
tmux select-window
tmux select-pane
```

Do not create windows or panes inside a user-facing or otherwise unrelated session, even with
a detached flag. Layout and status changes can still disturb an attached client. Use one
dedicated detached session per independently managed process by default.

Reuse is allowed only when the destination is an explicitly owned background session and the
new command belongs to the same managed lifecycle.

When running inside tmux, record the invoking pane before creation and verify it remains the
same afterward:

```bash
CALLER_TARGET=$(tmux display-message -p '#{session_name}:#{window_index}.#{pane_index}')
```

Do not use client switching as a recovery mechanism. If detached creation or targeted
inspection fails, report the failure and preserve the current terminal view.

## Start a Background Process

Before creation, confirm that the chosen session name does not already exist. Then create the
session detached with an explicit working directory and command:

```bash
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "session already exists: $SESSION" >&2
  exit 1
fi

tmux new-session -d \
  -s "$SESSION" \
  -c "$WORKING_DIRECTORY" \
  "$COMMAND"
```

Resolve and retain the exact target rather than relying on implicit current-window behavior:

```bash
TARGET="${SESSION}:0.0"
tmux display-message -p -t "$TARGET" \
  'target=#{session_name}:#{window_index}.#{pane_index} pane=#{pane_id} command=#{pane_current_command} cwd=#{pane_current_path}'
```

Check startup without attaching:

```bash
tmux has-session -t "$SESSION"
tmux capture-pane -p -t "$TARGET" -S -100
```

A session that disappears immediately may indicate that the command exited or failed before
inspection. Report what can be observed without silently relaunching it. Use application-level
health evidence when process presence alone is insufficient.

If the caller was already inside tmux, compare its current pane target with `CALLER_TARGET`
after creation. A mismatch is a workflow failure; do not continue managing the new process
until the unexpected client change is understood.

Report the session name, exact target, command, working directory, and observed startup state.
This skill does not execute or provide interactive attachment instructions.

## Inspect and Stop

Inspect only through exact targets and non-interactive commands:

```bash
tmux has-session -t "$SESSION"
tmux display-message -p -t "$TARGET" \
  'pane=#{pane_id} command=#{pane_current_command} cwd=#{pane_current_path} dead=#{pane_dead}'
tmux capture-pane -p -t "$TARGET" -S -100
```

Capture output to establish startup or diagnose a failure, not as a substitute for
application-level results or an agreed communication path. Do not turn this inspection into a
`sleep`-and-poll loop for delegated work completion.

Stop only an explicitly owned session after the process lifecycle authorizes shutdown. Use an
exact target and verify removal:

```bash
tmux kill-session -t "$SESSION"
! tmux has-session -t "$SESSION" 2>/dev/null
```

Do not kill a whole session merely because one command appears idle. Preserve it when its
continued background lifecycle is still intended.

## Boundaries

- Keep all creation and management detached, non-interactive, and explicitly targeted.
- Never attach, switch clients, navigate visible panes, or alter the active terminal view.
- Do not add panes or windows to user-facing or unrelated sessions.
- Do not inspect, signal, stop, or clean up sessions not owned by the current workflow.
- Do not install tmux or modify its server, configuration, layout, plugins, or keybindings.
- Do not silently choose a new session name after a collision; inspect ownership or report it.
- Do not duplicate communication, watchdog, task-acceptance, or application-specific policy.
