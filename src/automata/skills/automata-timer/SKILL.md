---
name: automata-timer
description: Use for scheduling concrete commands, reminders, notifications or bounded recurring checks after a delay or at a time. Not for choosing workflow or notification transport.
metadata:
  automata-tools: .agents/tools/timer/timer.py
---

# Automata Timer

Schedule explicit commands with visible state. Timers guarantee neither agent
availability nor recipient handling; they are not a workflow orchestrator or queue.

1. **Use the installed tool.** Invoke `.agents/tools/timer/timer.py` directly; consult
   `uv run .agents/tools/timer/timer.py --help` when needed, not unrelated scans.
   Missing tools need approved installation root/mode, for example
   `automata tools install --target-root .agents/tools --tool timer`.

2. **Choose bounded timing.** Make command, target, timing and effects clear; clarify
   meaningful ambiguity. Destructive, privileged, external or unbounded effects need
   explicit authority. Commands are concrete, not vague intentions:
   - `after`: one run after a duration; `at`: one run at an ISO datetime.
   - `every`: repeat with required `--max-runs` unless approved `--forever` is used.
     `--until` is an optional cutoff, not a run bound. Default `after-completion`
     waits after command completion; `--mode fixed-rate` anchors cadence to first run.
   - `cron`: five-field APScheduler crontab with required IANA `--timezone` and bounds.
     Prefer weekday names: APScheduler 3.x uses Monday=0, unlike Unix cron.
   Name jobs for later inspection/cancellation; unbounded jobs need stop/cleanup plans.
   ```bash
   uv run .agents/tools/timer/timer.py after 20m --name review-check -- <command>
   ```
   Positive `--grace` expires late one-shots without execution; omission allows late
   one-shots. Late recurring occurrences skip without incrementing run count and
   never replay backlog or overlap. Cron and fixed-rate skip missed ticks.

3. **Establish notification paths.** Schedule an authorized transport command, not
   choose participants or routes. Logs alone cannot wake a coordinator; establish
   supported delivery and return paths before asynchronous work or agree on a bounded
   alternative. Execution/dispatch is not delivery, response or action. Verify logs
   for execution and receive replies through their owner, not timer polling. Cancel
   or refresh stale checks when matching evidence arrives or their reason ends.

4. **Inspect and cancel precisely.** Use `status`, `logs <job-id-or-name>` and
   `cancel <job-id-or-name>` through the same tool. Cancellation stops future runs
   and signals the identified command cooperatively; `canceling` is not confirmed
   shutdown. Records/logs remain and effects are not rolled back. Identity failures
   need diagnosis, not forced deletion. Linux `/proc` verifies process identity;
   do not replace the tool under older active workers and assume new lock cooperation.

5. **Retain or clean with authority.** Terminal records are review candidates, not
   automatic deletion. Preserve useful evidence; use approved retention/removal policy.
   `cleanup` accepts exactly one selector: job ID/unique name, `--older-than 7d` or
   `--all`; no selector defaults to terminal records older than seven days. It
   permanently removes records, per-job locks and logs, never cancels active work,
   and refuses unconfirmed shutdown or active worker/executor leases. Batch skips
   are reported; the shared state lock intentionally remains. Keep runtime state
   outside installed code. Managed scheduler loops must not be hidden.
