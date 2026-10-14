---
name: automata-pi-context-status
description: Use for interpreting Pi context-status signals or checking context pressure, elapsed time and model-token usage. Not for compaction or automatic task control.
---

# Automata Pi Context Status

Interpret telemetry from the installed context-status extension. This skill does
not measure context or emit signals; report unavailable diagnostics instead of
inventing readings. Call `context_status` only when a snapshot informs the next step.

1. **Read the fields correctly.** Usage is current tokens relative to the model
   window; pressure is its observational band. Elapsed is wall-clock time, not
   active effort, since the latest input anchor. Model usage aggregates provider-
   reported input/output/cache/total since that anchor. User-role inputs, including
   worker messages, reset it; tools, summaries and hidden signals do not. Runtime
   checkpoints are automatic, not something to create or inspect on every turn.

2. **Understand signal timing.** Before each model request, one temporary reminder
   appears at measured usage of at least 80%, with stronger urgency at 90%+. Below
   80% or with unknown readings, none appears. Repeated advice is not a newly crossed
   threshold; diagnostic bands are independent. Readings refresh after compaction,
   session/reload/model-window changes; unknown does not prove compaction succeeded.
   Old request-local reminders are replaced, not accumulated or used to start turns.
   Ten-minute elapsed observations coalesce at safe boundaries and queue after the
   run settles; neither path polls or injects into streaming output. Message timestamps
   are a separate extension, and no active/idle timer or timer integration is implied.

3. **Use observations as evidence.** Consider a safe compaction boundary without
   interrupting coherent work; follow compaction policy and preferences rather than
   treating pressure as an action request. Signals grant no delegation, stopping or
   ownership authority. Manual diagnostics report the same fields as signals; do
   not persist transient status or turn every signal into a user-facing reply.
