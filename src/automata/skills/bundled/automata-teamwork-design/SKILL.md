---
name: automata-teamwork-design
description: Use when choosing assignment boundaries, context ownership, models, or solo/team arrangements, or revising them as evidence changes.
---

# Automata Teamwork Design

Organize work and context to balance quality, total cost, completion time and risk.
Use this judgment when the choices matter, not as a mandatory stage or document.

## Choose the arrangement

Choose an arrangement that serves the established outcome, priorities and material
constraints. Include relevant collaboration needs, such as user involvement or
keeping the coordinator available; execution speed is not the only measure of
success. Compare with a simpler viable alternative, including solo or sequential
work. Choose from dependencies, context overlap, specialization and the value of
independent evidence—not maximum parallelism or fixed model-to-role rankings.
Count briefing, duplicated context, review, retries and integration; explain what
assurance the arrangement adds.

Keep tightly coupled knowledge together. Assign coherent outcomes a worker can
complete and verify within manageable context, not arbitrary file or token counts.
Keep implementation and verification together when splitting duplicates reasoning;
separate concerns only when the benefit outweighs handoff and integration costs.
Delegating execution need not move the coordinator's design context.

When choosing between resuming an agent and starting fresh, weigh retained
knowledge against context size, likely cache reuse and the cost of loading context
again. Resuming is not automatically cheaper; cache availability is uncertain.
Prefer a concise handoff or compaction when obsolete context outweighs useful
continuity, accounting for the preparation cost and preserving needed state.

Clarify deadlines, budget, quality or risk only when uncertainty materially changes
the design. If no viable arrangement meets the outcome within material constraints,
surface the tradeoff; do not silently lower acceptance standards or expand scope.
Ordinary context allocation remains an engineering decision within those priorities.
Carry the relevant outcome, constraints and unresolved assumptions into assignments,
with ownership, dependencies, integration and expected evidence. Give each worker
enough context to judge its contribution without duplicating the entire discussion.

Distinguish the communication graph from the reporting and authority tree. Enable
direct discussion between authorized peers when it reduces relay cost or improves
shared understanding; do not route every technical exchange through the manager.
Choose communication paths for the task, not a universal all-to-all topology.
Respect scope, privacy and isolation. A communication path does not grant assignment,
editing or acceptance rights; keep accountable owners and reporting obligations
explicit.

## Choose models from evidence

Understand candidates' task-relevant strengths, limitations, reliability, context
capacity and speed/token-cost tradeoffs, including the proposed thinking levels.
Consult existing model-selection knowledge and approved preferences; distinguish
evidence from assumptions. Names, availability, price and current-session identity
do not establish task fit. Do not infer speed from price alone.

Use available **and permitted** models and effort levels; missing permission is not
unlimited authority. Justify each assignment, including a solo executor or current
coordinator, against a viable alternative. An approval-ready design includes model
and effort choices with their rationale; an arrangement-only sketch is preliminary.
Resolve decision-relevant evidence gaps before seeking execution approval. Reuse
applicable knowledge and research only gaps that could change the choice.

## Present the proposal

Present **team setup, time estimate and token estimate together** before approval,
with the recommendation and main tradeoff. A small solo task may need only a few
lines, not the full working analysis.

- **Team:** identify roles, ownership, manager/reviewer responsibilities, useful
  peer communication paths, reporting obligations and parallel versus sequential work. Give each agent's model and effort, including the
  coordinator. Distinguish proposed from verified settings; include known inherited
  defaults and label unknown or unsupported settings. Names or a team tree can aid
  discussion but do not replace runtime identities or require extra workers.
- **Time:** give an end-to-end range covering preparation, implementation, tests,
  review, corrections and integration. State assumptions and distinguish active
  effort from elapsed time, dependency delays and approval waits.
- **Tokens:** estimate the whole task across coordinator and workers, including
  startup/resumption, briefing, repeated input, output, review and corrections.
  Separate input, output and cached input when useful and supported. State the basis, uncertainty and
  exclusions. Context-window size is not cumulative usage; token estimates are not
  cost quotes. If an estimate is not defensible, offer a bounded first slice to
  calibrate it.

Revise estimates and ownership when evidence changes; report deltas rather than
repeating unchanged diagrams. Estimates are not acceptance criteria. Explain
changed assumptions when challenged; do not redesign merely to agree.

## Redesign within authority

Reconsider the arrangement when scope, dependencies, context needs, availability
or integration evidence changes. Preserve partial results and clear ownership
during transitions; avoid concurrent writes, duplicate effects and stranded work.

Initial delegation needs an approved envelope from the user or assigned parent.
Within it, launch, replacement and rebalancing need no per-worker approval;
exceeding it requires explicit approval. Proposals and research do not authorize
model changes or worker launches, and redesign does not expand permissions.

## Boundaries

Goal reasoning owns desired outcomes, priorities and material constraints;
planning owns the route, decomposition and concrete acceptance checks. Teamwork
design proposes responsibilities, context allocation, models and transitions. Delegation owns
executable handoffs and runtime verification; management enacts authorized changes
and owns active-work recovery. This skill does not launch or reassign workers.
Compose these capabilities as needed, not as a mandatory skill chain.
