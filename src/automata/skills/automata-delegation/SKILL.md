---
name: automata-delegation
description: Use for choosing solo/team arrangements, assigning bounded work, coordinating workers, reviewing results or recovering a handoff. Not for runtime-specific launch commands or adopting a dedicated manager role.
---

# Automata Delegation

Own delegation from work division through evidence-based acceptance. Delegating
some work does not require becoming a dedicated manager or giving up implementation.

1. **Choose a useful arrangement.** Compare solo work and delegation against the
   same goal, quality, time and risk constraints. Weigh parallelism and independent
   review against briefing, duplicated context, handoffs and integration. Keep
   coupled knowledge together and give workers coherent, verifiable outcomes, not
   arbitrary file slices. Small tasks need no formal team-design document. For
   consequential work division or review choices, consult
   [team design](references/team-design.md).

2. **Bound authority and resources.** Get an approved user/parent envelope covering
   scope, worker limits, allowed effects and model/effort choices. Task approval
   alone is not unrestricted delegation. Verify effective supported settings through
   the runtime rather than trusting launch flags; do not silently substitute.
   Launch, replace or rebalance within the envelope without per-worker approval;
   ask before exceeding it. Capacity and peer messages grant no extra authority.

3. **Brief and assign ownership.** Include the goal, owner, CWD, applicable
   instructions, scope, allowed effects, checks and completion evidence. Define
   stopping/escalation conditions, lifecycle and cleanup ownership, and the next
   meaningful evidence and deadline. Provide essential facts and accessible pointers,
   not a copied conversation. Limit discovery to authorized paths; durable policy
   belongs in `AGENTS.md`, not task briefs. Never allow concurrent conflicting edits.

4. **Establish the return path.** Verify exact worker/coordinator targets, transport
   and lifecycle ownership before dispatch. Asynchronous work needs a real callback
   wake path and one bounded coordinator-targeted watchdog for the next evidence,
   with task correlation. Logs do not wake the coordinator; messaging a stuck worker
   is not a coordinator wake-up. A watchdog sharing a failed owner's lifetime cannot
   cover its loss. Use bounded synchronous returns or pause if a usable path is
   missing. Synchronous work needs no communication watchdog; process limits remain
   separate backstops.

5. **Dispatch, coordinate and accept.** Send work once and yield when no independent
   work remains; do not wait through sleeps or repeated status checks. Allow approved
   peers to discuss dependencies without transferring assignment or acceptance rights.
   Coordinate shared contracts and ownership changes, not every technical decision.
   Assess meaningful callbacks and artifacts, not activity. Consolidate worker
   evidence, remaining dependencies and uncertainties; timestamp persistent summaries
   and label stale coverage. One blocked branch need not block the whole team.
   Execution completion is not task acceptance: review checked results and limitations.
   Usage totals need source, window and coverage, never invented complete figures.

6. **Adapt or recover deliberately.** Send bounded updates with the same correlation
   and revised expectations. Before transferring work, preserve partial results,
   resolve pending effects and verify the new owner's context and return path;
   launching a replacement alone is not a handoff. Retain completion evidence until
   acceptance or abandonment. Re-arm or cancel watchdogs as expectations change;
   late results do not resume paused or completed work. For overdue evidence or a
   delivery failure, use [missing evidence](references/missing-evidence.md). For
   nested teams or manager loss, use [hierarchical teams](references/hierarchical-teams.md).

Planning owns the route and evidence timing; dedicated management owns attention
and direction. Runtime tools, transport, timers and process lifecycle own their
mechanisms. This skill neither grants launch authority nor mandates a tool chain.
