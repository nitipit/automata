---
name: automata-pi-context-status
description: Use for interpreting Pi context-status observations or checking current context pressure and working model. Not for compaction or automatic task control.
---

# Automata Pi Context Status

`context_status` and `/context-status` report current projected context tokens,
window, pressure and working provider/model. Pi's projection is not an exact final
provider payload. Use a snapshot only when it informs the next step; report missing
capability rather than inventing readings.

Before a request, a temporary observation reports current usage when it enters a
new 50,000-token bucket. It is an at-most-once attempt, not a delivery guarantee:
a failed or aborted request does not re-arm it. Downward fluctuation does not
re-arm it; confirmed compaction, session/tree changes, reload or model/window
identity change do. Unknown usage is not evidence of successful compaction.
At 80% or more a reminder recurs on each request, with stronger urgency at 90%.
Observations never themselves authorize compaction, delegation or stopping work.

For wall-clock elapsed and model usage since the latest user-role input, use the
independent `activity_usage` tool or `/activity-usage` command. Elapsed is not
active effort; ten-minute observations coalesce and queue after settlement without
waking the agent. Queued observations are historical snapshots, identified by their
observation time and input anchor; they may precede the current input. This is the
replacement for the former context-status telemetry
fields. Message creation timestamps and active-branch cumulative token counts are
separate extensions. Do not persist transient observations or report every one to
the user.
