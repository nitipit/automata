---
name: automata-pi-context-compaction
description: Use for deciding when to compact Pi context, preserving continuity and requesting deferred native summarization through context_compact.
---

# Automata Pi Context Compaction

Use the exposed `context_compact` extension; installation alone does not expose it.
Report missing capability rather than injecting `/compact` or inventing a call.
Pi owns automatic compaction; changing its settings needs separate approval.

1. **Choose a safe boundary.** Assess remaining work and expected large inputs,
   the value of active evidence versus stale history, and both the working model's
   and summarizer's input/output headroom. Finish coherent edits and preserve
   ownership and pending evidence before compacting; do not interrupt an operation.
   Model-specific preferences are advisory ranges, not hard triggers. Without an
   applicable preference, above 75% consider compaction when meaningful work remains;
   at 90% preserve a minimal checkpoint and seek the earliest safe boundary.
   Runtime limits are authoritative, and summarizer headroom can require earlier
   action. Pressure is advice, not a command. Unknown usage, elapsed time or a new
   phase alone is insufficient; after compaction require fresh evidence of material
   benefit before another attempt. Briefly announce; do not compact just to finish.

2. **Use approved selections.** Apply current instructions, project preferences,
   global preferences, then session defaults. Existing paths remain:
   - `.agents/var/skills/automata-context-compaction/preferences.md`
   - `~/.agents/var/skills/automata-context-compaction/preferences.md`
   Do not migrate these paths for the skill rename. Pass `model` as `provider/model`;
   omission captures the current model when queued. Explicit `thinking` accepts
   `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`; omission inherits session
   effort at execution. Provider support applies; neither changes working settings.
   Invalid selections or summary failures never authorize fallback. Budget preflight
   is heuristic. Read `references/preferences.md` for customization; one-off choices
   need no file and saved preferences do not change automatic compaction.

3. **Preserve continuity.** Update existing authorized task state with goals,
   constraints, decisions, checks, ownership, pending evidence, cleanup, blockers
   and next actions. Keep the handoff brief and focused on future work, not a full
   archive of completed work. Do not save transcripts/secrets or create records just
   for compaction. Use brief `customInstructions` for essential continuity guidance,
   not a replacement summary; it reaches every native summary request.

4. **Queue and continue.** Use `resumeMessage` only for remaining authorized work;
   omit it when finished. Nonblank text is preserved; whitespace means compact-only.
   It guides continuation, not summarization. The tool may wake an unchanged idle
   session once; intervening work makes it non-triggering next-turn context.
   Failure/cancellation/session changes do not wake it, and dispatch proves no resume.
   Call as the sole final tool action when practical; the tool owns deferred queueing,
   duplicate protection and notifications. Do not repeat a satisfied request or
   automatically retry failure. Keep the checkpoint and reassess the cause.

Compaction does not complete, accept, cancel or transfer work. Resume only existing
assignments; do not create another wake path or change Pi settings.
