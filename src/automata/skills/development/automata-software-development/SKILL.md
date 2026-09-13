---
name: automata-software-development
description: Use for coding, refactoring, debugging, or code review tasks that need minimal, clear implementation, ambiguity handling, pragmatic tradeoffs, or concise suggestions without expanding scope.
---

# Automata Software Development

## Principles

- Implement only explicitly requested behavior.
- Prefer simple and direct solutions.
- Keep code changes minimal and easy to review, but do not optimize diff size at the
  expense of clear module boundaries or future context cost.
- Minimize context coupling: organize code and tests into cohesive units that can be
  understood, changed, and verified without loading unrelated implementation.
- Avoid overengineering, premature abstraction, and unnecessary fragmentation.
- Ask for clarification when requirements, scope, or risk are ambiguous.
- Suggest better approaches briefly, but do not implement them without approval.
- Use language-specific skills for stack/tool conventions when applicable.

## Development Phase

Before building on an uncertain assumption, use the smallest executable check in a
representative, authorized environment. Exercise the boundary whose behavior matters:
browser-dependent assumptions need real browser evidence, while pure logic may need only a
direct test. Mocks isolate concerns but do not establish behavior of the boundaries they
replace. A small implementation slice may be the proof; do not require a separate prototype
for every change.

Prove a minimal integrated path early, then extend it. Do not add generalized guardrails,
hardening, or defensive abstraction before a concrete threat, boundary, or acceptance
requirement justifies it.

Keep only the minimum protection needed to avoid an unintended capability,
destructive action, or privacy exposure. Record deferred hardening explicitly
when it matters; do not silently turn a prototype into a security architecture.

## Avoid By Default

Unless explicitly required, avoid:

- Excessive try/except
- Heavy validation
- Large abstractions
- Extra configuration systems
- Logging scaffolding
- Defensive edge-case handling
- Premature optimization
- Broad refactors

## Coding Style

- Prefer readable code over clever code.
- Prefer modifying existing code when it remains the right responsibility owner; do not
  append new behavior to an unrelated module merely to avoid creating a file.
- Keep functions focused and small.
- Keep production and test files cohesive. Place tests by behavior or responsibility
  instead of accumulating unrelated cases in one broad test file.
- Prefer files that stay easy to scan, roughly 500-1000 lines when practical. Treat size as
  a signal, not the design rule. Extract cohesive responsibilities before a file becomes a
  context-heavy monolith; avoid arbitrary line-count splitting and tiny pass-through files.
- Maintain existing project conventions.
- Use clear naming.

## Documentation

- Update documentation when behavior, commands, APIs, configuration, or
  user-facing workflows change.
- Prefer concise, useful comments and docs over boilerplate.
- Do not add comments that merely restate obvious code.
- If documenting a confusing design requires vague explanation, consider whether
  names, structure, or responsibilities should be clarified instead.

## Architecture

The plan aligns intent and constraints; it is not a file-editing checklist. For larger
changes, reason through logical composition: systems, subsystems, modules, and functions.
Understand each part through its responsibility, local logic, and dependency contracts;
decompose or inspect deeper only where needed. This model need not mirror directories,
assign each component to one parent, or prescribe fixed module counts.

Let interfaces, signatures, and focused comments carry the useful structure. Do not require
another design document or specify every internal function upfront. Define shared inputs,
outputs, state ownership, and important invariants sufficiently for independent work;
leave internal implementation flexible.

Implement coherent responsibilities, even across files. Parallelize where boundaries permit
independence, not merely because files differ. When a shared contract changes, align affected
owners and verify compatibility before building further on it; do not silently diverge or
change another owner's module for convenience.

Do not build on unclear or broken foundations. For risky changes, inspect the relevant
dependency and execution flow, distinguishing confirmed relationships from assumptions.
Use diagrams or new patterns only when they resolve a concrete problem.

## Workflow

Use stable constraints with adaptive execution. Choose order, granularity, concurrency, and
the lowest sufficient assurance from dependencies, uncertainty, and risk, not a universal
sequence. Make routine internal decisions within approved scope without repeated confirmation.

Inspect relevant code and keep planning proportional to the work. Interleave coherent changes
with the selected checks rather than leaving integration until every module is finished.
Reassess affected decisions when relevant, credible new information changes assumptions,
constraints, or available approaches. Adapt the implementation model or plan where useful,
preserving valid work rather than restarting by default. Explain material decisions when
useful or asked; summarize outcomes, verification scope, and remaining limitations without
narrating every internal step.

## Modular Assurance

Treat implementation, review, and verification as composable activities rather than a fixed
team pipeline. One owner may perform more than one activity for low-risk work; use separate
owners only when independent judgment materially improves confidence.

Choose the lowest sufficient level:

- **Direct**: documentation, formatting, or a small isolated change. Implement and run a
  relevant quick check when one exists.
- **Focused**: a normal code change. Implement and run targeted tests or checks; do not add a
  separate review or full-suite run by default.
- **Independent**: public interfaces, cross-module boundaries, security, data, concurrency,
  build configuration, or meaningful uncertainty. Add an independently scoped review and
  focused verification.
- **Full**: release readiness, high-blast-radius changes, or an explicit request. Combine
  independent review with the relevant suite, build, integration, or acceptance checks.

For every selected activity, state its scope, expected evidence, and what it must not repeat.
Review critiques correctness and risk; verification executes agreed checks; neither silently
expands into the other's work. Use the shortest checks that can detect the relevant regression.

## Test Boundaries

- Put direct module or API behavior in unit tests organized to mirror the
  production module structure.
- Put command-line invocation behavior in dedicated CLI tests.
- Put package-resource checks, external-process checks, and runtime-tool
  behavior in integration tests.
- Split mixed tests by boundary rather than leaving direct API assertions in
  CLI test files.
- Follow the repository's established test directories and filename patterns
  for exact placement.

## Boundaries

- Do not expand product scope or add extra features without approval.
- Do not introduce abstractions, configuration systems, logging scaffolding, or defensive edge-case handling unless they are required.
- Ask before changing public APIs, data models, persistence, security behavior,
  dependencies, build systems, generated files, or broad architecture.
- Do not skip practical repository validation without saying so.
