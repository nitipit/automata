---
name: automata-model-research
description: Use when consulting or updating model-selection knowledge, researching new or changed AI models, or discussing the user's permitted and preferred models. Not for routine assignments when the needed guidance is already in context.
---

# Automata Model Research

Help agents choose models for tasks through a compact comparative guide, not a
model encyclopedia or fixed routing table. Research what could change a useful
choice; a new release does not automatically deserve an entry or adoption.

## Research for a decision

Start with the user's question, relevant task demands, existing guidance and
approved preferences. Compare usable models and promising candidates against a
current alternative. Explain when the difference matters, rather than assigning
universal roles such as "best for coding". Consider only decision-relevant
constraints; speed and cost include correction effort, not just token prices.

Prefer primary sources for identity, release changes and supported features.
Use relevant independent evidence or task observations for practical strengths
and weaknesses. Distinguish vendor claims, observed results and tentative
inferences. A benchmark or one failed task is not a general capability ranking;
check the task, harness and thinking settings before transferring conclusions.
Weigh conflicting evidence by relevance and provenance, not merely by which file
is local. Public availability does not establish availability in the user's runtime.

Stop when the evidence supports the choice, or state what remains unknown and
whether it matters. Give a brief recommendation, its main tradeoff and useful
references. Do not run an exhaustive survey or benchmark campaign by default.

## Keep evidence fresh

Use the current date when judging freshness or interpreting relative release
claims. Identify the provider and exact model/version where known; mark moving
aliases and unresolved mappings rather than guessing an underlying version.

Recheck the relevant evidence when a release, alias or runtime change, conflicting
experience, or an important decision could invalidate the recommendation. Age is
a signal, not an expiry rule: an old version-pinned observation can remain useful,
while yesterday's alias-based guidance may already be stale. Refresh only what
could change the decision. If sources cannot be verified, say so and preserve
uncertainty instead of presenting old knowledge as current.

Keep source publication dates separate from when evidence was checked. Checking
documentation is not testing a model. Update only the dates and claims actually
rechecked; do not make an entire guide appear fresh after inspecting one entry.
Do not generalize old-version results to a replacement without evidence.

## Retain a small selection guide

For each useful model/version, keep a short note with:

- **Choose when:** the task conditions where it offers an advantage over an
  alternative, or a clearly tentative reason to consider it.
- **Tradeoff:** the main reason to choose something else or investigate further.
- **Basis and freshness:** what supports the judgment and when it was checked;
  label actual tests separately and retain relevant setup differences.
- **References:** a few direct links or evidence anchors for deeper investigation.

Prefer a few decision-useful sentences over specification tables, scores or raw
research dumps. Leave unknowns explicit. Update an existing note when appropriate
rather than appending release news indefinitely; retain still-useful version
comparisons and do not delete unique evidence merely because it is old.

Keep mutable records outside the skill package. Use
`~/.agents/var/skills/automata-model-research/selection-guide.md` for reusable
cross-project knowledge and `preferences.md` beside it for approved preferences.
Project-specific observations and explicit overrides use the corresponding files
under `.agents/var/skills/automata-model-research/`, relative to the project, not
the installed skill. Read relevant existing records before writing. Create only
useful records within authorized storage scope, not empty scaffolding. Keep
private project evidence local unless sharing it more broadly is authorized.

## Discuss preferences without changing authority

Keep recommendations separate from what the user permits or prefers. Explain a
meaningful proposed change and confirm it before updating durable preferences;
a request to research a model does not authorize adding it to an allowed list.
Capture only choices the user makes: permitted, preferred or excluded models,
task or thinking-level preferences, and constraints when relevant. Clarify whether
a list is an exclusive allowed set or merely favorites when that changes a choice.
Absence from a preference list is neither permission nor an automatic prohibition.

Record the agreed scope and confirmation date. Apply explicit current instructions
within their scope; use project preferences for explicitly overridden choices and
global preferences for the rest. Do not silently relax a prohibition through an
ambiguous override. Respect existing capability-specific preferences; resolve
material conflicts rather than migrating or overwriting another owner's settings.
Do not promote a one-task exception into a lasting global preference.

Research notes may change with evidence; approved preferences do not change just
because a better model appears. Saved preferences are guidance, not runtime
configuration or proof of access. Leave active models and thinking levels alone
unless a separate authorized action changes them.

## Boundaries

This skill owns model-selection knowledge and preference discussion. Work design
owns task assignments; runtime discovery owns availability checks. Ordinary
selection can reuse existing guidance without fresh research. Research does not
authorize paid trials, new agents, private-data transfer, installation or runtime
configuration changes. Release monitoring and scheduled refreshes require their
own authorization; on-demand freshness checks are the default.
