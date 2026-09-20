---
name: automata-delegation
description: Use when assigning work across an agent, process, working context, or other ownership boundary.
---

# Automata Delegation

Hand off bounded work with explicit ownership, a usable return path and observable
completion evidence. Task approval alone does not authorize unrestricted delegation.

## Establish the handoff

Initial delegation requires an approved user/parent envelope. Within it, launch,
replacement and rebalancing need no per-worker approval; missing authority or work
outside the envelope requires approval before dispatch.

Define the smallest sufficient contract:

- Goal, temporary responsibility, scope and verifiable completion criteria.
- Allowed corrections, required checks and stopping boundaries.
- Owner, working context/directory and applicable `AGENTS.md` instructions.
- Transport, exact return path and terminal-session lifecycle owner.
- Next meaningful evidence and deadline; intermediate milestones for longer work.
- Recovery, escalation, cancellation and cleanup conditions.

Resolve model choices before dispatch and verify exact runtime identifiers when
availability is uncertain. Confirm the launched model and supported thinking level
match the assignment. Report mismatches; do not substitute outside agreed choices
without approval.

Put task-specific decisions, interfaces, dependencies and expected evidence in the
brief, not the entire conversation. Keep durable policy in `AGENTS.md`. Include
essential facts directly and accessible pointers for selective reading. Constrain
discovery to authorized paths, not neighboring workspaces. If useful work requires
reconstructing broad unrelated context, revisit the assignment boundary rather than
merely shortening the brief.

## Establish the return path

Prefer tmux when the caller and worker share a tmux server and exact owned panes
can be verified. Follow the tmux communication/background contracts: verify a safe
receiver, use an explicitly owned detached session when persistence is needed, and
record exact worker and return targets. Otherwise agree on a return-capable
transport or bounded synchronous execution.

If ownership or the return path is missing, stale, ambiguous or unreachable, pause
the handoff. Preserve the task and ask for a verified path or agreed alternative;
do not send work with an abstract or guessed return destination.

## Dispatch, yield and assess

For asynchronous work:

```text
dispatch + coordinator-targeted watchdog → yield → callback or notice → assess
```

Pair each dispatch with one bounded watchdog for the next meaningful evidence.
Address its notice to the coordinator's wakeable input, identifying expected
evidence and task correlation. A scheduled request to a stuck worker cannot wake
the coordinator. Send work once, then end the turn when no independent work remains.

Ending an interactive turn leaves the session available for callbacks; it does not
abandon the assignment or close the terminal. Do not wait through sleeps or repeated
artifact, process or pane checks. A callback may queue during dialogue; its arrival,
not process presence or pane activity, is the normal completion trigger.

Bounded synchronous work returns directly and needs no communication watchdog.
A process/time limit is a separate safety backstop, not a callback.

Choose intermediate milestones and deadlines from duration, risk and dependencies.
Workers report meaningful changes through the agreed path, not periodic activity
for its own sake. Keep the expectation and watchdog current: cancel or re-arm when
evidence arrives or work completes, blocks, fails, is abandoned or relaunched.

Review a worker's result before acceptance. Preserve task correlation in the brief,
results and resends when callbacks could be confused. Keep completed evidence until
acceptance or abandonment so a valid status request can prompt a resend through the
original return path.

## Revisions and recovery

Relay accepted user/parent decisions as bounded updates under the same correlation,
including changed scope, evidence and ETA. Do not edit worker-owned files concurrently.
For a transfer, preserve partial results and pending decisions, confirm the receiving
owner's context and return path, and resolve outstanding writes/effects before
releasing the old owner. Align callbacks, watchdogs and cleanup responsibility;
a replacement launch alone does not complete the handoff.

When evidence is overdue or a concrete delivery failure needs diagnosis, read
[Missing evidence](references/missing-evidence.md). Inspect only owned resources;
observation is bounded diagnosis, not a way to wait for completion. If a still-needed
watchdog path becomes unsafe or unavailable, establish an agreed replacement before
removing coverage. Never silently leave active work unwatched.

## Boundaries

Delegation owns handoff, evidence, waiting, recovery and acceptance. Work design
proposes responsibilities and context boundaries; planning owns decomposition and
acceptance criteria; management coordinates within the approved envelope.
`AGENTS.md` owns durable policy. Model, transport, terminal lifecycle and timer
skills own their mechanisms; keep participant topology and evidence timing contextual.
