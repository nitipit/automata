---
name: automata-software-development
description: Use for software implementation, debugging, refactoring, code review, or project build/test/environment work that needs engineering judgment.
---

# Automata Software Development

Carry an approved outcome through a working happy path first, not production
readiness by default. Assume valid inputs and normal operation unless the approved
scope says otherwise. Prefer simple, readable solutions with cohesive responsibilities,
not the smallest diff at the expense of understandable boundaries.

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

Design modules for selective understanding: a typical change should require loading
only a small, coherent part of the system. Give each module a discoverable purpose
and clear contract so callers need not understand its internals. Keep related behavior
together, names clear and functions focused. Extend the right responsibility owner,
not a convenient nearby module; avoid tightly coupled fragments or pass-through files.

For hand-written source files, prefer up to 300 lines; 301–500 is acceptable for one
cohesive responsibility. Above 500, review boundaries before adding behavior and
prefer extracting an independent responsibility. Above 800, strongly favor splitting;
keeping the file intact needs a concrete justification. Count total physical lines,
including comments and blanks; do not compress formatting or remove useful docs to
meet thresholds. Exclude generated code, lockfiles and large data fixtures. Review
large tests by behavior too. These are design defaults, not model comprehension limits.
Cohesion takes priority over arbitrary splitting; do not refactor an existing large
file for an unrelated small fix. Judge how much code must be understood together,
not file size alone.

Parallelize independent responsibilities, not simply different files. Align affected
owners and verify compatibility when shared contracts change; do not change another
owner's module for convenience.

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

Build the smallest integrated happy path and confirm it with a minimal smoke check
in an authorized environment. For prose-only changes, a direct structural and
semantic review can suffice. Exercise only the boundary needed for this claim:
browser behavior needs browser evidence; pure logic may need only a direct call.
Mocks do not prove behavior of what they replace. If the relevant boundary is
unavailable or unauthorized, report the limit rather than expanding verification.
The first implementation slice can be the proof; no separate prototype is required.

Do not add edge-case handling, retries, recovery, concurrency mechanisms, generic
hardening, or logging/configuration scaffolds unless included in the approved scope.
Suggest worthwhile additions separately and obtain confirmation before implementing
them. A plausible risk alone does not authorize production-readiness work.
Keep basic authorization, destructive-action and privacy safeguards. If a safe
happy path cannot be built within scope, explain the blocker and ask rather than
silently adding hardening or bypassing safeguards.

Follow project conventions. Update docs when behavior, APIs, commands, configuration
or workflows change. Document non-obvious contracts beside their owner: lifecycle,
invariants, extension points, effects and failure expectations. Use language-appropriate
documentation and examples for composition, not boilerplate, repeated signatures or
duplicated contracts. If a module's purpose needs vague prose, reconsider its name
or responsibilities instead.

## Select assurance

The default is the minimal happy-path smoke check, not a test suite or review
pipeline. Suggest edge-case, regression, integration, production-like or broader
checks when useful, but obtain confirmation before adding or running them. An
explicit request for such checks authorizes that scope; approval to implement a
feature alone does not. Do not escalate automatically because a change involves
state, interfaces, security or concurrency.

When expanded assurance is approved, select checks for the agreed claim and keep
them cohesive by behavior/boundary using repository placement conventions. Review
critiques correctness/risk; verification executes checks. Independent review and
delegation require their own authority; a fresh self-review is not independent.
Make scope, evidence and non-goals explicit when useful, not a routine template.

## Finish and report

Adapt execution to dependencies, uncertainty and credible new evidence; preserve
valid work rather than restarting by default. Fix regressions caused by the change
within scope and complete agreed integration/validation, not just implementation.
Stop when verified, blocked on input or facing an unauthorized next action; do not
polish indefinitely or repair unrelated defects. Report outcomes, verification scope
and limitations, including skipped practical checks, without narrating every step.
