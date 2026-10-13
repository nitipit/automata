---
name: automata-software-development
description: Use for software implementation, debugging, refactoring, code review, or project build/test/environment work that needs engineering judgment.
---

# Automata Software Development

Turn an approved goal into a working, maintainable, tested change. Apply
engineering judgment, not a fixed workflow or technology stack. Deliver the
requested happy path, not production readiness by default.

1. **Understand the change.** Inspect relevant code, callers, project configuration,
   contracts and state ownership. Consult verified setup recipes before
   rediscovering commands. Clarify uncertainty that materially affects the work;
   distinguish observed facts from assumptions.

2. **Keep scope disciplined.** Reuse existing solutions and project conventions.
   Avoid speculative features, abstractions and hardening. Make ordinary internal
   decisions within approval; ask before material changes to scope, dependencies,
   APIs, data or security. Preserve basic authorization, privacy and data-loss
   safeguards. Approval for one change does not authorize unrelated repairs.

3. **Design for understanding.** Keep responsibilities cohesive, interfaces clear
   and coupling limited. A typical change should require understanding only a
   small part of the system. Extend the right owner, not the nearest file; align
   shared contracts before independent work. Readability beats the smallest diff.
   Prefer source files up to 300 lines; 301–500 can remain cohesive. Review
   boundaries above 500 and strongly favor splitting above 800, without arbitrary
   fragmentation or unrelated refactoring. Exclude generated code and fixtures.

4. **Implement completely.** Build the smallest integrated solution. Update affected
   callers, fixtures, documentation and configuration; explain non-obvious
   contracts beside their owner. Use authorized project commands and isolate
   environments when synchronization could disrupt other work. Retain useful,
   verified setup knowledge outside the skill package, not secrets or transient
   process handles.

5. **Leave repeatable evidence.** Save focused tests for new or changed non-trivial
   behavior. Prefer unit tests for isolated logic and integration tests for
   cross-component boundaries; neither substitutes for the other's useful checks.
   For bug fixes, add a regression test that fails for the defect and passes with
   the fix when practical. Assert meaningful behavior; do not mock away what is
   being verified. Run affected tests and distinguish environment failures from
   product failures. A smoke check is supplementary, not a substitute for saved
   tests. Explain concrete reasons for skipped testing. Trivial or prose-only
   changes need no new tests unless behavior changes. Focused tests are part of
   implementation; broader assurance campaigns remain separately scoped.

6. **Finish honestly.** Fix regressions caused by the change within scope. Stop when
   the approved outcome and affected tests are verified, or report the blocker;
   do not polish indefinitely. Report what works, what was verified and remaining
   limits. Distinguish implemented, tested, committed and published results.

Setup recipes belong under `.agents/var/skills/automata-software-development/`
or approved user defaults under `~/.agents/var/skills/automata-software-development/`.
Project constraints take precedence; recipes do not authorize installations or
shared-environment changes.
