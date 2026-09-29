---
name: automata-context-compaction
description: Use when an agent or user is considering intentional Pi context compaction after context-pressure observations, long-running work, or a stable task boundary.
---

# Automata Context Compaction

Choose when to compact, preserve continuity and request deferred native summarization
through `context_compact`. Pi owns automatic compaction; do not change its settings
without approval or make compaction a task-completion requirement.

## When to compact

Default to a trigger above 75% measured usage and an urgent threshold of 90%, unless
approved preferences override them. Pressure is an observation, not a command.

- Above the trigger with meaningful work remaining, finish the coherent unit and
  compact at the next stable boundary before substantial new work.
- At or above the urgent threshold, preserve the minimum safe checkpoint and
  compact at the earliest safe boundary.
- Unless the user explicitly requests compaction, unknown usage or a just-completed
  compaction requires a fresh measurement above the trigger. Time, long output or
  a new phase alone is insufficient.

A stable boundary leaves edits coherent, decisions settled, and ownership and
pending evidence recorded. Briefly announce the action; no per-use approval or
setup questionnaire is needed within these rules.

## Select model and thinking

Apply explicit current instructions, then project preferences, global preferences,
and finally session defaults. Consult existing preferences at:

- Project: `.agents/var/skills/automata-context-compaction/preferences.md`
- Global: `~/.agents/var/skills/automata-context-compaction/preferences.md`

Pass a selected `model` as `provider/model`. Omission captures the current model
when queued. Pass an explicit `thinking` level when selected: `off`, `minimal`,
`low`, `medium`, `high`, `xhigh` or `max`. Omission inherits the session level at
execution; an explicit level remains attached to the request. Provider/model
support still applies. Neither argument changes working-session settings.

For example, `model: "openai-codex/gpt-5.6-luna", thinking: "medium"` selects
Luna/medium for the summary only. Do not silently replace an invalid preference.
The tool checks model availability/authentication; selection or summary failure
never triggers fallback. Initially defaulting to the current model is not fallback.
Context-budget preflight is heuristic, not a guarantee against provider overflow.

For customization of models, thresholds or saved defaults, read
[Compaction preferences](references/preferences.md). One-off choices need no
preference file. Saved preferences guide explicit tool arguments, not Pi automatic
compaction or the tool's omitted-argument behavior.

## Preserve continuity

Update existing authorized task state with missing goal, constraints, decisions,
validation, ownership, pending evidence, cleanup obligations, blockers,
unfinished work and next action. Avoid transcripts, raw traces or secrets; do not
create records solely for compaction or broaden persistence without approval.

Supply brief `customInstructions` identifying what must survive, not a replacement
summary or substitute for durable state. The working model provides guidance;
the selected model summarizes. Guidance reaches every native summary request,
including split-turn summaries, without an extra summary call.

## Request and continue

When authorized work remains, pass a brief `resumeMessage` for the next action.
It guides continuation, not summarization; do not create another wakeup path.
Omit it when no work remains. Whitespace-only text also means compact-only;
nonblank text is preserved verbatim.

After success, the tool may dispatch one wakeup for the unchanged session. If other
work intervenes or the session is busy, guidance becomes non-triggering `nextTurn`
context instead. Failure, cancellation or session changes do not trigger
continuation. Fire-and-forget dispatch does not prove delivery or resumed work.

Once preservation is complete and the turn can end, call `context_compact` as the
sole final tool action when practical. It runs after the agent settles; the tool
owns queueing, duplicate protection and notifications. If another compaction
satisfies the request, do not repeat it.

After failure or cancellation, keep the checkpoint and reassess on the next turn.
Do not retry automatically; retry only when useful and the cause is understood.
Compaction does not complete, accept, cancel or transfer work. Resume only the
existing authorized assignment. Never inject `/compact` through tmux or as a user
message; humans may use it directly. This skill does not measure context or change
Pi settings.
