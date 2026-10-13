---
name: automata-zellij-background
description: Use for starting, reusing, inspecting or stopping authorized persistent commands in isolated Zellij sessions without disturbing the user's workspace.
---

# Automata Zellij Background

Own background lifecycle, not application behavior or message transport. Use direct
shell calls for short work. Approved commands cover dedicated sessions, not installs
or global configuration changes.

1. **Confirm ownership.** Reuse relevant setup and check unknown CLI support.
   Use task-specific names; `zellij list-sessions --short --no-formatting` resolves
   collisions, not unrelated work. Creation/assignment establishes ownership;
   `attach --create-background` may reuse a name, so never take over or resurrect
   unowned sessions. Keep live identities separate from reusable setup knowledge.

2. **Launch without changing the view.** For a collision-free name and authorized
   command/CWD, use separate arguments (`ARGS=()` if empty):
   ```bash
   zellij attach --create-background "$SESSION" || exit 1
   PANE_ID=$(zellij --session "$SESSION" action new-pane \
     --name "$PROCESS_NAME" --cwd "$WORKING_DIRECTORY" \
     -- "$PROGRAM" "${ARGS[@]}") || exit 1
   [[ "$PANE_ID" =~ ^terminal_[0-9]+$ ]] || exit 1
   zellij --session "$SESSION" action list-panes --json
   zellij --session "$SESSION" action dump-screen --pane-id "$PANE_ID"
   ```
   Use shells only for required semantics and custom configuration only when approved.
   Match numeric ID with `is_plugin: false`, command, CWD and exit state; fields may
   be absent and plugin IDs may share numbers. Record session, returned pane, owner
   and startup evidence. Output alone is not readiness; inspect failure before relaunch.
   Always name the session. Never add panes to user-facing/unrelated sessions, attach
   clients, switch focus or change layouts/keys—even detached actions can disturb views.

3. **Reuse and stop precisely.** Reuse only the same owned lifecycle; verify affected
   identity after restarts/settings changes or failures, not nearby targets. Pane IDs
   are session-local. Use application shutdown as needed, then
   `zellij kill-session "$SESSION"` only with lifecycle authority. Verify active-list
   absence and owned children separately. Detachment, server exit and saved-session
   deletion differ. Idleness grants no stop/cleanup authority; never kill/delete all
   sessions. Save useful verified methods only within the owner's storage convention.
