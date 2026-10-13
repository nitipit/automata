---
name: automata-zellij-background
description: Use when starting, inspecting, reusing, or stopping a persistent command in an isolated Zellij session without changing the user's terminal workspace.
---

# Automata Zellij Background

Manage an authorized background command's lifecycle, not application behavior or
message transport. Use a direct shell call for short-lived work.

## Establish ownership

Consult existing setup knowledge in an appropriate, authorized location. Reuse the
established storage convention; retain new knowledge only when it avoids useful
rediscovery. Keep reusable methods separate from task-specific sessions and logs.
Saved knowledge grants no permission to manage a resource.

Check Zellij availability and relevant CLI support when unknown or changed; skill
installation does not install Zellij. Starting an approved command covers a dedicated
background session, not software installation or changes to global configuration.

Use a task-specific session name. Check exact collisions with
`zellij list-sessions --short --no-formatting`, without inspecting unrelated work.
`attach --create-background` can reuse an existing session; do not take over an
unowned name or resurrect saved commands without authority. Ownership requires
workflow creation or assignment, not familiarity.

## Launch without changing the user's view

For a collision-free name, this Bash example assumes the command, CWD and argument
array `ARGS` have been chosen within scope. Use `ARGS=()` for no arguments:

```bash
zellij attach --create-background "$SESSION" || exit 1
PANE_ID=$(zellij --session "$SESSION" action new-pane \
  --name "$PROCESS_NAME" --cwd "$WORKING_DIRECTORY" \
  -- "$PROGRAM" "${ARGS[@]}") || exit 1
[[ "$PANE_ID" =~ ^terminal_[0-9]+$ ]] || exit 1
```

Pass arguments separately; invoke a shell only when the command needs shell
semantics. Use an explicitly approved task configuration when required, rather
than treating particular input modes or serialization settings as defaults.

Record the session, returned terminal pane ID, command, CWD and lifecycle owner
with the task. Verify startup without attaching:

```bash
zellij --session "$SESSION" action list-panes --json
zellij --session "$SESSION" action dump-screen --pane-id "$PANE_ID"
```

Match numeric `id` with `is_plugin: false`, expected command, CWD and exit state.
Plugin and terminal IDs can share a number; fields may be absent. Output alone
does not prove readiness. Report failed or uncertain startup before relaunching.

Always name the session. Do not create panes in user-facing or unrelated sessions,
attach clients, switch focus, change layouts or alter keybindings to make work
available. A detached command can still disturb an attached workspace.

## Reuse and stop

Reuse only the same owned lifecycle. Revalidate affected identity and readiness
facts after restarts, changed settings or failures; do not follow nearby matches.
Pane IDs are session-local and are not permanent across restarts.

Before shutdown, match the exact session to its recorded owner. Use application
shutdown where required, then stop only that session:

```bash
zellij kill-session "$SESSION"
```

Verify absence from the active listing and check application-owned children
separately. Client detachment, server shutdown and saved-session deletion are
different outcomes. Cleanup needs authority; never use all-session kill/delete
commands or infer permission to stop from idleness.
