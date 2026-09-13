---
name: automata-tmux-observation
description: Use when an agent needs read-only evidence from an owned or assigned tmux pane, such as receiver state, process activity, or output relevant to a communication or management decision.
---

# Automata Tmux Observation

Gather bounded evidence from an explicitly owned or assigned tmux pane. The caller
chooses the question and interprets the evidence; this skill does not manage the
process or decide what its output means for the surrounding workflow.

## Choose the Observation

Establish the intended server, exact `session:window.pane` target, permission to
inspect it, and the question the observation should answer. Pane identities are
server-local and may be stale. A familiar name or a recorded target does not prove
current identity or ownership. If the target or authority is unclear, clarify
rather than inspecting nearby sessions.

Start with pane/process metadata. Capture output only when it is needed and within
the authorized scope. Do not read unrelated panes or collect sensitive content for
convenience. Prefer a small relevant excerpt over a full scrollback dump.

## Read-Only CLI

Use tmux's read-only commands and consult their help when needed. Apply the intended
server consistently, for example with `-S` when using an explicitly known socket.
These examples assume that server is already selected and `TARGET` is verified:

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

Activity, silence, or visible text alone is not proof of readiness, message receipt,
or work completion. A captured reply is an observation of output, not delivery of
that reply to its intended recipient. Let the caller decide whether more evidence
or another action is warranted.

## Boundaries

Observe only: do not send keys, dismiss prompts, attach, switch clients, create or
stop sessions, or change terminal state. Do not install tmux silently. Do not turn
an observation into an automatic polling loop; repeated observation needs a new
reason within the caller's scope, not a promise to monitor. Communication, process
lifecycle, and management decisions remain with their respective owners. Other
skills may use this capability when useful, without a mandatory invocation chain.
