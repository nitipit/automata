---
name: automata-stateful-workflow
description: Use when designing or reviewing applications with multi-step workflows, durable business state, external side effects, or recovery requirements.
---

# Automata Stateful Workflow

Design and review applications where workflow determines what may happen next,
while durable state and evidence establish what actually happened.

## First Useful Move

Understand the business outcome before choosing tools. Identify the records whose
lifecycles matter, their stable identities, the actions that change them, and the
external effects those actions produce. Inspect existing code and contracts when
reviewing an application; distinguish observed behavior from intended behavior.

Clarify uncertainty that changes correctness or safety, especially what counts as
completion, what may be repeated, and who may authorize irreversible actions.
Agree on consequential design changes before implementing them.

## State and Transitions

- Give business records explicit identities. Distinguish a business operation
  from its individual attempts, incoming events, and source versions.
- Define meaningful states and permitted transitions, including prerequisites,
  ownership, and the evidence required to declare completion.
- Separate durable business facts from derived views and temporary execution
  details. A running process or successful command exit is not business completion.
- Keep related records consistent. Completing a grouped operation must account
  for every represented record, not only its anchor.
- Decide how corrected inputs supersede earlier versions without losing the
  evidence needed to explain previous results.

Use the smallest state model that explains valid progress and recovery. Do not
introduce event sourcing, a workflow engine, or a new database merely because the
application has multiple steps.

## External Effects and Recovery

Treat local state updates and external effects as separate failure boundaries
unless a real shared transaction guarantees otherwise.

- Define duplicate detection and idempotency around the business operation, not
  just a process invocation. Establish what happens on redelivery and retry.
- Consider crashes before an effect, after an effect but before recording it, and
  during partial completion. Preserve enough evidence to resume or reconcile.
- Treat an ambiguous external outcome as unknown, not automatically failed.
  Prefer readback, an external operation identifier, or reconciliation before
  repeating a potentially duplicate action.
- Distinguish retryable errors, invalid inputs, and outcomes requiring operator
  review. Bound retries and make held work visible.
- Define safe ownership for concurrent execution using mechanisms appropriate to
  the application. Account for expired leases, stale workers, and conflicting
  updates when those risks exist.
- Respect authorization and destination contracts. A retry or recovery path must
  not bypass the safety gates used by normal execution.

Do not claim exactly-once effects without proving the relevant boundary. Where
that guarantee is unavailable, state the limitation and design safe reconciliation.

## Evidence and Observability

Derive progress from persisted facts and verified outcomes. Keep operational
health separate from workflow health: an active service may still have blocked,
held, stale, or failed work.

Retain enough provenance to explain which input produced which outcome and why
an action was taken. Avoid secrets and unnecessary payload duplication in logs.
Identify who owns durable records, attempt history, and rebuildable views; agree
on retention and cleanup authority rather than deleting evidence implicitly.

For external writes, choose verification proportional to the effect: destination
identity, returned operation IDs, readback, or business totals as appropriate.
Do not rename or replace downstream interfaces without checking their consumers.

## Design and Review Outcomes

For new applications, propose the smallest coherent record and transition model,
including side-effect boundaries and recovery behavior. Adapt the presentation to
what the user needs to decide; no fixed diagram or document is required.

For existing applications, trace a representative record through the real
workflow. Report concrete gaps with evidence, impact, and the narrowest useful
repair. Do not turn a localized defect into an unsolicited architecture rewrite.

Validate the relevant failure boundaries, not only the happy path. Select tests
for risks present in the application: duplicate inputs, corrected versions,
concurrent claims, interrupted writes, ambiguous outcomes, partial completion,
and restart recovery. Check that reported completion matches business outcomes.

## Boundaries

This skill owns workflow/state design and review, not general coding conventions,
routine production operations, or permission to access live services.

It is storage-, framework-, and deployment-independent. Discover local repository
conventions rather than prescribing paths, services, actors, or technology.

No setup files or runtime state are required. Before creating design artifacts,
changing application files, choosing durable storage, or adding instruction
links, confirm the requested scope and destination. Do not automatically modify
AGENTS.md or install integrations. Skill installation and runtime exposure are
separate from authoring this package.
