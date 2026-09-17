---
name: automata-timer
description: Use when scheduling a command, reminder, notification, agent check, or bounded recurring action after a delay or at a specific time.
metadata:
  automata-tools: .agents/tools/timer/timer.py
---

# Automata Timer

Use the repo-local timer tool to turn an explicit future action into a visible,
inspectable command. Keep the timer generic: it schedules commands but does not
decide higher-level workflow or guarantee that an agent session remains alive.

## Tool Discovery

The conventional tool path is:

```text
.agents/tools/timer/timer.py
```

Invoke this mapped entry directly without preflight directory scans or
unrelated-tool inspection. Inspect `--help` when its interface is not already
known:

```bash
uv run .agents/tools/timer/timer.py --help
```

If it is missing, offer to install the bundled tool. Confirm the target root and
install mode first; do not install or replace it silently.

```bash
automata tools install --target-root .agents/tools --tool timer
```

## Scheduling Judgment

Choose the smallest schedule matching the request:

- `after`: run once after a duration.
- `at`: run once at an ISO datetime.
- `every`: run repeatedly; `--max-runs` is required unless explicit
  `--forever` is used. `--until` is an optional cutoff, not a replacement for
  the run bound. Its default mode is `after-completion`; use `--mode
  fixed-rate` for a cadence anchored to the first scheduled run.
- `cron`: run on a five-field APScheduler crontab in a required IANA timezone,
  for example `--timezone Asia/Bangkok --max-runs 3`.

Before creating a timer, make the timing, command, target, and expected effect
clear. Ask when any of them is materially ambiguous. A timer executes with the
available local permissions, so require explicit confirmation for destructive,
privileged, externally visible, or unbounded actions.

Prefer named jobs when the timer may need later inspection or cancellation:

```bash
uv run .agents/tools/timer/timer.py after 20m \
  --name review-check \
  -- <explicit-command>
```

Do not use `--forever` without explicit approval and a cancellation and cleanup
plan.

### Recurrence and late runs

Use `--grace 30s` (or another positive duration) when a run should expire after
being late. A one-shot with a grace period is marked completed without running
once it is past that period; omitting `--grace` preserves the legacy behavior
of allowing a late one-shot to run. A recurring job with grace skips an
occurrence that is too late, without increasing its run count, and advances to
the next safe occurrence. Recurring schedules never replay a backlog.

`after-completion` schedules the next `every` run after the command finishes.
`fixed-rate` uses APScheduler's interval cadence from the first scheduled run;
long commands and delayed workers skip missed ticks rather than overlapping.
Cron schedules are calendar-cadenced and likewise skip missed occurrences.
Cron weekday names such as `mon-fri` are recommended: APScheduler 3.x numbers
Monday as 0, so numeric weekday fields do not use the usual Unix-cron meaning.

## Notifications and Responses

Treat notification transport and participant coordination as separate concerns.
First determine the explicit command that attempts the notification, then
schedule that command. Do not make the timer choose a transport, return path, or
participant topology.

A timer is not a coordinator watchdog by itself. It cannot wake the current chat
session merely by writing a log or evidence file. For user-facing coordination,
establish a supported notification path before launching asynchronous work; if
that path is unavailable, report it and use a bounded synchronous or otherwise
agreed alternative.

A scheduled notification proves only that its command was attempted. It does not
prove that a recipient is available, received the notification, or acted on it.
Likewise, a scheduled status request is not the resulting status. When a response
is expected, establish its return path through the communication mechanism that
owns that interaction before scheduling the request.

For important checks, use the timer log to verify command execution, then expect
the response through its agreed path. Diagnose a missing or unhealthy response
through the workflow that owns that communication, not by turning timer polling
into the successful response path.

When a matching response or timer execution notice arrives, cancel or refresh
that job before the next coordination step. Cancel pending jobs when the reason
for them no longer applies, and avoid stale or duplicate checks.

## Inspection and Cleanup

Use visible state instead of assuming a timer ran:

```bash
uv run .agents/tools/timer/timer.py status
uv run .agents/tools/timer/timer.py logs <job-id-or-name>
uv run .agents/tools/timer/timer.py cancel <job-id-or-name>
```

Cancel obsolete pending or recurring jobs. Cancellation requests stop future runs and
signal the identified command; `canceling` means shutdown is not yet confirmed. The
worker exits cooperatively rather than being killed while writing evidence. Cancellation
preserves records and logs; it does not roll back command side effects.

When a timer completes, is canceled, or fails, its records become eligible for retention
review, not automatic deletion. Preserve evidence still needed for verification. Remove
records only under the owner's agreed retention/removal policy or explicit scoped
approval; do not ask or scan after every timer use. Age alone does not establish that
evidence is disposable. For approved cleanup:

```bash
uv run .agents/tools/timer/timer.py cleanup <job-id-or-unique-name>
uv run .agents/tools/timer/timer.py cleanup --older-than 7d
uv run .agents/tools/timer/timer.py cleanup --all
```

Choose exactly one selector. With no selector, cleanup defaults to terminal records
older than seven days. Cleanup permanently removes job records, per-job locks, and
logs, never implicitly cancels active work, and refuses unconfirmed process shutdown
or an active worker/executor lease. Batch cleanup reports skipped records. One shared
state lock remains intentionally to coordinate future operations safely.

An unavailable or changed process identity prevents cancellation from signaling that
process; inspect the reported blocker rather than forcing deletion. Process identity
verification currently uses Linux `/proc`. Do not replace the tool under active older
workers and assume they participate in the new locking protocol; let those jobs finish
and verify their processes have exited before cleanup.

Keep runtime state in a location appropriate to this skill and separate from
installed tool code.

## Boundaries

- Do not treat the timer as a workflow orchestrator, durable queue service, or
  guarantee of agent availability.
- Do not hide long-running scheduler loops; use an explicitly managed terminal
  session when one is needed.
- Do not schedule vague natural-language intentions without translating them
  into a concrete, reviewable command.
- Do not choose notification transports, hardcode participant topology, or
  duplicate communication coordination guidance.
- Do not install tools, replace existing tools, or create unbounded schedules
  without confirmation.
