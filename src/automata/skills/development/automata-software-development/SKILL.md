---
name: automata-software-development
description: Use for software implementation, debugging, refactoring, code review, or project build/test/environment work that needs engineering judgment.
---

# Automata Software Development

Carry an approved outcome through implementation and proportionate verification.
Prefer simple, readable solutions with cohesive responsibilities, not the smallest
diff at the expense of understandable boundaries or future context cost.

## Scope and design

Clarify uncertainty that materially affects requirements, scope or risk. Recommend
better approaches without implementing unapproved behavior. Make routine internal
decisions within approved scope; ask before exceeding it or introducing unresolved
material consequences, especially for APIs, data, security, dependencies or build
architecture. Approval for one change does not authorize unrelated repairs.

Inspect relevant code and execution/dependency contracts before building on them;
distinguish facts from assumptions. Reason through responsibilities and dependencies,
not just files. Define shared inputs/outputs, state ownership and invariants for
independent work, leaving internals flexible. Do not require a design document,
fixed hierarchy or every function specified upfront. Use diagrams or new patterns
only when they resolve a concrete problem.

Keep code and tests understandable without loading unrelated implementation.
Extend the right responsibility owner, not a convenient nearby module. Keep naming
clear and functions focused. File size signals context cost, not arbitrary splitting
or tiny pass-through files. Parallelize independent responsibilities, not simply
different files. Align affected owners and verify compatibility when shared contracts
change; do not change another owner's module for convenience.

## Project setup and verified recipes

Current project instructions, configuration, manifests, lockfiles and scripts
establish constraints. Consult relevant recipes before rediscovering setup:

- Project: `.agents/var/skills/automata-software-development/`
- Approved user defaults: `~/.agents/var/skills/automata-software-development/`

Locate recipes by project area or purpose; no fixed filenames, index or schema are
required. They hold choices that vary by project/user: runtime, environment, package
manager, dependency workflow, and test/lint/type-check/build commands. Do not impose
a universal stack or bundle basic language tutorials. Use language knowledge with
project conventions; retain special guidance only for actual constraints or
confirmed recurring mistakes.

Reuse a relevant recipe with lightweight checks of assumptions affecting this
operation. Changed configuration, runtime, project area or command failures may
invalidate part of it; repair that part, not the whole setup. Without a recipe,
establish the smallest working path from project evidence. User defaults apply only
where compatible. Resolve consequential conflicts rather than treating saved
commands as authority.

After useful discovery succeeds, retain verified commands, applicability,
prerequisites, evidence, limitations and invalidation/recovery conditions within
storage authority. Update existing knowledge where appropriate; do not fabricate
verification, duplicate project configuration, record secrets or create a recipe
for every command. Former bundled defaults are not approved user preferences.
Keep transient handles/logs separate. Recipes do not authorize downloads, account
changes or shared-environment disruption. Inspect synchronization/cleanup effects
before commands that could remove another task's packages or state; isolate when
needed.

## Implement and document

Check uncertain assumptions with the smallest executable test in a representative,
authorized environment. Exercise the relevant boundary: browser behavior needs
browser evidence; pure logic may need only a direct test. Mocks do not prove behavior
of what they replace. If a real boundary is unavailable or unauthorized, report the
limit. The first implementation slice can be the proof; no separate prototype is
required.

Prove a minimal integrated path early and interleave changes with checks. Avoid
premature abstractions, generic hardening or logging/configuration scaffolds without
a concrete threat, boundary or acceptance need. Keep protections against unintended
capabilities, destructive actions and privacy exposure; disclose material deferred
hardening without silently expanding a prototype's scope.

Follow project conventions. Update docs when behavior, APIs, commands, configuration
or workflows change. Document non-obvious contracts beside their owner: lifecycle,
invariants, extension points, effects and failure expectations. Use language-appropriate
documentation and examples for composition, not boilerplate, repeated signatures or
duplicated contracts. If a module's purpose needs vague prose, reconsider its name
or responsibilities instead.

## Select assurance

Implementation, review and verification are composable, not a mandatory team pipeline.
Choose the lowest sufficient assurance for risk and agreed acceptance criteria:

- **Direct:** prose, formatting or an isolated edit; a relevant quick check.
- **Focused:** ordinary code changes; targeted tests/checks without automatically
  requiring another reviewer or a full suite.
- **Independent:** consequential interfaces, state, security, concurrency or meaningful
  uncertainty; a separately scoped review and relevant verification. A fresh review
  pass is not an independent reviewer. Use another owner when independent judgment
  materially helps and delegation is authorized.
- **Full:** release readiness, broad impact or explicit request; appropriate review
  plus relevant suite, build, integration or acceptance checks.

Use the shortest checks that detect relevant regressions. Make scope, evidence and
non-goals explicit for handoffs or consequential choices, not a routine template.
Review critiques correctness/risk; verification executes checks. Do not silently
expand either assignment or claim independent review where none occurred.

Keep tests cohesive by behavior/boundary and follow repository placement conventions:
module/API behavior in unit tests, command invocation in CLI tests, package resources,
external processes and runtime tools in integration tests.

## Finish and report

Adapt execution to dependencies, uncertainty and credible new evidence; preserve
valid work rather than restarting by default. Fix regressions caused by the change
within scope and complete agreed integration/validation, not just implementation.
Stop when verified, blocked on input or facing an unauthorized next action; do not
polish indefinitely or repair unrelated defects. Report outcomes, verification scope
and limitations, including skipped practical checks, without narrating every step.
