---
name: automata-context-status
description: Use when an agent begins implementation work or receives a runtime context signal.
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
- The runtime evaluates ten-minute time thresholds and the 50%, 75%, and 90% pressure bands at
  safe runtime boundaries, without polling or mid-stream injection.
- `context_status` reports the same context, pressure, elapsed-time, input-anchor, and model-
  usage fields that appear in runtime signals.

## Read status

- **Usage** is current tokens relative to the model context window.
- **Pressure** is the observational band derived from context percentage.
- **Elapsed** is wall-clock time since the latest input anchor.
- **Anchor** is the local timestamp used for elapsed time and usage aggregation.
- **Model** is provider-reported usage accumulated since that anchor.

## Signal received

A hidden context signal provides factual status and the change that triggered it. It is not a
request, command, or ownership change. Use the included status and evidence to understand the
current runtime context; decide any next action from the task and other applicable guidance.

Signals do not automatically delegate, stop, or change ownership. Delegation still requires
the assigned caller or owner's approval and return path.

## Boundaries

This skill does not measure context, create checkpoints, emit signals, compact, delegate, or
persist transient status. It does not turn every signal into a user-facing reply or require a
fixed response sequence. Manual `context_status` use is optional and diagnostic only.
