---
name: automata-context-compaction
description: Use when an agent or user is considering intentional Pi context compaction after context-pressure observations, long-running work, or a stable task boundary.
---

# Automata Context Compaction

Choose when to compact and preserve continuation state. Pi owns summarization
and automatic compaction; `context_compact` handles deferred execution.

## When to compact

Request intentional compaction only when measured context usage exceeds 75%.
If usage is unknown or compaction just succeeded, obtain a fresh measurement
showing usage above 75%. Time, long output, or a new work phase alone is not enough.

Pressure sets urgency and task boundaries determine timing:

- Above 75%, when meaningful work remains, finish the current coherent unit and
  compact automatically at the next stable boundary, before substantial new work.
- At ≥90%, preserve the minimum safe checkpoint and compact at the earliest safe
  boundary rather than waiting for a perfect milestone.

A stable boundary leaves decisions settled, edits coherent, and ownership and
pending evidence recorded. Briefly announce the intent without asking for per-use
confirmation; a pressure signal alone is not a command to compact.

## Preserve continuation

Bring existing, authorized task state current: goal, constraints, decisions,
validation, ownership, pending evidence, cleanup obligations, blockers, relevant
worktree changes, and the next action. Record only missing continuation details,
not transcripts, raw traces, or secrets.

Do not create records solely for compaction or broaden persistence without
approval. Do not mark unfinished work complete: compaction does not finish,
accept, cancel, or transfer active work.

## Request and finish

Once preservation is complete and the turn can end, call `context_compact` as the
sole final tool action when practical. It invokes native compaction only after
`agent_settled`; leave queueing, duplicate protection, and notifications to the tool.

Keep optional `customInstructions` to brief focus notes, not a hand-written
summary or a substitute for durable state. Pi generates the summary.

After failure or cancellation, do not retry automatically. Preserve the checkpoint
and reassess on the next turn; retry only when still useful and the cause is
understood. If another compaction satisfies the request, do not repeat it.

## Boundaries

Do not route `/compact` through tmux or inject it as a user message. Humans can
use `/compact` directly. This skill does not change Pi settings, measure context,
or make compaction a completion requirement.
