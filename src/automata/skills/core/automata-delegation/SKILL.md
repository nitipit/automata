---
name: automata-delegation
description: Use when assigning work across an agent, process, working context, or other ownership boundary.
---

# Automata Delegation

Use this skill for the semantic handoff of work between owners or contexts. Keep the
assignment bounded, the return path explicit, and completion evidence observable.

## Before dispatch

Check that the assignment fits the approved scope and delegation envelope. Initial
delegation requires explicit user or assigned parent approval; within that envelope,
launch, replacement, and rebalancing need no per-worker approval. If authority is
missing or the assignment exceeds it, obtain approval before dispatch. Task approval
alone does not imply unrestricted delegation.

Resolve the smallest useful contract before sending work:

- goal, temporary responsibility, allowed scope, and expected result;
- responsible agent or owner and working context;
- working directory and the applicable `AGENTS.md` instruction context;
- communication transport, exact return path, and terminal-session lifecycle owner;
- the next meaningful evidence and a reasonable deadline;
- intermediate meaningful evidence before final completion for longer delegated work;
- recovery, escalation, cancellation, and cleanup conditions.

Verify exact runtime identifiers when availability is uncertain. Confirm the launched
model and supported thinking settings match the agreed assignment; report mismatches
and obtain approval before substituting outside the agreed choices. Resolve missing
choices before dispatch; work design owns selection judgment.

Keep durable behavior and project policy in the applicable `AGENTS.md`. Put task-specific
responsibility, permissions, constraints, and expected evidence in the delegation brief.
Use the supplied instruction context; constrain additional discovery to authorized paths,
not neighboring workspaces.

Provide sufficient context, not the whole conversation: relevant decisions, constraints,
interfaces, dependencies, and acceptance evidence. Include essential facts directly and
point to supporting material for selective reading. Ensure pointers are accessible within
the worker's authorized context; brevity must not hide information needed to act correctly.
If the assignment requires reconstructing broad unrelated context, revisit its boundary
with work design rather than merely shortening the brief.

Resolve transport before handoff rather than leaving the return path abstract. Prefer tmux for
delegated agent or persistent worker communication when the caller is inside tmux, caller and
worker share the same tmux server, and exact owned panes can be verified. Before dispatch,
apply the applicable tmux communication and background-session contracts, establish or reuse
an explicitly owned detached worker session when persistence is needed, and record the exact
worker target and return pane in the delegation brief. When tmux callback preconditions are
unavailable, use an agreed return-capable transport or bounded synchronous execution.

If ownership or the return path is missing, stale, ambiguous, or unreachable, pause the
handoff. Preserve the task locally and surface the boundary so the caller can provide a
verified path or agree on another channel.

## Assignment revisions

Accepted decisions made during ongoing alignment with a user or parent may be relayed as
explicit bounded assignment updates with the same correlation. State changed scope, evidence,
and ETA. For asynchronous delegated work, re-arm the watchdog for the revised next meaningful
evidence. Avoid concurrent manager edits to worker-owned files.

When applying a redesigned assignment, establish the ownership transfer at the agreed
handoff point. Preserve partial results and pending decisions, confirm the receiving
owner has the needed context and return path, and resolve outstanding writes or side
effects before releasing the old owner. Keep callback correlation, watchdog coverage,
and cleanup responsibility aligned; a replacement launch alone is not a completed
handoff.

## Normal completion

For asynchronous delegated work, use an event-driven sequence:

```text
dispatch + coordinator-targeted watchdog notice → yield → callback or notice → assess
```

Pair each asynchronous dispatch with one bounded watchdog for the next meaningful
evidence. Address its notice to the coordinator's wakeable input, not to the worker:
a scheduled worker status request does not wake the coordinator if the worker is stuck.
Send the work once, then end the current agent turn when no independent work remains.

In an interactive session, ending the turn leaves the session available for callbacks;
it does not abandon the assignment or close the terminal. Do not keep the turn open
with sleep calls or repeated artifact, process, or pane checks. Let a callback or
watchdog notice begin the next coordination turn. A callback may queue during active
dialogue; arrival, not process presence or pane output, is the normal completion trigger.

Bounded synchronous delegated execution returns directly and does not require a communication
watchdog. A hard process or time limit may still be useful as a separate safety backstop; it is
not a watchdog or callback.

A worker's result is evidence to inspect, not automatic acceptance. When stale or concurrent
callbacks could be confused, carry the same task or correlation identity in the assignment,
initial result, and any resend. Keep completed evidence available until acceptance or
abandonment so a valid status request can prompt a resend through the original return path.
Process or pane observation is bounded diagnosis when evidence is overdue or a concrete
failure needs investigation, not a way to wait for completion.

## Adaptive visibility

Set intermediate evidence and deadlines from duration, risk, dependencies, and useful
milestones. Workers report meaningful changes through the agreed return path; revise
expectations when the work changes. Do not substitute periodic activity reports for
useful evidence or turn visibility into polling.

## Missing evidence

A bounded watchdog delivers an overdue notice to the responsible coordinator's wakeable input
path. The notice identifies the expected evidence and correlation, starting a new coordinator
turn while leaving the recovery decision to that coordinator.

If a still-needed asynchronous watchdog transport becomes unsafe or unavailable, establish
an agreed replacement before removing coverage. Canceling stale delivery must not silently
leave active work unwatched.

On notice, the coordinator:

1. checks once whether the expected evidence already arrived;
2. sends a context-appropriate status request through the agreed path, if useful;
3. chooses diagnosis, escalation, cancellation, or stopping from the current contract.

Cancel or re-arm the watchdog when evidence arrives, the work completes, blocks, fails, is
abandoned, or is relaunched so timer state stays aligned with the active expectation.

## Boundaries

This skill owns delegation semantics: handoff, evidence, waiting, recovery, and acceptance.
Work design owns proposed responsibilities, context ownership, and transitions;
planning owns work decomposition and acceptance criteria; management owns active
coordination within the approved envelope. Applicable `AGENTS.md` files own durable
instructions. Model, transport, terminal session, timer implementation, and message
vocabulary remain contextual choices made by their natural owners. Keep evidence timing
contextual and the contract neutral to coordinator, topology, and response sequence.
