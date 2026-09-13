---
name: automata-agents-md
description: Use when configuring, reviewing, or adapting Automata agent instructions through AGENTS.md, including character, behavior, and later updates.
---

# Automata AGENTS.md

Configure or review agent instructions, character, and behavior through an intended `AGENTS.md` surface.

Treat labels such as `Assistant`, `Quiet`, `Focused`, or `Forward` as discussion shorthand,
not final instruction text. Convert confirmed choices into plain-language instructions.

## Setup Flow

For requests such as "create agents", "set up the default agent", "configure this runtime",
or behavior changes, start with read-only review and discussion before writing.

1. Inspect existing instruction files, available character components, and nearby
   conventions.
2. Identify the target runtime, scope, and target `AGENTS.md` file. If multiple
   instruction surfaces could apply, explain the scopes and ask which one to modify.
3. Discuss the setup before writing. At minimum cover `Role`, `Request Detection`,
   `Follow-Up Behavior`, and discussion-versus-implementation behavior.
4. For personality, communication style, or user-facing behavior, configure character
   choices interactively. Ask which personality and behavior components should apply unless
   the user's request already gives a complete, unambiguous selection.
5. Present the final proposed setup and ask for explicit confirmation.
6. Generate or update only the confirmed instruction surface, using the target CLI when it
   supports generation.
7. When additional local instructions should remain separate from a generated surface, keep
   them in the appropriate skill-owned agent-data location for the current environment and
   use the generator's supported discovery mechanism.
8. Validate by reviewing the resulting Markdown and, when practical, using the target CLI's
   prompt/debug discovery to confirm the content is visible.

Treat drafts, examples, labels, and partial agreement as discussion artifacts. They are not
approval to edit files. Approval to write should be explicit, such as "confirm", "apply",
"write it", "update the file", or equivalent.

## Character Components

When configuring personality, communication style, agency level, or user-facing behavior,
check for reusable character components before drafting new instruction text.

Use packaged character components when present. The CLI can render them as Markdown for the
agent to read:

```bash
automata character list
automata character compose --personality <name> --behavior <name> > AGENTS.md
automata character compose --personality <name> --behavior <name> --agents-md <path> > AGENTS.md
```

Character configuration is interactive by default. Discover available components, present
them as choices, explain their meaning briefly from their rendered file contents, and
configure them step by step. Do not assume specific component names beyond the component
layout.

Do not apply character components silently. Treat them as reusable source material that can
be referenced, copied, adapted, or generated into the chosen `AGENTS.md` after explicit
confirmation.

## Role

Suggested label: `Assistant`

Meaning:
1. Act as an active thinking partner.
2. Clarify goals, challenge unclear ideas, and point out likely issues.
3. Suggest stronger approaches when they materially improve the outcome.
4. Use a different label or plain-language description when it fits better.

## Follow-Up Behavior

Suggested label: `Focused`

Scale:
1. `Quiet`: Complete the requested task and stop unless a next step is necessary to make
   the result usable.
2. `Focused`: Complete the requested task, then suggest the single most relevant next step
   when it would help.
3. `Forward`: Complete the requested task, then suggest a short priority-ordered list of
   useful next steps when it would help.

## Request Detection

Configure the agent to distinguish requests from low-intent messages before choosing
discussion, implementation, or follow-up behavior.

When the user shares a thought, preference, observation, reaction, or acknowledgement without
asking for action, the agent should respond briefly by acknowledging or confirming the
understood concept.

Do not treat low-intent messages as requests to suggest options, make a plan, implement
changes, run tools, or produce detailed analysis unless the user asks, the meaning is
unclear, or a material risk needs to be surfaced.

## Target Surface

Use the user's intended `AGENTS.md` as the runtime instruction surface. It may be maintained
directly or generated from confirmed inputs. Support personal/global, repo-local, and nested
working-context files without assuming that the nearest or global file is always the intended
owner.

A spawned agent should begin in the intended working directory and use the applicable
`AGENTS.md` hierarchy. Keep temporary responsibilities, task scope, permissions, return
paths, and expected evidence in its delegation brief rather than writing them into a
separate durable instruction file.

1. Identify the scope and target file before editing.
2. When the intended location is unclear or multiple instruction files may apply, explain
   the candidate scopes and ask which `AGENTS.md` to modify.
3. Create, generate, or modify the chosen `AGENTS.md` only after the setup text is confirmed.
4. Keep additional local instructions separate when the chosen generation mechanism supports
   discovery, using their appropriate skill-owned agent-data location.
5. Route delegation briefs, runtime profiles, and tool-specific config files to their
   separate workflows.

## Work Behavior

Use co-pilot discussion discipline while configuring agent instructions: discuss ambiguous
agent behavior and setup choices first, do not switch from discussion into editing until the
user explicitly confirms the final proposed text or change, and stay on the section being
revised until it is settled.

## Boundaries

1. Scope this skill to configuring or reviewing agent instructions through `AGENTS.md`.
2. Use the user-confirmed `AGENTS.md` as the runtime instruction surface for this skill.
3. Treat discussion labels as shorthand that becomes plain-language instructions.
4. Support CLIs that follow the standard convention.
5. Clarify the target location when scope is unclear instead of assuming default, repo-local,
   or global instructions.
6. Write instruction changes after confirmation.
7. Route runtime-specific config changes to another workflow for tool-specific setup.
8. Keep delegation briefs, multi-session setup, and broader repo policy work in separate
   workflows; do not encode temporary assignments as durable agent instructions.
