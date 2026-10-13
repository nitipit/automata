---
name: automata-tmux-background
description: Use for starting, reusing, inspecting or stopping authorized persistent commands in detached tmux sessions without changing the active terminal view.
---

# Automata Tmux Background

Use direct shell calls for short work; tmux manages persistent process lifecycle,
not message transport, application behavior or result acceptance.

1. **Confirm server and ownership.** Command-start approval covers a dedicated
   session, not installation or extra effects. Use the same intended server/socket;
   IDs are server-local. Consult known setup first and list only to resolve owned
   reuse or collisions. Ownership means creation/assignment, not familiar names.
   Use task names and reuse only the same owned lifecycle; report collisions.

2. **Preserve the user's view.** Default to one detached session per independently
   managed process. Never add windows/panes to user-facing or unrelated sessions,
   attach/switch/select clients or alter layout/config/plugins/keys without authority.
   Detached flags alone do not protect attached views. In tmux, record the caller:
   ```bash
   CALLER_TARGET=$(tmux display-message -p -t "$TMUX_PANE" \
     '#{session_name}:#{window_index}.#{pane_index}')
   ```
   It identifies a return pane, not current client visibility. Claim unchanged view
   only with authorized before/after client evidence; do not navigate to repair it.

3. **Launch and verify.** Use authorized command and explicit CWD; examples assume
   consistent server selection:
   ```bash
   if tmux has-session -t "=$SESSION" 2>/dev/null; then exit 1; fi
   TARGET=$(tmux new-session -d -P \
     -F '#{session_name}:#{window_index}.#{pane_index}' \
     -s "$SESSION" -c "$WORKING_DIRECTORY" "$COMMAND") || exit 1
   tmux display-message -p -t "$TARGET" \
     'pane=#{pane_id} command=#{pane_current_command} cwd=#{pane_current_path} dead=#{pane_dead}'
   tmux capture-pane -p -t "$TARGET" -S 0 -E 39
   ```
   Retain returned target and resolved pane ID, not assumed indices. Inspect bounded
   startup evidence without attachment. A vanished session may mean completion or
   failure; report uncertainty instead of silently relaunching. Record server,
   command, CWD, owner and evidence in task state, not attachment instructions.

4. **Reuse or stop safely.** Revalidate affected identities after restart/mismatch;
   never follow nearby matches. Observation is diagnosis, not polling for replies.
   Stop only the exact owned lifecycle with shutdown authority; idleness is insufficient.
   Use application shutdown if needed, then `tmux kill-session -t "=$SESSION"` and
   check that exact session. Failed lookup alone may be server/socket/access failure.
   Session removal does not prove detached children stopped; verify owned resources
   separately and preserve sessions still needed.

5. **Retain useful setup.** Within storage authority, save discovered launch,
   prerequisites, checks, shutdown and invalidation knowledge at
   `.agents/var/skills/automata-tmux-background/setup.md`, not duplicated CLI help.
   Live pane/PID/owner data stays in task state. Reuse with lightweight relevant
   checks, repair only invalid parts, and reference other owners rather than copy
   their setup. Recipes grant no process-management permission.
