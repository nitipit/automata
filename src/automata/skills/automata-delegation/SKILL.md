---
name: automata-delegation
description: Use for assigning work across agents, processes or working contexts, managing handoffs, receiving results and recovering missing delegation evidence.
---

# Automata Delegation

Hand off bounded work with clear ownership, a usable return path and evidence for
acceptance. Task approval alone does not authorize unrestricted delegation.

1. **Confirm authority and ownership.** Get an approved user/parent delegation
   envelope. Launch, replace or rebalance within it without per-worker approval;
   ask before exceeding it. Resolve model and supported effort choices before
   dispatch. Use native launch controls and verify actual settings, not just flags;
   report mismatches rather than silently substituting. Later changes need supported
   human controls or relaunch, not an assumed worker-side setter.

2. **Brief the work.** Define the goal, owner, scope, working directory, applicable
   instructions, allowed effects, checks and completion evidence. Include stopping,
   escalation and cleanup conditions, plus the next meaningful evidence and deadline.
   Provide essential task facts and accessible pointers, not the whole conversation.
   Keep durable policy in `AGENTS.md`; limit discovery to authorized paths. If the
   worker needs broad unrelated context, reconsider the assignment boundary.

3. **Establish the return path.** Verify exact worker and coordinator targets,
   transport and lifecycle ownership. Choose a return-capable method suited to
   interaction needs and resource costs, or bounded synchronous execution. Pause
   if the path is missing, stale or unreachable.
   Before asynchronous dispatch, establish a real callback wake path and one bounded
   coordinator-targeted watchdog for the next evidence, with task correlation.
   Logs and artifacts do not wake the coordinator; a message to a stuck worker is
   not a coordinator wake-up. Synchronous returns need no communication watchdog;
   process/time limits are separate safety backstops.

4. **Dispatch, yield and review.** Send work once. End the turn when no independent
   work remains; the session stays available for callbacks. Do not wait through
   sleeps or repeated pane, process or artifact checks. Assess callbacks or fallback
   notices, not activity alone. Choose milestones by risk, duration and dependencies;
   require meaningful updates, not periodic activity. Review results before acceptance.
   Preserve correlation and completion evidence until acceptance or abandonment so
   results can be resent through the agreed path. Cancel or re-arm watchdogs as
   expectations change; late results do not authorize resuming paused work.

5. **Update or recover safely.** Relay accepted decisions as bounded updates with
   the same correlation, revised evidence and ETA. Never edit worker-owned files
   concurrently. For transfers, preserve partial work, resolve outstanding effects
   and verify the new owner's context and return path before releasing the old owner.
   Align callback, watchdog and cleanup ownership; launching a replacement alone
   does not complete a transfer. For overdue evidence or delivery failure, read
   `references/missing-evidence.md`; diagnose only owned resources without busy-polling.
   Replace unsafe wake paths before removing still-needed coverage. Do not silently
   leave active work unwatched.

This skill owns handoff and acceptance. Work design, planning, management, models,
transport, terminal lifecycle and timers retain their own decisions and mechanisms.
