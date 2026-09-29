---
name: automata-tmux-background
description: Use when an agent needs to start, inspect, reuse, or stop a persistent command in a detached tmux session without changing the active terminal view.
---

# Automata Tmux Background

Manage the lifecycle of an authorized persistent command without changing the
active terminal view. Use a direct shell command for short-lived checks; tmux is
for work that must survive the invoking shell call or remain inspectable later.

## Authority and targets

Command-start approval includes a dedicated background session. Ask only when
the command, installation or material consequences lack authorization.

Consult any saved setup recipe before discovery. On first setup, confirm tmux
availability and the intended server; use that server consistently, including any
explicit socket option. Session/pane identifiers are server-local. Use listings
only to resolve collisions or owned reusable sessions, not to inspect unrelated work.

Ownership requires workflow creation or explicit assignment, not a familiar name.
Use task-specific names. Reuse only within the same owned lifecycle; resolve or
report collisions rather than silently renaming or replacing work.

## Save and reuse verified setup

When setup required discovery, retain the verified launch method, prerequisites,
startup evidence, shutdown procedure and invalidation conditions under
`.agents/var/skills/automata-tmux-background/setup.md`, within storage authority.
Save only knowledge that avoids rediscovery, not copies of standard commands.
Current session/pane IDs, process identities and lifecycle owners belong in the
active task's runtime state, not the durable recipe.

Reuse a successful recipe with lightweight checks of changeable prerequisites.
Do not repeat discovery for each launch. Server restarts, changed launch settings,
failed startup or identity mismatches require repairing only the affected part;
update the recipe after verification. Saved knowledge grants no authority to start,
reuse or stop processes. Reference another owner's setup rather than copying it.

## Preserve the active view

Use one dedicated detached session per independently managed process by default.
Never create panes/windows in user-facing or unrelated sessions, even with detached
flags: layout and status changes can still affect attached clients.

Do not run bare `tmux`, `attach-session`, `switch-client`, `select-window` or
`select-pane`. Do not change server configuration, layout, plugins or keybindings,
or install tmux without approval. Never switch clients to recover from failure.

When invoked inside tmux, record the caller's pane for return-path identity:

```bash
CALLER_TARGET=$(tmux display-message -p -t "$TMUX_PANE" \
  '#{session_name}:#{window_index}.#{pane_index}')
```

Keep that identity with the task's live return path. It does not establish an
attached client's visible state: the client can switch while the pane remains.
Use detached-only operations; claim an unchanged view only with before/after
evidence from an authorized client. Do not inspect other clients or navigate one
to repair a discrepancy.

## Start and verify

Use the chosen name, explicit working directory and authorized command. These
examples assume the intended tmux server is selected consistently:

```bash
if tmux has-session -t "=$SESSION" 2>/dev/null; then
  echo "session already exists: $SESSION" >&2
  exit 1
fi

TARGET=$(tmux new-session -d -P \
  -F '#{session_name}:#{window_index}.#{pane_index}' \
  -s "$SESSION" -c "$WORKING_DIRECTORY" "$COMMAND") || exit 1
```

Retain the returned target and resolve its server-local pane ID instead of assuming
window/pane indices or implicit selection. Verify startup without attaching:

```bash
tmux display-message -p -t "$TARGET" \
  'target=#{session_name}:#{window_index}.#{pane_index} pane=#{pane_id} command=#{pane_current_command} cwd=#{pane_current_path} dead=#{pane_dead}'
tmux capture-pane -p -t "$TARGET" -S 0 -E 39
```

Inspect only relevant startup output. A vanished session may have completed or
failed; report evidence, not assumed readiness, and do not silently relaunch.
Report server/session, target, command, CWD and startup evidence. Do not offer
interactive attachment instructions.

## Inspect and stop

Use the task's current target, not an old recipe's session name. Match inspection
metadata to its recorded identity; re-establish ownership after server restarts or
identity changes, and verify the exact owned session before shutdown. Stop on
mismatches or failed lookups rather than following nearby matches.
Reuse bounded metadata/output commands for diagnosis; consult tmux-observation when
useful, not as a mandatory step. Output may be evidence of activity, but is not by
itself readiness, a delivered reply or accepted completion. Do not sleep/poll for
delegated results.

Stop only an owned session whose lifecycle authorizes shutdown. Idleness alone is
not permission. Use application-specific graceful shutdown when required, then
remove the exact session and verify that it is gone:

```bash
tmux kill-session -t "=$SESSION"
# Then check the same exact target and inspect any diagnostic:
tmux has-session -t "=$SESSION"
```

Successful removal plus expected absence supports closure. A failed lookup alone
may mean a wrong socket, unavailable server or permission failure; report uncertainty.
Session removal does not prove detached children stopped. Verify application-owned
resources separately and preserve sessions still needed.

## Boundaries

This skill owns background process/session lifecycle, not application behavior,
message transport, watchdogs or result acceptance. Communication and management
retain those decisions. Inspect, signal and stop only explicitly owned resources;
never manage unrelated sessions to make the current task easier.
