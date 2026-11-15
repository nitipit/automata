# Progress Reports

Keep substantial work understandable through a compact status view, not a transcript.
Use this structure by default when it helps the user follow the work; shorten it
when fields add no value. Small tasks can use a brief result instead.

## Report structure

Present the following in order:

1. **Project or goal.** Identify the work being reported, not just the current tool.
2. **Status, reporter and update time.** Name the actual reporter and include the
   timezone or UTC offset. Make the status understandable without color alone:
   - 🟦 Progress: work is underway.
   - 🟧 Caution: a risk or uncertainty needs attention, but work can proceed without
     user action. Explain the consequence rather than merely changing the marker.
   - 🟥 Blocked: work cannot proceed. Name the obstacle and what or who can unblock
     it; ask the user only when their action is needed.
   - 🟩 Finished: the reported scope is complete and checked. Do not hide partial
     results, unresolved errors or unchecked work behind a finished status.
3. **Target finish.** Give an estimated time or range, with its timezone. At completion,
   replace the target with actual finish time. If a finish estimate is not yet useful,
   say it is unknown and identify the next evidence needed to estimate it.
4. **Short summary.** State meaningful progress, a changed expectation or the specific
   action needed. Do not make the user infer a blocker from task rows.
5. **Task progress.** Use a few coherent milestones, not a tool-call checklist. Put
   the status before each task number: ⬜ todo, 🔄 in progress, ✅ done. Show elapsed
   time versus estimated duration for active or completed tasks; todo uses
   `— / <estimate>`. Keep stable task identities between updates when practical.
6. **Overall elapsed time.** Put wall-clock duration last, measured from the actual
   work start. Include waits; distinguish active effort separately if useful. Never
   sum parallel workers' durations into overall elapsed time.

## Illustrative layout

These placeholders are not live progress or measured times:

```text
<project / goal>
🟦 <reporter> · Updated <time + zone>
Target finish: <time or range + zone>
<short progress summary or action needed>
✅ 1. <task> · <elapsed> / <estimate>
🔄 2. <task> · <elapsed> / <estimate>
⬜ 3. <task> · — / <estimate>
Elapsed: <overall wall-clock duration>
```

## Keep reports honest and useful

- Use observed start and finish data. Mark missing measurements or estimates as
  unknown; never substitute example values or claim a complete team total from
  partial evidence. Revise targets when evidence changes and explain material drift.
- Report blockers and completion promptly. During ongoing work, report meaningful
  changes and honor an agreed cadence; if nothing changed, say so rather than invent
  progress. A reporting promise does not establish a background wake or delivery path.
- Keep the status view short. Detailed plans, roles, logs, checks and recovery notes
  belong in the relevant discussion or task record, not in every progress update.
  Close with deliverables, checks and limitations; a finished marker is not evidence
  of live verification, user acceptance or permission for further action.
