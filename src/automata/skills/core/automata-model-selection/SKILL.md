---
name: automata-model-selection
description: Use when choosing or comparing AI models for a task, planning model use, or designing solo/team model assignments; also when consulting model preferences or researching evidence that could change a choice.
---

# Automata Model Selection

Choose AI models that fit the work and the user's constraints. Support choices
with a compact comparative guide, not a model encyclopedia or fixed routing table.
Research supports selection; it is not a prerequisite for every choice.

## Choose for the work

Start with the task demands and relevant existing selection guidance and approved
preferences, using the record locations below when that context is not already
available. Apply their agreed scope; distinguish permission and preference from
verified runtime availability. Missing records are unknowns, not an unrestricted
allowed set.

Compare suitable models against a viable alternative. Match the choice to the
work's reasoning, context, tool-use and verification needs, not fixed role labels
such as "best for coding". Consider only decision-relevant constraints; speed and
cost include briefing, review and correction effort, not just token prices.

Give a brief recommendation and its main tradeoff for the plan or assignment.
Reuse sufficient evidence without fresh research. If an uncertainty could change
the choice, resolve it through a focused evidence check or user clarification;
otherwise state the limitation without blocking the work. A plan with no model
choice does not need a model-selection exercise.

## Research what could change the choice

Investigate missing or potentially stale evidence relevant to the decision.
Compare promising candidates with a current alternative; a new release does not
automatically deserve an entry or adoption.

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
the installed skill. These legacy `automata-model-research` data paths remain
canonical after the skill rename; do not migrate or duplicate records merely to
match the new name. Read relevant existing records before writing. Create only
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

This skill owns model recommendations, comparative knowledge and preference
discussion. Planning owns decomposition; teamwork design owns task assignments
and the solo/team arrangement; runtime discovery owns availability checks.
Compose these capabilities when needed, not as a mandatory invocation chain.
Selection and research do not authorize paid trials, new agents, private-data
transfer, installation or runtime configuration changes. Release monitoring and scheduled refreshes require their
own authorization; on-demand freshness checks are the default.
