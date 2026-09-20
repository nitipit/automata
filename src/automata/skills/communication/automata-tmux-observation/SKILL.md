---
name: automata-tmux-observation
description: Use when an agent needs read-only evidence from an owned or assigned tmux pane, such as receiver state, process activity, or output relevant to a communication or management decision.
---

# Automata Tmux Observation

Gather bounded evidence from an explicitly owned or assigned tmux pane. The caller
chooses the question and interprets the evidence; this skill does not manage the
process or decide what its output means for the surrounding workflow.

## Establish and reuse observation setup

Consult `.agents/var/skills/automata-tmux-observation/setup.md` when present before
rediscovering commands. If setup required experimentation, save useful verified
server selection, metadata/capture methods, output bounds, interpretation limits
and invalidation conditions there within storage authority. Do not create a record
merely to repeat standard commands; reference another capability's setup instead
of duplicating it. Keep live pane identities and captures separate from recipes.

For each observation, choose the question and authorized target. Ownership means
this workflow created the resource or was assigned it, not that its name is familiar.
Use the known method with lightweight checks of changeable prerequisites, not a
fresh setup sequence. Match returned metadata to the intended server and recorded
pane identity. Names/addresses can be reused, and IDs do not survive server restarts
as durable identities. Restart, mismatch, lookup failure or changed output format
requires resolving only the affected assumptions and updating verified knowledge.
Saved setup grants no inspection permission; never follow nearby matches.

Start with relevant metadata; capture output only if the question requires it.
Prefer a small excerpt over scrollback dumps. Do not inspect unrelated panes or
collect sensitive content for convenience.

## Read-Only CLI

Use tmux's read-only commands and consult their help when needed. Apply the intended
server consistently, for example with `-S` when using an explicitly known socket.
These examples assume that server is selected and `TARGET` is the verified pane ID
or exact address; metadata must resolve to the intended pane:

```bash
tmux display-message -p -t "$TARGET" \
  'pane=#{pane_id} target=#{session_name}:#{window_index}.#{pane_index} pid=#{pane_pid} command=#{pane_current_command} cwd=#{pane_current_path} dead=#{pane_dead} mode=#{pane_in_mode}'
```

For a bounded excerpt of the visible pane, without requesting scrollback:

```bash
tmux capture-pane -p -t "$TARGET" -S 0 -E 39
```

Choose the smallest useful output bound. A pane's process label or mode does not
establish application readiness; output may be stale, partial, or unrelated to the
current request. Report lookup and capture failures rather than treating missing
output as inactivity or silently selecting another target.

## Return Evidence

Identify the observed server/target and relevant observation time, then summarize
facts and uncertainty. Include only the output needed to support the caller's
question, excluding secrets and irrelevant content. Do not persist captures by
default; retained evidence needs an approved owner and location.

Activity, silence or visible text alone is not proof of readiness, message receipt,
or work completion. A captured reply is output evidence, not delivery to its intended
recipient through the agreed return path. A pane's identity or existence also does
not establish what an attached client is viewing. Inspect an explicitly authorized
client only when that separate question matters. Let the caller interpret evidence
and choose the next action; observation grants no permission to send or stop work.

## Boundaries

Observe only: do not send keys, dismiss prompts, attach, switch clients, create or
stop sessions, or change terminal state. Do not install tmux silently. Do not turn
an observation into an automatic polling loop; repeated observation needs a new
reason within the caller's scope, not a promise to monitor. Communication, process
lifecycle, and management decisions remain with their respective owners. Other
skills may use this capability when useful, without a mandatory invocation chain.
