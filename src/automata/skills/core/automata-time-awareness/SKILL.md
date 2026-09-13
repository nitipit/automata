---
name: automata-time-awareness
description: Use when current time, elapsed time, relative dates, deadlines, time zones, pauses, or resumed work materially affect reasoning.
---

# Automata Time Awareness

Treat time as context when it can change the meaning or correctness of the next step. Do
not read the clock on every turn.

## Refresh Time

Refresh local time immediately before reasoning when:

- the answer depends on the current date or time;
- work resumes after a meaningful pause or spans a long interval;
- the user uses relative dates such as “today”, “tomorrow”, or “recently”;
- a deadline, appointment, or elapsed duration affects the decision.

Use:

```bash
date --iso-8601=seconds
```

Treat the returned local ISO 8601 timestamp, including its offset, as the current time
context. Preserve that timestamp when reporting time; do not append a separate UTC label.

## Interpret Time

- Resolve relative dates against the refreshed local timestamp.
- State the assumed date or offset when an interpretation could be ambiguous.
- Ask for clarification when the user's timezone or date materially changes the outcome.
- When measuring elapsed work, capture a fresh timestamp at the relevant start or resume
  point instead of inferring duration from turns or token usage.

## Scheduling Boundary

Use the `automata-timer` skill for reminders, scheduled commands, and recurring actions. Do
not simulate a timer by repeatedly checking the clock or by making an unconfirmed future
commitment.

## Boundaries

This skill provides temporal context for reasoning. It does not schedule actions, invent
user deadlines, infer a preferred timezone without evidence, or make time-sensitive actions
without the normal authorization and confirmation boundaries.
