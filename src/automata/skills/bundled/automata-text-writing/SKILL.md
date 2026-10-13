---
name: automata-text-writing
description: Use for creating or editing human-maintained text such as Markdown, TOML, YAML, JSON, INI, .env.example, prompts or instructions when clarity, proportionate changes and format safety matter.
---

# Automata Text Writing

Make the intended meaning clear while preserving the file's format and role.
Apply these principles to the approved change, not a fixed editing workflow.

1. **Understand the text.** Inspect the relevant content and context. Distinguish
   prose, structured configuration and generated output; their correctness checks
   differ. Identify the intended meaning and the maintained source before editing.

2. **Edit proportionately.** Make the smallest useful change that satisfies the
   request; broader revision is appropriate when approved. Preserve unrelated
   content, surrounding structure and local conventions. Ask when ambiguity
   materially affects meaning, scope or formatting, not for ordinary wording
   decisions within the request.

3. **Protect format and semantics.** Use clear, direct language. Preserve syntax,
   comments, ordering and significant whitespace unless the intended change
   requires otherwise. Follow local wrapping conventions; around 80 characters is
   a useful prose default, not a limit. Avoid unrelated reflow and do not wrap
   URLs, code, tables or structured values when readability or semantics suffer.
   For structured text, change the intended values without altering unrelated
   behavior; a syntactically valid file can still mean the wrong thing.

4. **Verify the result.** Review the changed text for intended meaning and
   preservation of necessary conditions and exceptions. Use existing parsers,
   validators or relevant checks for structured text when practical; parsing alone
   does not verify semantics. Correct defects caused by the edit within scope.
   Stop when the approved result is verified, or report the blocker. Summarize
   meaningful changes, assumptions and skipped checks without claiming unperformed
   validation.

## Related documentation

For organizing related documentation, searchable sections, shared definitions and
navigation, the related guidance is `skills/automata-documentation/SKILL.md`,
relative to this skill directory. It stands independently; ordinary text edits
need no documentation-tree restructuring.

## Boundaries

Text editing does not authorize configuration-system redesign, broader
restructuring or editing generated outputs. Change their maintained source when
that is within scope; direct output edits need explicit approval. Do not silently
reinterpret policy, requirements or instructions, or expose secrets in examples.
