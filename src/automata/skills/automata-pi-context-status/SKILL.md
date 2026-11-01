---
name: automata-pi-context-status
description: Use for interpreting compaction planning notices or checking projected Pi context usage and working model. Not for executing compaction.
---

# Automata Pi Context Status

`context_status` and `/context-status` report projected context tokens, window,
working provider/model and the compaction planning threshold. Pi's projection is
not an exact final provider payload. Use a manual snapshot only when it informs
the next step; report missing capability rather than inventing readings.

At the model's configured used-token threshold, one temporary planning notice is
included in each request while usage stays at or above it. Immediately insert a
compaction break into the current work plan: finish the small in-flight step,
preserve continuity, compact at the nearest suitable boundary in the coming turns,
then resume. Do not start another substantial work unit or large input first.
This requires planning now, not interrupting an operation to compact immediately.
The extension never calls compaction, changes Pi settings or wakes an idle agent.
Pi auto-compaction remains the guardrail. There are no token-bucket notices,
pressure bands or percentage urgency rules. Unknown usage or an unconfigured model
produces no planning notice; a successful compaction has unknown usage until Pi
gets fresh usage evidence. Notices are request-local, never accumulated in history.
Threshold values have one owner: `COMPACTION_PLANNING_TOKENS` in `context-status.ts`;
the tool reports the active value. Changing thresholds needs approval.

For elapsed time and model usage since the latest user-role input, use the separate
on-demand `activity_usage` tool when relevant. Elapsed is not active effort or
whole-task duration. Do not persist transient observations or report every notice
to the user; communicate the chosen compaction break briefly.
