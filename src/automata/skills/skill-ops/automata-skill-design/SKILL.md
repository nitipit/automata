---
name: automata-skill-design
description: Use when discussing, reviewing, designing, or modifying Automata skills so they stay focused, clarification-first, and light on unnecessary structure.
---

# Automata Skill Design

Design skills as compact contracts for agent behavior. Keep each skill focused,
interactive, and light on structure.

## Principles

- Keep one skill focused on one capability or scope.
- For judgment-oriented skills, define the intended orientation, first useful move, and
  action boundary, then let the agent adapt to the situation. Avoid prescribing an internal
  workflow unless a concrete failure, safety concern, or interoperability requirement
  justifies it. Every additional instruction should materially change agent behavior.
- Keep internal decisions separate from user-visible presentation. Describe what the agent
  should decide or do without requiring it to announce internal modes, labels, checklists, or
  steps unless doing so addresses a concrete communication, safety, auditability, or
  interoperability need. Let the configured character behavior shape ordinary wording.
- Design each ability to stand independently within its scope and compose through context.
  Make relevant relationships discoverable through activation cues, inputs, outputs, and
  ownership boundaries, not mandatory invocation chains. Let the agent decide which
  capabilities to combine; do not make one skill orchestrate its neighbors. Require explicit
  dependencies only where a concrete interface, handoff, or safety boundary needs them.
- Be rigid at mechanical and safety boundaries, but adaptive at coordination and judgment
  boundaries. Use fixed procedures only when repeatability, interoperability, or safety
  genuinely requires them.
- Do not hardcode actors, topology, timing, message paths, or ceremony when agents should
  establish them from context and communication.
- Prefer each `SKILL.md` under 5000-8000 characters. Use the lower end for simple skills and
  the upper end only when the root behavior contract genuinely needs more detail.
- If stable supporting material would make `SKILL.md` too long, move it into
  `references/`, `templates/`, or `scripts/`.
- Write frontmatter `description` for activation matching: natural user requests and task
  situations, not a full behavior summary.
- Use `SKILL.md` for scope, workflow, constraints, boundaries, conventions, and shipped
  defaults.
- Resolve ambiguity through brief user clarification instead of exhaustive branch logic or
  hidden defaults.
- Generalize durable behavior from examples. Avoid session-specific rules.
- Put only important constraints in the skill. Leave ordinary reasoning and obvious cases to
  the agent.
- Ask before writing files, running non-read-only commands, or changing broad scope.

## Skill Existence Test

Do not create a skill only because its principles are useful or nameable. Before creating one,
identify a concrete activation situation, a capability or decision boundary it uniquely owns,
and a meaningful next action or outcome. If the guidance is general behavior, ordinary
reasoning, or a short instruction that fits an existing skill, merge it there or leave it as a
direct instruction. A skill may be conceptual when its activation boundary and post-activation
decision are concrete.

## Structure

Use this shape only when useful:

```text
skill-name/
├── SKILL.md
├── examples/
├── references/
├── scripts/
└── templates/
```

Only `SKILL.md` is required.

- `examples/`: complete, neutral artifacts that teach a contract more clearly than prose
- `references/`: stable reusable guidance that would clutter `SKILL.md`
- `templates/`: reusable output structures or scaffolds
- `scripts/`: repeated mechanical workflows that are safer or faster as code

Use an example when agents benefit from inspecting a realistic complete artifact. Explain
what the example teaches, keep situation-specific policy out of it, and tell agents to adapt
rather than copy it blindly. Prefer a compact example over lengthy duplicate instructions,
but do not add examples or other support directories merely to make a skill look complete.

Keep scripts inspectable and document safe commands before using them.

Repo-local agent data belongs outside the package and with its natural capability owner.
Identify ownership before location. A portable skill should describe the data's purpose,
lifecycle, and owner, then use the applicable owner-scoped data convention instead of
hardcoding a host layout. A skill whose purpose is defining a storage convention may define a
default layout; concrete path resolution may also belong to the tool or CLI implementation
when its mechanics require it.

Keep generated outputs separate from additional local inputs when they have different
lifecycles. Let portable skills describe ownership and discovery behavior while the generator
implements concrete discovery paths. Do not prescribe a generic data workspace without a
concrete use case. A skill that writes durable artifacts should say when to ask for or confirm
the destination.

For skills that accumulate persistent data, define how growth is noticed, when retention
is reviewed, and who may authorize cleanup. Distinguish disposable or rebuildable data
from durable evidence and user inputs. Choose review triggers or limits appropriate to
the data's value and cost, not universal quotas. A soft review threshold is not a hard
storage bound; automatic eviction or deletion requires an agreed policy. Keep checks and
reminders proportionate rather than scanning or interrupting on every write. Describe
responsibilities without prescribing a named skill chain.

