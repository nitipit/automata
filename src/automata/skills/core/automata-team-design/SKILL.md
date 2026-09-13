---
name: automata-team-design
description: Use when designing an initial agent team or reconsidering its responsibilities, context ownership, model choices, or arrangement as work and evidence change.
---

# Automata Team Design

Design the smallest useful distribution of work and context. One owner, fewer
workers, or sequential work may be better than a larger team. A full work plan is
not required to discuss a team, and a plan does not require one.

## Design Judgment

Start from the outcome, dependencies, available capabilities, and existing authority.
Design temporary responsibilities, not predefined roles. Consider specialist context,
independent evidence, integration cost, and keeping the coordinator available—not
only parallelism. Delegating execution need not move the coordinator's design context.

Make ownership, dependencies, integration, and expected evidence clear enough that
work can be handed off without ambiguity. Shared versus isolated contexts should
follow the work's overlap and risk, not a fixed topology. Use time/token estimates
as evidence, not automatic team-size rules.

Show the model and thinking level of every agent in the team, including the coordinator.
Use known current settings or explicitly label unknown settings; distinguish these from
proposed worker settings. Include inherited defaults when known. Explain choices when
they materially affect feasibility, cost, or authority. Distinguish **runtime capability** from
**approved selection bounds**: available models and effort levels are not automatically
permitted choices. Preserve allowed sets and discrete effort choices rather than
inventing a universal ranking. Do not guess unknown settings or treat missing authority
as unlimited. Match choices to the work and available evidence, not role labels alone.

## Make the proposal easy to discuss

For multi-agent proposals and material redesigns, show two compact plain-text diagrams:

- A team tree showing reporting relationships. Give every agent, including the
  coordinator, a short temporary human-style name and show its responsibility, model,
  and thinking level. Keep names
  stable during their assignments and unambiguous within the team. Names are discussion
  labels, not personalities, predefined roles, or substitutes for runtime session IDs.
- A separate work-flow diagram showing the agreed or proposed dependencies, parallel
  work, and review loops when relevant. Label stages with their responsible agent names.
  Planning owns those dependencies; visualize the available plan rather than inventing
  extra stages to fill a diagram. Mark unresolved dependencies instead of guessing.

Keep both diagrams proportionate. One agent may be shown on one line; a simple work
sequence needs only a short arrow chain. Do not redraw unchanged diagrams in every
progress report. Make clear that tree lines mean reporting relationships and work arrows
mean dependencies, not a change in authority. Reporting hierarchy does not dictate
every communication path. Identify where direct peer collaboration would help and
make shared scope, decision ownership, and any isolation boundaries clear.

Before launch, label settings as proposed; distinguish them from verified running settings
when redesigning active work. Label unknown model or thinking settings as unknown and
unsupported thinking controls as unsupported, rather than guessing.

Use the diagrams to discuss responsibilities, settings, and unresolved choices until
aligned. Ask a clear question when input is needed. Agreement on a diagram is not launch
authority; obtain approval for execution outside the existing delegation envelope.

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

Planning owns work decomposition and acceptance criteria. Team design owns proposed
responsibilities, context ownership, model choices, and transitions. Delegation owns
executable handoffs and verifies launched settings; management recognizes redesign
needs, enacts authorized changes, and remains accountable for active work and recovery.
This skill does not launch or reassign workers. Compose through the situation, not
a mandatory skill chain.
