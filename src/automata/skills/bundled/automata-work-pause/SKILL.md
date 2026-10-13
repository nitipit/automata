---
name: automata-work-pause
description: Use for pausing work for later continuation or preparing for shutdown. Not for completion, cleanup or abandoning a task.
---

# Automata Work Pause

Stop activity while preserving resumability. Minimize actions, not just the reply.

1. **Stop safely.** Start no new work. Stop active owned operations/workers at the
   nearest safe boundary; do not finish milestones just to tidy the pause. Idle
   workers need no new assignment. Suspend task-owned reporting/watchdog triggers,
   leaving unrelated services/reminders alone. Use known ownership and only checks
   needed to stop and confirm; do not rediscover or audit. Report activity that cannot
   stop safely or has an uncertain outcome.

2. **Preserve what already exists.** Leave sessions idle and files intact. If shutdown
   requires exiting, retain saved history. Existing sessions/artifacts are the default
   resume record; do not rewrite plans or create checkpoint documents by default.
   Save only essential otherwise-lost recovery details with their owner; volatile
   memory alone is insufficient. Minimal state changes to keep mechanisms paused
   do not justify duplicate records.

3. **Wait for explicit resume.** Pausing authorizes no tests, reviews, acceptance,
   commits, backups or deletion. Preserve late results without follow-up; callbacks
   and old deadlines grant no resumption authority. Briefly confirm the pause and
   material remaining stop/recovery gaps, then wait for the user or authorized owner.
