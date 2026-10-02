---
name: automata-work-pause
description: Use when work needs to pause for later continuation, including requests to stop for now or prepare for computer shutdown without abandoning the task.
---

# Automata Work Pause

Stop task activity while preserving its existing resumable state. A pause is not
completion, abandonment, cleanup, or a formal handoff. Minimize actions, not just
confirmation length.

## Stop the Activity

Stop starting new work. For active operations and owned workers, use the available
stop mechanism at the nearest safe boundary. An already idle worker needs no new
assignment. Do not finish a milestone merely to make the pause look tidy.

Suspend task-owned triggers that would continue the work, including its reporting
and watchdog timers. Leave unrelated services and reminders alone. Use known
ownership records with only the checks needed to target and confirm the stop;
do not rediscover the environment or audit the task. If something cannot stop
safely, report the remaining activity or uncertain outcome rather than claiming
it stopped.

Keep existing agent sessions and files. For an ordinary pause, leave the agent
session open but idle by default. If shutdown requires exiting a process, retain
its saved session for later continuation; stopping a process is not deleting its
history.

## Preserve Only What Is Missing

Retained session context, existing files, and received results are the default
resume record. No checkpoint-document updates by default. Do not rewrite plans,
resume documents, or task summaries merely because work is pausing.

Add recovery information only when essential information would otherwise be lost
and is not already recoverable from retained sessions or artifacts. Put the
smallest necessary note with its existing owner; do not create a new checkpoint
system. Saved session context is sufficient; volatile process memory alone is not.
A small operational-state update is appropriate when a mechanism needs it to
remain paused, not as a reason to duplicate state across documents.

## Boundaries

Do not run tests, review results, accept work, commit, back up, or delete resources
as part of pausing. Preserve late results without starting follow-up work. A late
callback or old deadline does not authorize resuming the paused task; wait for an
explicit resume instruction from the user or authorized task owner.

Confirm the pause briefly, naming only material unfinished stop actions or recovery
gaps. Then wait. Do not expand a simple pause into a handoff or maintenance task.
