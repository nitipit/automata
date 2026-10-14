---
name: automata-tmux-observation
description: Use for read-only identity, process state or bounded output evidence from an owned/assigned tmux pane. Not for polling or controlling sessions.
---

# Automata Tmux Observation

Answer a specific question with bounded evidence. Observation grants no sending,
shutdown or workflow authority; the caller interprets results.

1. **Verify the target.** Use the intended server and owned/assigned pane; familiar
   names do not establish ownership. Match metadata against recorded identity and
   recheck affected assumptions after restarts, mismatches or failed lookups. Names
   can be reused and IDs are not permanent. Never follow nearby matches or inspect
   unrelated clients. Saved setup grants no access permission.

2. **Read only what is needed.** Begin with metadata; capture only for the question.
   Apply the same server/socket selection; `TARGET` is the verified ID or exact address:
   ```bash
   tmux display-message -p -t "$TARGET" \
     'pane=#{pane_id} target=#{session_name}:#{window_index}.#{pane_index} pid=#{pane_pid} command=#{pane_current_command} cwd=#{pane_current_path} dead=#{pane_dead} mode=#{pane_in_mode}'
   tmux capture-pane -p -t "$TARGET" -S 0 -E 39
   ```
   Prefer small visible excerpts, not scrollback dumps or sensitive content. Report
   capture/lookup failures rather than assuming inactivity. Never send keys, dismiss
   prompts, attach/switch clients, create/stop sessions or install silently.

3. **Return facts and limits.** Identify server/target and relevant observation time.
   Output may be stale or partial; activity/silence/text proves neither readiness,
   receipt nor completion. A captured reply is not delivery on the return path, and
   pane existence is not client visibility. Client inspection needs separate authority
   and a relevant question. Do not poll or promise open-ended monitoring.

4. **Reuse setup appropriately.** Consult or retain discovered metadata/capture methods,
   bounds and invalidation knowledge at
   `.agents/var/skills/automata-tmux-observation/setup.md` within storage authority.
   Do not duplicate standard help or other owners' setup. Keep live identities and
   captures separate; captures are not persisted by default. Repair only changed
   assumptions rather than repeating discovery.
