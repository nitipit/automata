---
name: automata-goal
description: Use when defining or reviewing durable project goals, sub-goals, or instruction links that keep future work aligned.
---

# Automata Goal

Design goals as durable alignment, not task management.

## Core Rule

The main goal describes the desired product or outcome. Sub-goals describe
stable review perspectives that future work can be judged against.

## Workflow

1. Understand the product outcome the user wants to preserve.
2. Reuse the approved goal location. If none is established, ask before writing
   or moving files; offer `goal/main.md` and `goal/sub-goals/` as a simple option.
3. Explain how the goal files will be used: agents should read them to align
   implementation and review decisions, not to find task status or step-by-step
   work.
4. Ask whether the user wants goal paths linked from an appropriate
   `AGENTS.md`. If yes, identify the relevant `AGENTS.md`, propose the minimal
   reference text, and confirm before editing it.
5. Identify the few enduring perspectives relevant to consequential decisions.
6. Test each proposed sub-goal as a review lens:
   - It should remain useful after the current implementation changes.
   - It should evaluate many kinds of work, not only one task.
   - It should describe a perspective, not a phase or step.
   - It should avoid status, ownership, commands, and implementation details.
   - The set should remain easy to consult when a decision needs alignment.
7. Write concise goal text, preferably one paragraph per goal file.
8. Move implementation details to code, tests, ADRs, cues, or planning notes
   instead of keeping them in goal files.

## AGENTS.md Linking

When the user wants goals to guide future sessions, help connect them to the
agent startup path.

- Prefer the closest relevant `AGENTS.md` for the intended working context.
- Link goal files for direction reviews and consequential architecture/product
  decisions, not as mandatory reading before every small edit.
- Keep the `AGENTS.md` text small; it should point to goal files, not duplicate
  them.
- Confirm the path and wording before editing.
- If multiple `AGENTS.md` files could apply, explain the choice and ask the
  user which scope should own the link.

## Defaults

Use the smallest set that captures the important independent perspectives.
Do not add goals to fill a quota or split one perspective into task-sized pieces.

## Boundaries

- Do not turn sub-goals into milestones, TODOs, task phases, or implementation
  plans.
- Do not store detailed architecture, command usage, current status, or
  acceptance criteria in goal files by default.
- Do not create, move, or rewrite goal files during discussion unless the user
  confirms the change.
- Do not silently choose a goal directory or `AGENTS.md` integration point when
  the user has not confirmed it.
- If a user wants execution planning, switch to planning behavior after the
  goals are clear.
