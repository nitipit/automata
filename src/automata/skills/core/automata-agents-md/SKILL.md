---
name: automata-agents-md
description: Use when configuring or reviewing AGENTS.md instruction surfaces, character components, or durable agent behavior.
---

# Automata AGENTS.md

Configure the intended instruction surface, not every file an agent might read.
Keep durable behavior separate from temporary assignments and runtime configuration.

## Scope and authority

Inspect the relevant instruction hierarchy and available character components.
Identify the runtime, intended scope, and target file: personal/global, repository,
or nested working context. Do not assume the nearest file is always the owner.
If several surfaces could apply, explain the choice and resolve it before editing.

Discuss material behavior choices before writing. Drafts, examples, labels, and
partial agreement are not permission to edit. Apply an explicitly approved setup
or change without asking again for the same scope; return unresolved personality,
authority, or integration decisions to the user. Do not extend approval to other
instruction surfaces.

For a new configuration, consider role, request detection, follow-up behavior, and
discussion versus implementation. For a targeted revision, stay with the affected
behavior rather than repeating a full setup interview.

## Character components

Prefer existing reusable components when they express the confirmed intent.
Inspect their rendered contents rather than inferring behavior from names:

```bash
automata character list
automata character compose --personality <name> --behavior <name>
automata character compose --personality <name> --behavior <name> --agents-md <path>
```

Choose components interactively when the request leaves material choices open;
do not require another selection when the user has already specified it. Render
or adapt only into the confirmed destination. For generated surfaces, update the
owning inputs so regeneration preserves the change.

Labels are discussion shorthand, not instruction text. For example, `Assistant`
can mean an active thinking partner who challenges assumptions and suggests better
approaches. Follow-up preferences might be `Quiet` (stop after completion),
`Focused` (one useful next step), or `Forward` (a short prioritized set). Translate
confirmed choices into plain language rather than imposing these labels or defaults.

## Instruction design

Distinguish action requests from thoughts, preferences, observations, and
acknowledgements. Low-intent messages usually need a brief response, not an automatic
plan or implementation; clarify only when ambiguity or a material risk warrants it.

Keep broadly loaded guidance orienting. Link specialized material with cues for
when it matters, not a reading checklist before every edit. Check overlapping
instructions for contradictions instead of appending compensating rules.

Keep additional local instructions in the appropriate skill-owned agent-data location
and use the generator's supported discovery mechanism when available. Do not duplicate
their contents into every generated file or invent host paths in portable guidance.

## Verify and finish

Review the resulting Markdown against the approved behavior and intended scope.
When practical, use the runtime's prompt/debug discovery to confirm visibility;
distinguish a correct file from instructions actually loaded by a session. Report
what changed and any unverified discovery or reload requirement.

## Boundaries

This skill owns durable instruction configuration, not temporary delegation briefs,
multi-session setup, runtime-specific configuration, or broad repository policy.
A spawned agent uses its intended working directory and applicable AGENTS.md hierarchy;
put temporary responsibility, scope, permissions, return paths, and evidence in its
assignment instead of a new durable instruction file. Do not edit instructions merely
because another skill could benefit from being linked there.
