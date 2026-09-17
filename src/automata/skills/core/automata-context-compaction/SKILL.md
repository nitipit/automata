---
name: automata-context-compaction
description: Use when an agent or user is considering intentional Pi context compaction after context-pressure observations, long-running work, or a stable task boundary.
---

# Automata Context Compaction

Choose when to compact, preserve continuation state, and request deferred native
summarization through `context_compact`. Pi owns automatic compaction; leave its
settings unchanged unless the user approves a change.

## Timing and defaults

Use a default trigger above 75% measured context usage and an urgent threshold
of 90%; substitute approved preferences when present. Do not initiate a setup
questionnaire.

- Above the trigger, when meaningful work remains, finish the current coherent
  unit and compact at the next stable boundary before substantial new work.
- At or above the urgent threshold, preserve the minimum safe checkpoint and
  compact at the earliest safe boundary.
- If usage is unknown or compaction just succeeded, obtain a fresh measurement
  above the trigger before requesting another compaction. Time, long output, or
  a new work phase alone is not enough.

A stable boundary leaves edits coherent, decisions settled, and ownership and
pending evidence recorded. Briefly announce compaction without asking for per-use
confirmation; pressure alone is not a command to compact.

## Model and preferences

Choose the summarization model from the explicit selection for this request,
then an approved compaction preference, otherwise the current working model.
Pass a selected preference as `provider/model`; omit `model` to capture the
current model at queue time without interrupting work to ask. Explicitly choosing
the current model is also allowed. Never silently replace an invalid preference.

The tool validates runtime model availability and authentication without changing
the working model or thinking setting. Its context-budget preflight is a heuristic,
not a fit guarantee: provider overflow remains possible. Selection or summary
failure stops the operation; it does not fall back to another model. Defaulting
to the current model initially is not fallback.

When the user requests customization, verify provider/model/thinking using
`automata-runtime-status`, then inspect runtime-advertised context limits of both
models and effective Pi compaction settings. Discuss cost, summary quality,
input/output headroom, and whether a smaller summarizer needs earlier compaction.
Validate thresholds as percentages with 0 < trigger < urgent < 100. Resolve invalid
or conflicting choices rather than silently replacing them.

Persist preferences only with approval for future use, in a suitable skill-owned
data location following `automata-agent-data` and the approved project/global
scope. Read existing preferences before defaults; precedence is explicit current
instructions, project preferences, global preferences, then defaults. One-off
choices need no preference file. Do not invent a Pi compaction-model setting.
Recheck changing runtime facts rather than storing them as permanent preferences;
revisit approved choices only when their suitability materially changes.

## Preserve and guide

Bring existing authorized task state current: goal, constraints, decisions,
validation, ownership, pending evidence, cleanup obligations, blockers, relevant
worktree changes, and next action. Record missing continuation details, not
transcripts, raw traces, or secrets. Do not create records solely for compaction
or broaden persistence without approval.

Supply brief `customInstructions` highlighting what must survive. The working
model provides this handoff; the selected model generates the summary. Do not
write a full replacement summary or use guidance instead of necessary durable
state. The tool applies guidance to every native summary request, including
split-turn summaries, without an extra summary call.

## Continue and finish

When authorized work remains, pass a brief `resumeMessage` describing the next
action. It guides continuation, not summarization. Do not arrange another wakeup
path. Omit it when no work remains; empty or whitespace-only text also means
compact-only behavior. Nonblank text is preserved verbatim.

After successful compaction, the tool can dispatch one wakeup for the unchanged
session. If other work intervenes or the session is busy, it instead retains the
guidance as non-triggering `nextTurn` context; this does not itself resume work.
Failure, cancellation, or session changes do not trigger continuation. Messaging
is fire-and-forget, so dispatch is not proof of delivery or resumed work.

Once preservation is complete and the turn can end, call `context_compact` as the
sole final tool action when practical. It runs after the agent settles; leave
queueing, duplicate protection, and notifications to the tool.

After failure or cancellation, preserve the checkpoint and reassess on the next
turn. Do not retry automatically; retry only when useful and the cause is
understood. If another compaction satisfies the request, do not repeat it.

Compaction does not complete, accept, cancel, or transfer active work. Resume only
the existing authorized assignment. Do not route `/compact` through tmux or inject
it as a user message; humans can use it directly. This skill does not measure
context, change Pi settings, or make compaction a completion requirement.
