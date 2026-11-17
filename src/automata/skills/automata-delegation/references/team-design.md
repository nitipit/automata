# Team design

Use when work division, context ownership or independent review materially affects
quality, cost, time or risk. A simple handoff needs no separate design exercise.

## Compare arrangements

Evaluate viable solo and team arrangements against the same goals, constraints and
user-availability needs. More workers are not inherently faster. Account for
briefing, repeated discovery, dependencies, review, retries and integration, not
just concurrent implementation. Do not silently lower standards to fit a team.

## Bound verification and independent review

Do not add or propose a separate independent reviewer unless the user explicitly
requests one. General permission to delegate or form a team is not that request.

Verifier agents remain available within approved delegation: run tests, reproduce
behavior, check agreed acceptance criteria and report evidence or gaps. They may
flag unexpected problems, but must not redefine requirements or direct the team.
The coordinator resolves findings within scope and brings material changes of
direction to the user. Implementers still check their own work; this rule does not
restrict self-checks, raising concerns or challenging assumptions.

Distinguish responsibilities, not titles. Calling an independent design critique
"verification", "QA" or an "audit" does not bypass the explicit-request requirement.

When independent review is explicitly requested, assess its expected risk reduction,
blind spots, consequences and cost. Brief the reviewer on goals, acceptance criteria,
constraints, non-goals and deliberate tradeoffs. The assignment returns findings
and recommendations, not new assignments or unilateral project direction;
integration and acceptance ownership do not transfer to the reviewer.

## Divide coherent outcomes

Keep coupled knowledge and implementation/checks together unless independent work
or assurance earns its handoff cost. State technical integration and acceptance
ownership; execution delegation need not transfer design ownership. Prefer explicit
contracts and non-conflicting files to arbitrary splits or maximal parallelism.

Choose resumption versus a fresh worker by retained knowledge and obsolete context
cost; cache reuse is uncertain. Use concise checkpoints when needed, not copied
parent sessions. Reconsider an assignment that needs broad unrelated context.

## Choose and explain resources

Use task-relevant evidence and approved model/effort preferences. Compare a viable
alternative for material choices; model names, price and availability alone prove
neither fit nor speed. Distinguish proposed settings from verified runtime identity.
Resolve decision-changing uncertainty, but do not reopen settled choices each turn.

Explain ownership, context, resources, dependencies and the main tradeoff concisely.
Revise the arrangement with evidence rather than adding workers to fill boxes.
