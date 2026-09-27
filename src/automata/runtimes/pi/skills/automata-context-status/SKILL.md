---
name: automata-context-status
description: Use when interpreting runtime context signals or checking context pressure, elapsed time, or model-token usage.
---

# Automata Context Status

The runtime silently creates a task checkpoint at the start of a user-driven agent run.
It anchors time and model-usage telemetry to the latest Pi input message, including
coordinator or subagent inputs delivered as `role: "user"` messages. The agent does not
create or inspect that checkpoint automatically.

`context_status` remains an optional manual diagnostic. Use it only when a status snapshot
would inform the next step; do not call it merely to acknowledge a new run or signal.

## Runtime observations

- Each model request includes a temporary runtime-local ISO 8601 timestamp with timezone.
  It observes time before that request, not task start or exact completion. It is not saved
  to session history and does not reset the input anchor or accumulate timestamp messages.
- Time is wall-clock elapsed since the latest input message. There is no active/idle timer
  distinction and no `automata-timer` integration.
- Assistant messages contribute provider-reported input, output, cache, and total usage after
  the latest input anchor. Tool results, hidden signals, summaries, and other non-input entries
  do not reset the anchor.
- Before each model request, the runtime checks pressure and injects a temporary reminder
  at 75%, 80%, 85%, 90%, and 95%; the 50% moderate-pressure observation is also retained.
  A jump produces one current reminder, not a backlog of crossed thresholds. The first
  request after loading can report pressure already above a threshold.
- Pressure reminders are deduplicated across user inputs. Successful compaction, session
  changes, reload, or a changed effective model/window rearm them; ordinary fluctuations,
  unknown readings and failed/cancelled compaction do not. Unknown usage produces no reminder.
  These request-local messages do not accumulate in session history or start agent turns.
- Ten-minute elapsed-time observations still coalesce at safe runtime boundaries and are
  queued after the run settles for a subsequent turn. Neither signal path polls or injects
  into a streaming response.
- `context_status` reports the same context, pressure, elapsed-time, input-anchor, and model-
  usage fields that appear in runtime signals.

## Read status

- **Usage** is current tokens relative to the model context window.
- **Pressure** is the observational band derived from context percentage.
- **Elapsed** is wall-clock time since the latest input anchor.
- **Anchor** is the local timestamp used for elapsed time and usage aggregation.
- **Model** is provider-reported usage accumulated since that anchor.

## Signal received

A hidden context signal provides factual status and the threshold that triggered it.
High-pressure reminders call attention to a stable compaction boundary; at 90%+ they express
stronger urgency. They do not run compaction or replace its applicable policy and preferences.
Decide the next safe action from the task and that guidance, without interrupting unfinished
operations or treating an observation as new authority.

Signals do not automatically delegate, stop, or change ownership. Delegation still requires
the assigned caller or owner's approval and return path.

## Boundaries

This skill does not measure context, create checkpoints, emit signals, compact, delegate, or
persist transient status. It does not turn every signal into a user-facing reply or require a
fixed response sequence. Manual `context_status` use is optional and diagnostic only.