For capabilities that create runtime resources or persistent records, define when their
purpose ends and when cleanup is safe. Distinguish stopping activity from deleting
evidence; a terminal status alone may not prove inactivity. Support owner-scoped cleanup,
preserve needed evidence, and place concurrency and deletion safeguards in the tool
rather than relying on prose.

## Frontmatter

Use minimal frontmatter:

```yaml
---
name: skill-name
description: Short activation description for AI agents.
---
```

Treat `description` as the activation surface. It should help an AI agent decide when to
load the skill. Describe observable activation sources—user requests, agent task state,
runtime signals, or tool/event results where applicable. Do not default to “when the user
asks” when the skill can activate from agent or system context. Keep detailed behavior,
workflow, and constraints in the body.

When a skill meaningfully uses an Automata tool, set `metadata.automata-tools` to
comma-separated `.agents/tools/...` entry paths. After activation, invoke mapped entries
without discovery or preflight scans. Do not map source paths, system commands, or helpers.
A packaged tool may stand alone without a skill mapping.

## Setup and Mutation Behavior

When designing a skill that writes files, stores durable state, changes configuration, links
into instructions, or expects future agents to use project-local artifacts, define its
first-time setup behavior.

For environment-dependent abilities, distinguish establishing a working setup from normal use;
separate files or phases are optional. Define acceptance criteria, inspect relevant available
capabilities, and verify the chosen approach before persisting environment-specific facts.
Reuse verified setup with lightweight checks of changeable prerequisites; recover only the
affected setup within existing authority. Executable presence alone is not proof of readiness.
Do not rediscover known mapped tool entries as ceremony or require setup for judgment-only skills.

Compactly cover:

- purpose, ownership boundary, and activation behavior
- where package files, generated files, config, durable data, or runtime artifacts live
- which existing files it may edit, such as `AGENTS.md`, cue files, project docs, or task
  files
- how future agents will discover or activate it
- whether it should offer to link itself from instructions such as `AGENTS.md`

Require confirmation before writing files, mutating configuration, choosing durable storage
locations, or adding integration points.

## Skill Modification

When updating an existing skill, review the whole skill for coherence before proposing edits.
Do not blindly append the requested instruction.

Check whether the change:

- supports the skill's purpose and scope
- fits the workflow and boundaries
- conflicts with or duplicates existing guidance
- should replace, refine, or remove older guidance
- belongs in `SKILL.md` or supporting assets
- generalizes durable behavior instead of encoding a one-off case
- changes the activation surface and needs frontmatter wording updates

If the change would make the skill incoherent, too broad, or contradictory, explain the issue
and propose cleaner wording or structure before editing.

## Boundaries

Every skill should state clear boundaries, especially when nearby skills own related work.
When a proposed skill has multiple responsibilities, suggest splitting it.

Creation owns skill purpose, scope, instructions, boundaries, configuration behavior, setup
contracts, and supporting package assets. Use `automata-setup` for actual
installation and runtime exposure decisions such as source, target, copy versus symlink,
overwrite behavior, and package identity to runtime-name mapping.

## Names

Automata skills may have a canonical package identity and a runtime name. Runtime names must
be lowercase alphanumeric with single hyphen separators and match the target runtime
directory, such as `automata-skill-design`.

Before naming, check likely collisions with bundled Automata skills, project-local skills,
known AI CLI built-ins, and user-installed global skills.

## Review Checklist

Check that a skill has one clear scope, passes the skill existence test, minimal frontmatter,
valid installed-tool mappings when applicable, no duplicated trigger guidance, clear
post-activation decisions when needed, shipped defaults in `SKILL.md`, clear boundaries,
appropriate package directories, coherent durable-artifact
guidance, growth/retention and cleanup authority for accumulating data, neutral and purposeful
examples when present, safe validation guidance when
applicable, and no unnecessary schema/version requirements.

Review modularity and contextual composition:

- Is the skill independently useful within its scope?
- Can the agent recognize when to combine it with other capabilities?
- Can it change without forcing unrelated skills to change?
- Are required dependencies justified by concrete contracts?

For skill updates, verify the edited instruction remains coherent with the full skill rather
than only satisfying the latest requested sentence.

When `SKILL.md` or a reference file exceeds 8000 characters, check whether it should be
shortened, split by topic, or moved into a script/template asset. Extra length should be
justified by stable contract needs, not repetition, padding, or examples.
