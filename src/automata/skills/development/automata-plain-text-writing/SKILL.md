---
name: automata-plain-text-writing
description: Use for creating or editing human-edited plain-text files such as Markdown, TOML, YAML, INI, .env.example, prompts, or instructions when clarity, minimal changes, and format safety matter.
---

# Automata Plain Text Writing

Write or revise human-edited plain-text files without treating them like code or generated
data.

## Principles

- Default to minimal edits that satisfy the request.
- Be interactive when scope, wording, formatting, or restructuring level is unclear.
- Allow broader restructuring when the user asks for it or confirms it.
- Preserve meaning, surrounding structure, and local conventions unless change is needed.
- Exclude JSON by default. Handle it only when the user clearly wants this skill for that
  file.

## Formatting

- Prefer clear, direct wording over decorative or overly compressed phrasing.
- Prefer prose lines around 80 characters when practical.
- Preserve clear file-local formatting conventions when they are obvious.
- Ask the user when wrapping or formatting preference is unclear and changing it would cause
  noticeable reflow.
- Do not reflow unrelated content just to normalize line length.
- Do not wrap lines when the format, semantics, or readability would suffer, such as URLs,
  tables, code fences, examples, or structured values.

## Workflow

1. Inspect the target file first.
2. Identify whether the task is prose editing, structured-text editing, or mixed.
3. Clarify ambiguity before making broad wording or structure changes.
4. Make the smallest useful edit unless the user wants broader revision.
5. Preserve comments, ordering, headings, and surrounding layout unless the change needs more.
6. Validate structured text when practical, using the repository's existing approach when
   available.
7. Summarize what changed and note any assumptions or skipped validation.

## Boundaries

- Do not treat plain-text editing as code implementation or configuration-system design.
- Do not make broad rewrites or file-wide reformatting unless the user asks for it or confirms
  it.
- Do not silently reinterpret ambiguous policy, requirements, or instruction text.
- Do not skip practical structured-text validation without saying so.
