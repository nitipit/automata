---
name: automata-team-management
description: Use when a manager coordinates one or more delegated children, consolidates subtree status, adapts a delegation team, or recovers from manager loss.
---

# Automata Team Management

Manage a team's aggregate progress, adaptation and continuity. This skill owns
subtree coordination, not individual handoff or transport mechanics.

## Ownership and reporting

Each subtree has a named accountable manager. Manage only direct children; use
their rollups for deeper descendants. Do not command, reassign or escalate around
a parent to reach grandchildren. A non-root manager reports to its direct parent;
only the root sends consolidated status to the user. Never leave work silently
unowned or treat a status report as acceptance or new authority.

Build estimates from child evidence, elapsed work, remaining scope, dependencies
and uncertainty. Distinguish observations from inferences and active work from
waiting; avoid unsupported percentages. Revise estimates when evidence changes.
Report meaningful transitions or agreed deadlines, not every activity. Include
verified progress, material risks, the next useful move and relevant estimate
changes, using the recipient's requested format.

Persistent reports timestamp both the aggregate checkpoint and the child evidence.
Label stale evidence, missing coverage and unknowns; a fresh report is not proof of
fresh progress. Token totals identify their source, measurement window, as-of time
and coverage; do not invent a separate telemetry system.

A blocked report names the input, decision or dependency needed from the reporting
node's parent, or from the user at the root. Do not label ordinary waiting or one
blocked branch as a globally blocked subtree when other work can continue.

## Visibility without interruption

Keep reporting commitments separate from worker-evidence deadlines. For each
asynchronous child, maintain the next meaningful evidence and coordinator-targeted
watchdog through the delegation contract. Synchronous work needs no watchdog.
Do not leave users or parents responsible for watching workers.

Use callbacks as the normal evidence path. When evidence is overdue or a concrete
failure needs diagnosis, make one bounded passive observation of the owned child:
prefer relevant messages/artifacts, then pane/process metadata, and capture output
once if needed. Do not poll, infer completion from activity, or replace the agreed
callback and watchdog with inspection.

During user/parent alignment, queue ordinary child evidence until a stable boundary.
Interrupt only for urgent safety, time-sensitive consequences, invalidated active
scope or a blocker needing immediate input. Remain available for clarification and
course correction without turning progress checks into worker interruptions.

## Delegation envelopes

The user approves the root manager's envelope; a parent grants a child manager an
envelope within its own authority. Initial delegation requires this approval.

- Missing `depth` means `0`; missing `child_limit` means no children.
- `depth` counts remaining descendant levels. Delegating consumes one level;
  further delegation requires remaining depth.
- A child's `depth` cannot exceed the parent's remaining depth minus one, and
  its `child_limit` cannot exceed the parent's limit. Descendant scope must stay
  equal or narrower; omitted limits or spare capacity never grant permission.

Within the envelope, launch, replacement and rebalancing need no per-worker approval.
Exceeding it requires explicit user/parent approval and a newly issued envelope.
Keep material changes visible; do not silently expand scope or strand active work.

## Adapt the team

Reconsider the arrangement when scope, dependencies, context needs, availability
or integration evidence changes. Work design proposes the arrangement; management
supplies current evidence and enacts authorized changes. Preserve direct-parent
accountability, bounded assignments and verified ownership transfers. Delegation
owns handoff mechanics; keep active work and cleanup accounted for.

Authorized peers may discuss work within scope and isolation boundaries without
separate approval. Collaboration does not transfer ownership, acceptance rights or
management authority. Peers cannot assign each other work or expand scope. Surface
material decisions and unresolved disagreements to the manager; do not contact
unrelated agents.

## Manager unavailable

Manager loss is not a missing worker callback. Pause new work in the affected
subtree unless safe, bounded continuation was explicitly authorized. Preserve
partial results and report through the direct-parent chain, or to the user at the
root. No descendant may assume the missing manager's authority.

When manager availability is lost or recovery is needed, read
[Manager recovery](references/manager-recovery.md) before changing ownership or
resuming work. Recovery requires an explicit parent-owned decision.

## Boundaries

This skill owns aggregate status, adaptive visibility, direct-team adaptation and
manager-loss recovery. Planning owns acceptance criteria; work design owns proposed
arrangements; delegation owns individual handoff, review, acceptance and cleanup.
Applicable `AGENTS.md` files own durable instructions. Timer, model and transport
skills own their mechanisms. Compose these contracts; do not replace them.
