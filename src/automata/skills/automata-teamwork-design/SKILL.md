---
name: automata-teamwork-design
description: Use for choosing solo/team arrangements, assignment boundaries, context ownership and models, or revising those choices. Not for launching workers.
---

# Automata Teamwork Design

Arrange work and context for useful quality, cost, time and risk tradeoffs—not
maximum parallelism. Small work needs no formal team-design document.

1. **Compare viable arrangements.** Use established goals and constraints, including
   user involvement and coordinator availability. Use solo work as the comparison
   baseline; a request for a team plan does not imply a team is needed. Recommend
   additional agents only when specific parallelism, specialization or independent
   assurance outweighs briefing, duplicated context, handoffs, review, retries and
   integration. Account for dependencies and context overlap; do not silently lower
   standards when no arrangement fits.

   Justify independent review by concrete failure risks, consequences or a user
   requirement—not merely a generally tricky topic such as async code. Compare its
   added assurance with focused checks and live verification by the implementer.

2. **Keep context coherent.** Assign outcomes workers can complete and verify, not
   arbitrary file/token slices. Keep coupled knowledge and implementation/checks
   together unless separation earns its handoff cost. Execution delegation need
   not move design ownership. Provide scope, dependencies, integration and expected
   evidence without copying the whole conversation. When choosing between resuming
   a worker and starting a new one, weigh retained knowledge against the cost of
   retaining or reloading context; cache reuse is uncertain.
   Consider concise handoff or compaction when obsolete context outweighs continuity.

3. **Choose supported models.** Use task-relevant evidence and approved preferences
   for model/effort choices; names, price or availability do not establish fit or
   speed. Compare a viable alternative for material choices and distinguish proposals
   from verified runtime identities. Resolve missing information when it could
   change the recommendation; do not reopen settled choices at every continuation.
   Missing permission is not unlimited authority.

4. **Explain and adapt.** Present decision-relevant ownership, context, models,
   integration and communication with the main tradeoff; avoid exhaustive diagrams
   or mandatory estimate templates. Allow authorized peer discussion without manager
   relays while preserving reporting, privacy, isolation and ownership boundaries.
   Revise affected assumptions with evidence, not merely to agree. Preserve partial
   results and clear ownership; avoid concurrent writes, duplicate effects and
   stranded work during transitions.

Initial delegation requires an approved scope and resource limits. Within those
boundaries, worker launches, replacements and rebalancing need no per-worker
approval; expanding those boundaries requires approval. This skill guides proposed
arrangements; it does not authorize worker launches or reassignments. Planning owns
the work approach and resource tradeoffs; delegation owns handoffs and runtime
verification; management owns carrying out approved team changes.
