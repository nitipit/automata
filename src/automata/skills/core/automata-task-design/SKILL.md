---
name: automata-task-design
description: Use when choosing assignment boundaries, context ownership, models, or solo/team arrangements, or revising them as evidence changes.
---

# Automata Task Design

Choose how to organize work and context, whether solo or with a team. One owner,
fewer workers, or sequential work may be better than a larger team. A full work
plan is not required to discuss an arrangement. Use this judgment when the choices
matter, not as a mandatory stage for every task.

## Design Judgment

Design for an acceptable result, balancing context ownership, total cost, completion
time, and risk—not maximum parallelism or minimum token price. Design temporary
responsibilities, not predefined roles.

Keep tightly coupled knowledge together. Shared versus isolated contexts should
follow overlap, specialization, and the value of independent evidence. Delegating
execution need not move the coordinator's design context. Count briefing, duplicated
context, review, retries, and integration in total cost; consider dependencies and
waiting in end-to-end completion time. Meet agreed acceptance criteria; stronger
models or more agents do not guarantee quality. Explain what assurance the
arrangement provides.

Size assignments around coherent, verifiable outcomes that a worker can understand,
complete, and check with manageable working context—not arbitrary task counts, file
counts, or token limits. Keep tightly coupled implementation and verification together
when splitting would duplicate reasoning. Split or stage accumulating unrelated concerns
when the context benefit outweighs briefing, handoff, and integration costs. Smaller
assignments are not automatically more efficient; revise boundaries with evidence.

Use established user priorities. When a tradeoff would materially change the design,
recommend an approach, explain its concrete consequence, and ask what matters most.
Clarify deadlines, budget or quota, and acceptable quality or risk as needed—not as
a routine questionnaire. Context distribution remains the agent's engineering decision.
Tradeoffs may reveal a need to revise quality expectations with the user; planning
keeps the agreed acceptance criteria. Adapt within agreed priorities without
repeatedly asking; do not silently lower the standard.

Before recommending an arrangement, compare it with a simpler viable alternative,
including solo or sequential work where appropriate. Use dependencies, context overlap,
coordination cost, and expected evidence to choose—not to justify a team already chosen.
Briefly explain why the recommendation is preferable without waiting to be asked why;
do not routinely present the full comparison. When challenged, reassess on evidence:
explain what changed or was missed rather than redesigning merely to agree.

Make ownership, dependencies, integration, and expected evidence clear enough to
hand off work. Identify where direct peer collaboration helps while respecting
scope, decision ownership, and isolation boundaries.

## Model Evidence

Let model choices and work distribution inform each other. Use the user's available
and permitted candidates, not a universal model-to-role ranking. Reuse relevant
research or task evidence. Suggest focused research when missing or stale comparative
evidence could materially change the design; missing research alone does not require
investigation. Separate vendor claims, observed results, and unknowns. Research is
supporting evidence, not a mandatory phase or launch authorization.

When proposing model choices, show the model and thinking level for the solo agent
or every agent in the team, including the coordinator.
Use known current settings or explicitly label unknown settings; distinguish these from
proposed worker settings. Include inherited defaults when known. Explain choices when
they materially affect feasibility, cost, or authority. Distinguish **runtime capability** from
**approved selection bounds**: available models and effort levels are not automatically
permitted choices. Preserve allowed sets and discrete effort choices rather than
inventing a universal ranking. Do not guess unknown settings or treat missing authority
as unlimited. Match choices to the work and available evidence, not role labels alone.

## Make the proposal easy to discuss

Present the recommended arrangement and its main tradeoff, not the full working
analysis. Diagrams are optional: use a compact team tree or dependency flow when it
helps a decision, without inventing stages or redrawing unchanged arrangements.
Use stable, unambiguous names when helpful; names do not replace runtime identities.
Reporting hierarchy does not dictate every communication path, and dependency arrows
do not transfer authority. Label proposed settings separately from verified running
settings, and unsupported thinking controls as unsupported.

Discuss unresolved choices when needed. Agreement on a proposal is not launch
authority; obtain approval for actions outside existing scope and, when delegating,
outside the approved delegation envelope.

## Redesign and Authority

Reconsider the arrangement when scope, dependencies, context needs, availability,
or integration evidence changes. For active work, propose a safe transition as well
as the new arrangement: preserve partial results, keep ownership clear, and avoid
concurrent writes or duplicate side effects. Handoff and recovery mechanics belong
with delegation and management rather than this design discussion.

Initial delegation requires an approved envelope from the user or assigned parent.
Within it, launch, replacement, and rebalancing need no per-worker approval; exceeding
it requires explicit approval. A design proposes an arrangement, not new authority.
Keep the proposal proportionate; no separate document is required.

## Boundaries

Planning owns work decomposition and acceptance criteria. Task design owns proposed
responsibilities, context ownership, model choices, and transitions. Delegation owns
executable handoffs and verifies launched settings; management recognizes redesign
needs, enacts authorized changes, and remains accountable for active work and recovery.
This skill does not launch or reassign workers. Compose through the situation, not
a mandatory skill chain.
