---
name: automata-text-writing
description: Use for writing or editing human-maintained prose, Markdown, configuration, prompts and instructions where meaning and format matter. Not for editing generated output directly.
---

# Automata Text Writing

Make meaning clear while preserving the text's format and role.

1. **Understand the source.** Read relevant content and context. Identify maintained
   prose, structured configuration or generated output; each needs different checks.
   Edit the owning source when authorized, not generated files without explicit approval.

2. **Change only what serves the request.** Preserve unrelated content and conventions.
   Broader revision is appropriate when approved. Ask about ambiguity that changes
   meaning, scope or format, not ordinary wording choices. Do not silently reinterpret
   policy or requirements, redesign configuration or expose secrets in examples.

3. **Protect meaning and syntax.** Use plain language. Preserve comments, ordering,
   syntax and significant whitespace unless the change requires otherwise. Follow
   local wrapping; roughly 80 characters is a prose default, not a limit. Avoid
   unrelated reflow and wrapping code, URLs, tables or values that become less usable.
   Parsing successfully does not prove the intended meaning is preserved.

4. **Check and report.** Review conditions and exceptions; use available parsers or
   relevant checks for structured text. Fix defects caused by the edit within scope.
   Stop once the approved result is checked or explain the blocker. Report changes,
   assumptions and skipped checks without claiming unperformed validation.

For organizing related documents and navigation, use the independent guidance at
`skills/automata-documentation/SKILL.md`; ordinary edits need no tree restructuring.
