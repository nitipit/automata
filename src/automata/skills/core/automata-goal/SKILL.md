---
name: automata-goal
description: Use when creating, redesigning, reviewing, configuring, or maintaining project goals, sub-goals, goal files, product direction, durable alignment documents, or AGENTS.md links to goals so goals stay as review perspectives rather than task lists, implementation plans, status reports, or architecture notes.
---

# Automata Goal

Design goals as durable alignment, not task management.

## Core Rule

The main goal describes the desired product or outcome. Sub-goals describe
stable review perspectives that future work can be judged against.

## Workflow

1. Understand the product outcome the user wants to preserve.
2. Ask where goal files should live before writing or moving files. Offer a
   simple default such as `goal/main.md` and `goal/sub-goals/`, but let the
   user choose a different file or directory layout.
3. Explain how the goal files will be used: agents should read them to align
   implementation and review decisions, not to find task status or step-by-step
   work.
4. Ask whether the user wants goal paths linked from an appropriate
   `AGENTS.md`. If yes, identify the relevant `AGENTS.md`, propose the minimal
   reference text, and confirm before editing it.
5. Identify the few enduring perspectives that should review every meaningful
   implementation.
6. Test each proposed sub-goal as a review lens:
   - It should remain useful after the current implementation changes.
   - It should evaluate many kinds of work, not only one task.
   - It should describe a perspective, not a phase or step.
   - It should avoid status, ownership, commands, and implementation details.
   - The full set should stay small enough to read before starting work.
7. Write concise goal text, preferably one paragraph per goal file.
8. Move implementation details to code, tests, ADRs, cues, or planning notes
   instead of keeping them in goal files.

## AGENTS.md Linking

When the user wants goals to guide future sessions, help connect them to the
agent startup path.

- Prefer the closest relevant `AGENTS.md` for the intended working context.
- Add a compact instruction to read the goal files when starting work,
  understanding the repo, reviewing direction, or making architecture/product
  decisions.
- Keep the `AGENTS.md` text small; it should point to goal files, not duplicate
  them.
- Confirm the path and wording before editing.
- If multiple `AGENTS.md` files could apply, explain the choice and ask the
  user which scope should own the link.

## Defaults

Use about three to seven sub-goals. Fewer than three often hides important
tradeoffs; more than seven usually becomes task tracking or documentation.

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
