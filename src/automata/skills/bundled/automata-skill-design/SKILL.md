---
name: automata-skill-design
description: Use when designing, reviewing, or modifying skills—their scope, activation, instructions, supporting assets, or boundaries.
---

# Automata Skill Design

Design compact contracts that improve agent decisions without prescribing every move.

## Scope and Activation

A skill needs a distinct capability or decision, recognizable activation and a useful
outcome—even when conceptual. Otherwise refine an existing owner or leave ordinary
reasoning to the agent. Split independent responsibilities, not every subtopic.

Use minimal frontmatter (`name` and `description`). Keep `description` short and
specific to intent, task state or runtime signals needing specialized guidance;
put details in the body. Review activation, nearby non-activation and overlap with
another skill; no formal evaluation campaign is required.

Use a lowercase, single-hyphen-separated runtime name matching the installed
directory; check collisions with skills and runtime commands.

## Instructions and Composition

Keep portable skills agent-CLI-brand-neutral in names, activation, instructions and
references. Describe capabilities and outcomes, not host branches. Name and scope
runtime-dependent contracts in runtime-specific skills, not portable branches or
counterparts for symmetry. Shared tool bindings and installation belong in tool or
runtime docs. Installing a skill neither installs required extensions nor proves
their interfaces are exposed.

Orient judgment through useful decisions and authority boundaries; let the agent
adapt. Require fixed procedures only for mechanical, interoperability or safety needs.
Action-oriented skills need success criteria, proportionate verification, authorized
corrections and stop/escalation conditions. Authority boundaries remain necessary
regardless of a model's claimed judgment.

Each skill should stand independently and compose through context. Make activation,
inputs, outputs and ownership clear. Describe needed capabilities, evidence or outcomes;
let the agent select skills rather than prescribing named skill invocation. Documentation
and interface links are not invocation instructions. Dependencies need a concrete
interface, handoff or safety reason—not an invocation chain. Leave actors, topology,
timing and message paths flexible when the situation should determine them.

Every instruction should affect behavior. Remove filler and overlap while preserving
decisions, conditions, exceptions and authority. Prefer clear language over brevity
or cryptic abbreviations. Keep internal decisions separate from presentation; require
announced modes, checklists or steps only for a real communication need. Ordinary
response style belongs to character guidance.

## Supporting Assets

Only `SKILL.md` is required; keep its core contract and defaults together. Use
references for on-demand knowledge, examples for general behavior rather than session
policy, templates for formats and scripts for repeated mechanics. Cue optional reading;
moving always-read prose does not reduce context cost. Keep short, coherent contracts
together rather than forcing router structures. Do not add assets for appearance.

Map Automata tools by installed `.agents/tools/...` entry path in
`metadata.automata-tools` (comma-separated for multiple entries), not source paths,
system commands or helpers. Reuse known entries; check changeable prerequisites when
evidence warrants it. Mapping does not prove readiness. Keep scripts inspectable and
document safe use.

## State and Environment Boundaries

Identify ownership before location. Keep mutable agent data outside the package;
define its purpose and lifecycle under the owner's data convention. Keep generated
outputs separate from user inputs with different lifecycles. Host-specific paths
need an owning convention; let the generator implement concrete discovery paths.

Separate setup from normal use and reusable knowledge from runtime state. Retain
findable, verified setup recipes within storage authority when they avoid repeated
work: commands, prerequisites, usage, cleanup and invalidation. Consult before
rediscovery; check changeable prerequisites, repair only invalid parts within authority
and update after verification. Each capability owns validity/invalidation; persist
runtime state only for continuity or recovery. Saved knowledge grants no permission.
Do not impose records or universal schemas. Judgment-only skills need no setup ceremony.
Installation mechanics belong to setup.

Define growth/retention review, cleanup authority and end-of-use conditions for
accumulating data or resources. Distinguish disposable data from needed evidence,
stopping activity from deleting records, and review triggers from deletion permission.
Terminal status does not prove inactivity. Automatic deletion needs an agreed policy,
not universal quotas or per-write checks. Enforce concurrency and deletion safeguards
in tools, not prose alone.

## Modification and Review

Read the whole skill and resolve material ambiguity before editing. Complete approved
changes and verification without repeated permission; ask before exceeding scope or
adding unapproved storage, configuration or integrations. Discussion is not authority
to mutate.

For poor behavior, check missing guidance versus failed application: discovery,
loading, understanding or conflicting instructions. Fix the cause at its owner,
not by adding prose by default. Replace overlap rather than append requests. Review
scope, activation, composition and authority together; explain misplaced additions
or conflicts before implementing. Do not universalize one incident.

Use proportionate behavior/interface checks; wording tests do not prove agent behavior.
Review preservation of decisions, conditions and exceptions, not word count alone.
Above 8000 characters, review repetition or separable supporting material—not an
automatic split or size target.

## Report skill edits

Capture pre-edit baselines for edited skills and supporting files. Report a compact
table: path, bytes and physical lines before → after, and added/deleted lines against
that baseline. Exclude unrelated changes; disclose unavailable baselines, never invent
values. Summarize meaningful changes, verification and limits beside the table. Counts
show growth and churn, not exact tokens or quality; do not optimize wording merely
to lower them. Honor an explicitly requested alternative format.

## Boundaries

This skill owns design and revision, not installation or runtime exposure.
