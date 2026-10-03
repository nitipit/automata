---
name: automata-skill-design
description: Use when designing, reviewing, or modifying skills—their scope, activation, instructions, supporting assets, or boundaries.
---

# Automata Skill Design

Design compact contracts that improve agent decisions without prescribing every move.

## Scope and Activation

Create a skill only when it owns a distinct capability or decision, has a recognizable
activation situation, and leads to a useful action or outcome. Otherwise refine an
existing owner or leave ordinary reasoning to the agent. Conceptual skills need a
concrete post-activation purpose too.

Keep one coherent scope. Split independent responsibilities, not every subtopic.
Write frontmatter `description` for recognition: user intent, task state, or runtime
signals that need this skill's specialized guidance, not broad everyday activities.
Keep descriptions short and distinguish nearby capabilities. Review a situation
where the skill should activate, a nearby one where it should not, and overlap
with another skill. This need not become a formal evaluation campaign. Put detailed
behavior in the body. Use minimal frontmatter (`name` and `description`).

Choose a lowercase, single-hyphen-separated runtime name matching the installed
directory. Check likely collisions with existing skills and runtime commands.

## Instructions and Composition

Keep portable skills agent-CLI-brand-neutral, including names, activation
descriptions, instructions and supporting references. Describe capabilities,
decisions and required outcomes rather than branching workflows by host.
When a skill genuinely requires a particular runtime's extension or interface
contract, name and scope it explicitly for that runtime. Keep that contract in
the runtime-specific skill instead of adding host branches to a portable skill;
do not create counterparts just for symmetry. Shared tool bindings and runtime
installation details belong in tool or runtime documentation. Installing a skill
does not install its required extension or establish that its interface is exposed.

For judgment, establish orientation, useful decisions, and authority boundaries;
let the agent adapt. Require fixed procedures only for concrete mechanical,
interoperability, or safety needs. Every instruction should affect behavior.
For action-oriented skills, define success, proportionate verification, authorized
corrections, and when to stop or escalate. Preserve authority boundaries across
models; do not assume a model's claimed judgment makes them unnecessary.

Use direct wording. Remove filler, repeated ideas, and unnecessary qualifiers.
Combine overlapping instructions while preserving conditions, exceptions, and authority
boundaries. Prefer clarity over the shortest text; avoid cryptic abbreviations.
Judge revisions by whether they preserve intended decisions, not word count alone.

Keep internal decisions separate from user-visible presentation. Do not require
announcing modes, checklists, or steps unless that communication serves a real need.
Leave ordinary response style to character guidance.

Each skill should stand independently within its scope and compose through context.
Make activation cues, inputs, outputs, and ownership boundaries clear. Don't instruct
the agent to load or invoke another skill by name. Describe the capability, evidence,
or outcome needed; let the agent choose relevant skills from their activation
descriptions. Links to documentation or shared interface contracts are not invocation
instructions. Require dependencies only where a concrete interface, handoff, or safety
boundary needs them—not mandatory invocation chains. Avoid fixed actors, topology,
timing, or message paths when the situation should determine them.

## Supporting Assets

Only `SKILL.md` is required. Keep its core contract and shipped defaults together.
Use references for on-demand knowledge, examples for clearer demonstrations,
templates for reusable formats, and scripts for repeated mechanics. Do not create
assets for appearance. Moving always-read prose does not reduce context cost.
Separate optional workflows with clear cues for selective reading; keep short,
coherent contracts together rather than forcing every skill into a router.
Examples should teach general behavior, not encode one session's policy.

When using an Automata tool, map its installed `.agents/tools/...` entry path in
`metadata.automata-tools` (comma-separated for multiple entries). Do not map source
paths, system commands, or helpers. Reuse known entries without redundant discovery;
check changeable prerequisites when evidence warrants it. A mapping is not proof
that the environment is ready. Keep scripts inspectable and document safe use.

## State and Environment Boundaries

Identify ownership before location. Keep mutable agent data outside the package;
describe its purpose and lifecycle using the applicable owner-scoped data convention.
Avoid host-specific paths unless the capability owns that convention. Let the
generator implement concrete discovery paths. Keep generated outputs separate from
user inputs with different lifecycles.

For environment-dependent skills, distinguish setup from normal use. When setup
requires discovery or experimentation, save a verified recipe in a suitable agent-data
location within existing storage authority: working commands, prerequisites, usage
and cleanup procedures, and invalidation conditions. Make it findable on later use
and consult it before repeating discovery. Reuse it with lightweight checks of
changeable prerequisites; repair or rediscover only what is invalid within existing
authority, then update the recipe after verification. Saved knowledge does not grant
permission.

Separate reusable setup knowledge from temporary runtime state. Each capability owns
its validity checks and invalidation conditions; persist runtime state only when
continuity or recovery requires it. Do not mandate records or a universal schema:
retain knowledge only when it avoids useful work being repeated. Judgment-only skills
need no setup ceremony. Installation mechanics belong to `automata-setup`.

For accumulating data or runtime resources, establish growth/retention review,
cleanup authority, and when use has ended. Distinguish disposable material from
needed evidence, stopping activity from deleting records, and review thresholds
from deletion permission. A terminal status alone does not prove inactivity.
Automatic deletion needs an agreed policy; avoid universal quotas or checks on every
write. Put concurrency and deletion safeguards in tools, not prose alone.

## Modification and Review

Review the whole skill before editing. Resolve material ambiguity, then carry out
approved changes and verification without repeated permission. Ask before exceeding
scope or adding unapproved storage, configuration, or integration changes.
Discussion alone does not authorize mutation.

When revising after poor agent behavior, distinguish missing guidance from failed
application. Check whether the instruction was discoverable, loaded, understood,
or contradicted elsewhere in the instruction stack. Fix the cause at its owner;
more prose does not necessarily improve behavior.

Replace or remove overlapping guidance rather than appending each new request.
Check scope, activation, composition, and authority together. If an addition belongs
elsewhere or creates a conflict, explain that before implementing it. Do not turn
one observed incident into a universal rule.

Validate the affected behavior or interface with proportionate checks; wording tests
alone do not establish agent behavior. Ensure the revision preserves decisions,
conditions, and exceptions. Keep simple skills short; above 8000 characters, review
for repetition or separable supporting material, not an automatic split or size target.

## Report skill edits

Capture each skill file's pre-edit baseline. In the completion report, use a compact
table with file paths, byte size before → after, total physical lines before → after,
and lines added/deleted relative to that baseline. Include supporting files when
edited, not only `SKILL.md`. Do not count unrelated pre-existing changes as this
task's work; if a baseline is unavailable, label that limit rather than inventing
before-values. Pair the table with meaningful changes, verification and limitations.
Size and line counts show growth and churn, not exact token usage or skill quality;
do not optimize wording merely to reduce them. Honor an explicitly different
reporting format requested by the user.

## Boundaries

This skill owns design and revision, not installation or runtime exposure.
