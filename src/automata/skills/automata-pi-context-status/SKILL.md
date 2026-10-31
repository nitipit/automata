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
independent, on-demand `activity_usage` tool or `/activity-usage` command when time
or usage matters, not routinely after every action. Elapsed is not active effort
or whole-task duration: a new user-role input resets the checkpoint. Session/tree
changes reset it too; compaction preserves it. No activity observations are sent
automatically. Message creation timestamps are a separate extension. Do not persist
transient context observations or report every one to the user.
