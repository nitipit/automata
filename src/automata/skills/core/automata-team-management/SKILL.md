---
name: automata-team-management
description: Use when a manager coordinates one or more delegated children, consolidates subtree status, adapts a delegation team, or recovers from manager loss.
---

# Automata Team Management

Manage a delegated team or subtree across one or more direct children: consolidate
progress, adapt the team within its authority, and preserve management continuity.
This is not the single caller-to-worker handoff contract.

## Manager and scope

Every managed subtree has a named manager accountable for aggregate state. Only the
root manager sends consolidated status to the user. A non-root manager aggregates
direct-child evidence and reports to its direct parent; it does not bypass that
parent. The manager chain never leaves delegated work silently unowned. Handoff,
instruction-context, timer, model, and transport evidence remain owned by natural
skills.

This is direct-parent management only: manage direct children, not arbitrary
descendants. Use a child's rollup for deeper descendants, but do not command,
reassign, or escalate around a direct parent to reach a grandchild. Escalate
parent-by-parent and let the direct parent resolve or forward issues.

## Aggregate progress

Build estimates from direct-child evidence, elapsed work, remaining scope, dependency
latency, and uncertainty. Distinguish active work from waiting when useful. Revise the
range when evidence changes, and state confidence or the main uncertainty.

Report at meaningful transitions or an agreed reporting deadline, not every activity.
Convey aggregate state, supporting evidence, material risks, and the next useful move;
include an updated estimate when relevant. Use the recipient's required format when
one exists; otherwise keep presentation natural and concise. A status report
is not acceptance. Persistent reports timestamp the aggregate checkpoint and child
evidence as-of; distinguish a newly assembled report from stale child evidence and
label missing coverage and unknowns.
Persistent token totals identify their source, window, as-of time, and coverage; this
is not a new telemetry mechanism.

A blocked report is relative to the reporting node's current scope: at a non-root node,
it means that interaction with its direct parent is required; at the root, it means
interaction with the user is required. Name the dependency,
decision, or input needed. Do not call ordinary waiting or a blocked child a
globally blocked subtree when another branch can continue; aggregate the relative
cause and its effect instead.

## Adaptive visibility

Agree on user/parent visibility appropriate to duration, risk, milestones, and recipient
needs. Keep reporting commitments distinct from worker-evidence deadlines; neither
requires polling.

Next meaningful evidence drives asynchronous work. Synchronous work needs no watchdog;
user/parent reports are separate. While active, keep each direct child's next evidence
and watchdog current; users/parents do not watch workers.

When expected evidence is overdue or a concrete failure needs diagnosis, a manager may
make one bounded passive observation of an explicitly owned direct child. Prefer the
relevant artifact or message, then pane/process metadata; capture diagnostic output once
if needed. Observation is diagnosis, not a way to wait for completion. Preserve the agreed
callback and watchdog; activity or output is not completion or acceptance.

During active user or parent alignment, preserve and queue ordinary child evidence until a stable
boundary. Interrupt only for urgent safety, time-sensitive consequences, invalidated active scope,
or a blocker needing immediate input. Manager availability supports clarification, design
discussion, progress interpretation, and course correction.

## Envelopes and team adaptation

Recognize when changed scope, dependencies, context needs, availability, or weak
integration evidence makes the arrangement worth revisiting. Work design owns the
proposed arrangement and transition; management supplies current evidence and enacts
authorized changes. Preserve manager accountability and direct-parent boundaries.

The user approves the root manager's delegation envelope; a parent supplies a child
manager's envelope within its own authority. Initial delegation requires approval.
Treat missing `depth` = `0`
and missing `child_limit` = **no children**. `depth` is the remaining number of
descendant management levels: a manager can delegate further only when it has
remaining depth, and each descendant consumes one level. When issuing a child
envelope, set `depth` no greater than the parent's remaining depth minus one and
`child_limit` no greater than the parent's limit. Every descendant envelope is
therefore equal-or-narrower; omitted limits never gain authority. Exceeding an
envelope requires explicit user or parent approval and a newly issued envelope; do not
infer permission from available capacity.

Within the approved envelope, launch, replacement, and rebalancing need no per-worker
approval. Adapt the direct team to evidence, preserving scope and the user or parent's
visibility of material changes. Ask before exceeding the envelope, not each time a
worker changes. Do not silently expand authority or strand in-flight work.

Apply redesign through bounded assignments and verified ownership transfers.
Delegation owns the transfer mechanics; keep active work and cleanup accounted for.

Peers within an authorized team may collaborate directly within scope and access
boundaries, without separate approval for ordinary discussion. Collaboration never
transfers management authority, acceptance rights, or ownership. Peers cannot assign
each other work or expand scope. Surface material decisions and unresolved disagreements
to the manager. Respect isolation restrictions; do not contact unrelated agents.

Use direct-child evidence, not unsupported percentages. Distinguish observations
from inferences and identify the next event that would change the aggregate report.

## Manager loss and recovery

Manager loss is distinct from missing worker evidence: handle a child's missing callback
through that caller-to-worker delegation contract. If the manager is lost or unavailable,
pause new work in the affected subtree unless safe, bounded continuation was explicitly
authorized. Preserve completed and partial evidence, current state, envelopes,
dependencies, estimates, risks, correlation, and pending decisions; do not discard,
duplicate, or silently accept work. Report loss and paused work to the direct parent;
at the root, report it to the user. Manager-loss reporting climbs parent-by-parent, and
non-root nodes do not bypass their direct parent to report to the user.

Recovery is a formal parent-owned decision. Record one of:

- **Replacement:** appoint a new manager and reissue the applicable envelope.
- **Reparent:** move a direct child to an explicitly named parent with a compatible
  envelope and notify affected participants.
- **Closure:** stop the subtree with final evidence, unresolved risks, reason,
  acceptance state, and named cleanup owner.

Until replacement, reparenting, or closure is explicit, no descendant may assume
authority. Recovery preserves evidence and visibility; it does not silently
transfer responsibilities, timers, models, transports, or ownership.

## Boundaries

This skill owns subtree aggregation, adaptive user/parent visibility, consolidated status,
bounded direct-team adaptation, and manager-loss recovery. Planning owns goals,
decomposition, constraints, and acceptance criteria; work design owns proposed
responsibilities, context ownership, integration, and transitions. Applicable `AGENTS.md` files
own durable instructions; delegation owns each caller-to-worker handoff, return path, result
review, acceptance, and cleanup; timer, model, and transport skills own their mechanisms. Do
not replace those contracts, bypass a direct parent, or turn a status report into authority
change.
