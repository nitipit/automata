---
name: automata-toolsmith
description: Use for deciding whether to automate repeated/risky mechanics or creating, reviewing and maintaining task helpers and reusable tools. Not for replacing judgment with frameworks.
---

# Automata Toolsmith

Build small inspectable mechanisms when reduced repetition, context cost or risk
justifies maintenance. Prefer existing tools or direct commands for simple work.

1. **Confirm owner and authority.** Task helpers need covered location, dependencies,
   effects and lifecycle. Packaged-source promotion and deployment need their own
   authority. Use the actual owner's storage conventions; keep operational helpers
   out of maintained/installed surfaces until promoted. Do not move assets or create
   directories merely for a model. Failure is investigation evidence, not repair
   permission; distinguish defects from invocation/setup problems and task workarounds
   from source repairs. Report unresolved defects even when alternatives work.

2. **Make operation clear.** Use cohesive CLI-first interfaces with explicit inputs,
   destinations, exit codes, useful errors and observable state. Provide JSON or
   human-readable output for actual consumers; add correlation/provenance when
   dispatch, completion and success could be confused. Put repeated preparation
   inside the tool. Tiny helpers need help or a short usage comment; maintained
   CLIs need defaults, surprising effects and recovery guidance. Process tools
   need status and graceful stop, not hidden unmanaged leftovers.

3. **Keep implementation proportionate.** Follow project conventions; shell suits
   tiny glue, structured languages suit parsing/state/retries. Read
   `references/stacks.md` for undecided stacks; preferences grant no installs.
   Prefer Cyclopts/Dictify for substantive Python agent CLIs when compatible,
   standard-library helpers when simpler. Verify real binding/schema behavior,
   not duplicate validation. Change interfaces for actual consumers and update
   mappings/docs; do not invent wrapper skills just to assign ownership.

4. **Verify before relying.** Check usage discovery and a representative operation.
   Repairs need the failure regression and a normal path. One-off helpers generally
   need smoke checks; maintained/risky tools need focused failure checks where
   justified and authorized. Report evidence and limits. Keep verified setup with
   its owner, separate from live handles; one successful experiment is not promotion.
