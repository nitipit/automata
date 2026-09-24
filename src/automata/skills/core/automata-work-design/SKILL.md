---
name: automata-work-design
description: Use when choosing assignment boundaries, context ownership, models, or solo/team arrangements, or revising them as evidence changes.
---

# Automata Work Design

Choose how to organize work and context for an acceptable result, balancing total
cost, completion time and risk. Use this judgment when the choices matter, not as
a mandatory stage for every task. A full plan or separate document is not required.

## Choose the arrangement

Compare the proposed arrangement with a simpler viable alternative, including solo
or sequential work. Choose from dependencies, context overlap, specialization and
the value of independent evidence—not maximum parallelism, minimum token price or
fixed model-to-role rankings. Count briefing, duplicated context, review, retries
and integration. More agents or stronger models do not guarantee quality; explain
what assurance the chosen arrangement provides.

Keep tightly coupled knowledge together. Size assignments around coherent outcomes
that a worker can understand, complete and verify within manageable context, not
arbitrary file counts or token limits. Keep implementation and verification together
when splitting would duplicate reasoning. Separate or stage unrelated concerns only
when the context benefit outweighs handoff and integration costs. Delegating
execution need not move the coordinator's design context.

Use established user priorities. Clarify deadlines, budget, quality or risk only
when uncertainty materially changes the design. Explain consequential tradeoffs
and recommend an approach; do not silently lower acceptance standards. Ordinary
context allocation stays an engineering decision within the approved priorities.

Make ownership, dependencies, integration and expected evidence clear enough for
handoff. Allow useful peer collaboration within scope and isolation boundaries;
reporting lines and dependency arrows do not grant authority.

## Choose models from evidence

Use available **and permitted** models and thinking levels. Runtime capability is
not selection authority: preserve approved model sets and effort choices, and do
not treat missing permission as unlimited. Match choices to the work, not role
labels alone.

Reuse relevant model-selection knowledge and approved preferences. Distinguish
measured results, vendor claims and unknowns; apply preferences within their agreed
scope without silently relaxing restrictions. Seek focused research only when
missing or stale evidence could change the choice. Research is neither a mandatory
phase nor launch authorization. Do not infer model speed from price alone.

## Present the proposal

Describe **team setup, time estimate and token estimate together** before approval.
Keep it proportionate: a small solo task may need only a few lines. Present the
recommendation, why it beats the simpler alternative and its main tradeoff—not the
full working analysis.

- **Team:** identify solo/team work, names or proposed roles, manager/reviewer
  responsibilities, ownership, and parallel versus sequential work. Show each
  agent's model and thinking level, including the coordinator. Separate proposed
  settings from verified runtime settings; label unknown or unsupported settings
  rather than guessing, and include inherited defaults when known. Use a compact
  team tree when helpful; do not invent workers for the diagram. Names aid discussion
  but do not replace runtime identities.
- **Time:** give an end-to-end range covering preparation, implementation, tests,
  review, corrections and integration. Distinguish active effort from elapsed time,
  dependency delays and approval waits. State the assumptions that affect the range.
- **Tokens:** estimate whole-task usage across coordinator and workers, including
  briefing, repeated input, output, review and likely corrections. Separate input,
  output and cached input when useful and supported; context-window size is not
  cumulative usage. Give a rough range with its basis, uncertainty and exclusions.
  If a number is not defensible, say so and offer a bounded first slice to calibrate
  it rather than inventing precision. Token estimates are not cost quotes.

Revise estimates after meaningful evidence. During updates, report changed estimates
or ownership without repeating unchanged diagrams. Estimates are not acceptance
criteria. When challenged, explain what evidence or assumption changed; do not
redesign merely to agree.

## Redesign within authority

Reconsider the arrangement when scope, dependencies, context needs, availability
or integration evidence changes. For active work, propose a safe transition:
preserve partial results, keep ownership clear, and avoid concurrent writes or
duplicate effects. Do not strand work during a replacement.

Initial delegation needs an approved envelope from the user or assigned parent.
Within it, launch, replacement and rebalancing need no per-worker approval;
exceeding it requires explicit approval. Discussion of a proposal is not launch
authority, and redesign does not expand permissions.

## Boundaries

Planning owns decomposition and acceptance criteria. Work design proposes
responsibilities, context allocation, models and transitions. Delegation owns
executable handoffs and runtime verification; management enacts authorized changes
and owns active-work recovery. This skill does not launch or reassign workers.
Compose these capabilities as needed, not as a mandatory skill chain.
